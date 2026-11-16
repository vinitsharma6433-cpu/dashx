"""DASHX Autonomy: deeper READ-ONLY analytics (retention, subscribers, reach, saves, shares). Standard library only.

OFF BY DEFAULT. Each source switches on only when its OWN new secret exists in the environment. The machine never asks for a scope,
never creates a token and never changes one. With no secret, nothing is called and nothing is written.

  source           secret(s) that switch it on                         scope / permission the owner must grant first
  yt_analytics     YT_ANALYTICS_REFRESH_TOKEN (+ existing YT_CLIENT_ID,  https://www.googleapis.com/auth/yt-analytics.readonly
                   YT_CLIENT_SECRET)                                    (and the "YouTube Analytics API" enabled in the Google project)
  ig_insights      META_INSIGHTS_TOKEN (+ existing IG_USER_ID)          instagram_manage_insights (with instagram_basic, pages_read_engagement)
  fb_insights      META_INSIGHTS_TOKEN (+ existing FB_PAGE_ID)          read_insights (with pages_read_engagement)

Results go to autonomy/metrics.json under "insights" (an existing machine-notes file). A refused call is stored as DENIED, never retried
in a loop, and never printed with the token. Tests use mocked data only.
"""
from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import guard  # noqa: E402

ROOT = guard.ROOT
IST = guard.IST
OUT = "autonomy/metrics.json"
GRAPH = "https://graph.facebook.com/v21.0"
SOURCES = {
    "yt_analytics": {"needs": ["YT_ANALYTICS_REFRESH_TOKEN", "YT_CLIENT_ID", "YT_CLIENT_SECRET"], "scope": "https://www.googleapis.com/auth/yt-analytics.readonly"},
    "ig_insights": {"needs": ["META_INSIGHTS_TOKEN", "IG_USER_ID"], "scope": "instagram_manage_insights + instagram_basic + pages_read_engagement"},
    "fb_insights": {"needs": ["META_INSIGHTS_TOKEN", "FB_PAGE_ID"], "scope": "read_insights + pages_read_engagement"},
}
YT_METRICS = "views,averageViewDuration,averageViewPercentage,subscribersGained"
IG_METRICS = "reach,saved,shares,views"
FB_METRICS = "total_video_views,total_video_avg_time_watched"


def enabled(env: dict) -> dict[str, bool]:
    """Which sources are ON: every secret they need is present and not empty."""
    return {k: all(str(env.get(n, "")).strip() for n in v["needs"]) for k, v in SOURCES.items()}


def http_get(url: str, headers: dict | None = None, data: bytes | None = None) -> dict:
    req = urllib.request.Request(url, data=data, headers={"User-Agent": "DASHX-autonomy/1.0", **(headers or {})})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def _denied(e: Exception) -> str:
    code = getattr(e, "code", None)
    return f"DENIED (HTTP {code})" if code in (400, 401, 403) else f"error ({type(e).__name__})"


def yt_analytics(video_ids: list[str], env: dict, get=http_get, today=None) -> tuple[dict, str]:
    try:
        tok = get("https://oauth2.googleapis.com/token", data=urllib.parse.urlencode({
            "client_id": env["YT_CLIENT_ID"], "client_secret": env["YT_CLIENT_SECRET"],
            "refresh_token": env["YT_ANALYTICS_REFRESH_TOKEN"], "grant_type": "refresh_token"}).encode())["access_token"]
        today = today or datetime.now(IST).date()
        q = urllib.parse.urlencode({"ids": "channel==MINE", "metrics": YT_METRICS, "dimensions": "video", "filters": "video==" + ",".join(video_ids[:200]),
                                    "startDate": (today - timedelta(days=60)).isoformat(), "endDate": today.isoformat()})
        j = get("https://youtubeanalytics.googleapis.com/v2/reports?" + q, headers={"Authorization": "Bearer " + tok})
        cols = [c["name"] for c in j.get("columnHeaders", [])]
        out = {}
        for row in j.get("rows", []):
            d = dict(zip(cols, row))
            vid = d.pop("video", None)
            if vid:
                out[vid] = {"views": d.get("views"), "avg_view_seconds": d.get("averageViewDuration"),
                            "avg_view_percent": d.get("averageViewPercentage"), "subs_gained": d.get("subscribersGained")}
        return out, "ok"
    except Exception as e:
        return {}, _denied(e)


def ig_insights(media_ids: list[str], env: dict, get=http_get) -> tuple[dict, str]:
    out, status = {}, "ok"
    for mid in media_ids[:50]:
        try:
            j = get(f"{GRAPH}/{mid}/insights?" + urllib.parse.urlencode({"metric": IG_METRICS, "access_token": env["META_INSIGHTS_TOKEN"]}))
            out[mid] = {m["name"]: (m.get("values") or [{}])[0].get("value") for m in j.get("data", [])}
        except Exception as e:
            status = _denied(e)
            if status.startswith("DENIED"):
                break
    return out, status


def fb_insights(video_ids: list[str], env: dict, get=http_get) -> tuple[dict, str]:
    out, status = {}, "ok"
    for vid in video_ids[:50]:
        try:
            j = get(f"{GRAPH}/{vid}/video_insights?" + urllib.parse.urlencode({"metric": FB_METRICS, "access_token": env["META_INSIGHTS_TOKEN"]}))
            out[vid] = {m["name"]: (m.get("values") or [{}])[0].get("value") for m in j.get("data", [])}
        except Exception as e:
            status = _denied(e)
            if status.startswith("DENIED"):
                break
    return out, status


def ids_from_queue(posts: list[dict]) -> dict[str, dict[str, str]]:
    """title -> {yt, ig, fb} ids from the poster's own notes (our own reels only)."""
    out = {}
    for p in posts:
        n = p.get("notes") or {}
        ids = {k: str(n[f]) for k, f in (("yt", "yt_video_id"), ("ig", "ig_media_id"), ("fb", "fb_video_id")) if n.get(f)}
        if ids:
            out[p.get("title", "?")] = ids
    return out


def collect(posts: list[dict], env: dict, get=http_get, today=None) -> dict | None:
    """None when every source is OFF (nothing called). Otherwise {source: {"status", "by_reel": {title: {...}}}}."""
    on = enabled(env)
    if not any(on.values()):
        return None
    ids = ids_from_queue(posts)
    result = {}
    for src, key, fn in (("yt_analytics", "yt", lambda v: yt_analytics(v, env, get, today)), ("ig_insights", "ig", lambda v: ig_insights(v, env, get)),
                         ("fb_insights", "fb", lambda v: fb_insights(v, env, get))):
        if not on[src]:
            result[src] = {"status": "OFF (secret not set)"}
            continue
        wanted = {t: i[key] for t, i in ids.items() if key in i}
        data, status = fn(list(wanted.values()))
        back = {v: t for t, v in wanted.items()}
        result[src] = {"status": status, "by_reel": {back[k]: v for k, v in data.items() if k in back}}
    return result


def run(root: Path = ROOT, env: dict | None = None, get=http_get, now: datetime | None = None) -> dict | None:
    import os
    env = dict(os.environ) if env is None else env
    if guard.halted("all", root):
        return None
    try:
        posts = json.loads((root / "poster/queue.json").read_text(encoding="utf-8")).get("posts", [])
    except Exception:
        posts = []
    res = collect(posts, env, get)
    if res is None:
        return None                                                  # OFF: nothing called, nothing written
    if guard.classify(OUT, guard.load_rules())[0] != "state":
        raise PermissionError(f"{OUT} is not a machine-notes file")
    p = root / OUT
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    data["insights"] = {"updated": (now or datetime.now(IST)).isoformat(timespec="minutes"), **res}
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    return res


if __name__ == "__main__":
    r = run()
    print("analytics:", "OFF (no insights secret set)" if r is None else {k: v["status"] for k, v in r.items()})
