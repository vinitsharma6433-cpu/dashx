"""DASHX Autonomy: the weekly "NotebookLM pack" (autonomy/notebooklm_pack.md). Standard library only.

NotebookLM has no API, so the machine only PREPARES a study pack; the owner pastes it into NotebookLM by hand.
  (a) our own top 5 and bottom 5 reels of the last 7 days: links and numbers from the poster queue + autonomy/metrics.json
  (b) 5 to 10 public YouTube Shorts in our niche that look like hits: ONLY with a YouTube Data API key (env YT_API_KEY).
      Without it this part is left empty and says so. Only links, views and dates are kept: never a title, a channel name,
      a description, a script or any other creator's words.
  (c) a fixed list of study questions.
Writes ONLY autonomy/notebooklm_pack.md, and only when RULES.json lists it as a machine-notes file (fail closed). Once a week.
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import guard  # noqa: E402

ROOT = guard.ROOT
IST = guard.IST
OUT = "autonomy/notebooklm_pack.md"
NETS = ("youtube", "instagram", "facebook")
NICHE_QUERIES = ["gully cricket shorts hindi", "hindi cartoon comedy shorts", "kids family comedy shorts hindi"]
QUESTIONS = [
    "Hook: what happens in the very first line or frame, and why does it stop the scroll?",
    "First 3 seconds: what does the viewer see and hear before any setup?",
    "Length: how long is the reel, and where would you cut 2 seconds?",
    "Emotion: which single feeling does it aim for (laugh, surprise, pride, nostalgia)?",
    "Ending: how does the last scene flip or pay off what came before?",
    "Shareable: why would a kid or a parent send this to a friend?",
    "Compared with our bottom 5: what is missing in ours?",
]
VID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


def week_tag(now: datetime) -> str:
    y, w, _ = now.isocalendar()
    return f"{y}-W{w:02d}"


def due(root: Path, now: datetime) -> bool:
    p = root / OUT
    return not (p.exists() and f"<!-- week: {week_tag(now)} -->" in p.read_text(encoding="utf-8"))


def own_reels(posts: list[dict], metrics: dict, now: datetime) -> list[dict]:
    """Our reels posted in the last 7 days with links and per-day numbers. Only OUR OWN data."""
    rows = []
    for p in posts:
        try:
            due_at = datetime.fromisoformat(p["when"])
        except Exception:
            continue
        if not (now - timedelta(days=7) <= due_at <= now):
            continue
        res = p.get("results") or {}
        if not any((res.get(n) or {}).get("ok") for n in NETS):
            continue
        m = (metrics.get("reels") or {}).get(p.get("title", ""), {})
        days = max(1.0, (now - due_at).total_seconds() / 86400)
        nets = {}
        for n in NETS:
            r = res.get(n) or {}
            mm = m.get(n) or {}
            nets[n] = {"link": r.get("link", ""), "views": mm.get("views"), "likes": mm.get("likes"), "comments": mm.get("comments"),
                       "views_per_day": round(mm["views"] / days, 1) if isinstance(mm.get("views"), (int, float)) else None}
        yt = nets["youtube"]["views_per_day"]
        rows.append({"reel": str(p.get("title", "?")).replace(" DASHX", ""), "posted": due_at.strftime("%Y-%m-%d"), "nets": nets,
                     "rank": yt if yt is not None else -1})
    return sorted(rows, key=lambda r: -r["rank"])


def niche_hits(key: str, now: datetime, get=None) -> list[dict]:
    """Public Shorts that look like hits: ONLY the video link, views and publish date are kept."""
    get = get or (lambda url: json.loads(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "DASHX-autonomy/1.0"}), timeout=30).read()))
    ids: list[str] = []
    after = (now - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    for q in NICHE_QUERIES:
        j = get("https://www.googleapis.com/youtube/v3/search?" + urllib.parse.urlencode({
            "part": "id", "type": "video", "videoDuration": "short", "order": "viewCount", "regionCode": "IN", "relevanceLanguage": "hi",
            "publishedAfter": after, "maxResults": 10, "q": q, "key": key}))
        ids += [i["id"]["videoId"] for i in j.get("items", []) if VID_RE.match(str(i.get("id", {}).get("videoId", "")))]
    ids = list(dict.fromkeys(ids))[:30]
    if not ids:
        return []
    j = get("https://www.googleapis.com/youtube/v3/videos?" + urllib.parse.urlencode({"part": "statistics,snippet", "id": ",".join(ids), "key": key}))
    out = []
    for v in j.get("items", []):
        vid = str(v.get("id", ""))
        if not VID_RE.match(vid):
            continue
        try:
            views = int(v["statistics"]["viewCount"])
            date = str(v["snippet"]["publishedAt"])[:10]
        except Exception:
            continue
        out.append({"link": f"https://www.youtube.com/shorts/{vid}", "views": views, "published": date})   # nothing else is kept
    return sorted(out, key=lambda r: -r["views"])[:10]


def render(now: datetime, rows: list[dict], hits: list[dict] | None, why_no_hits: str) -> str:
    L = [f"# DASHX NotebookLM pack, week {week_tag(now)}", f"<!-- week: {week_tag(now)} -->", "",
         "How to use: open NotebookLM, make a notebook, paste this whole page as a source, add the reel links as sources, then ask the study questions.",
         "Written by the machine once a week. Our own numbers only; public reels are links and numbers only (no titles, no channel names, no text).", ""]

    def line(r):
        parts = []
        for n in NETS:
            x = r["nets"][n]
            if not x["link"]:
                continue
            nums = ", ".join(f"{k} {x[k]}" for k in ("views", "views_per_day", "likes", "comments") if x.get(k) is not None) or "no numbers yet"
            parts.append(f"{n}: {x['link']} ({nums})")
        return f"- {r['reel']} (posted {r['posted']}): " + "; ".join(parts)
    L.append("## (a) Our top 5 reels this week (by YouTube views per day)")
    L += [line(r) for r in rows[:5]] or ["- no reel posted in the last 7 days"]
    L += ["", "## (a) Our bottom 5 reels this week"]
    L += [line(r) for r in rows[-5:][::-1]] if len(rows) > 5 else ["- fewer than 6 reels this week: see the top list"]
    L += ["", "Note: Instagram and Facebook show likes and comments only. Views per day there need the insights permission (owner)."]
    L += ["", "## (b) Public Shorts in our niche that look like hits"]
    if hits is None:
        L.append(f"- Left empty: {why_no_hits}")
    else:
        L += [f"- {h['link']} ({h['views']} views, published {h['published']})" for h in hits] or ["- nothing found this week"]
    L += ["", "## (c) Study questions (ask NotebookLM for each reel)"] + [f"{i}. {q}" for i, q in enumerate(QUESTIONS, 1)]
    return "\n".join(L) + "\n"


def run(root: Path = ROOT, now: datetime | None = None, env: dict | None = None, get=None, force: bool = False) -> str:
    now = (now or datetime.now(IST)).astimezone(IST)
    env = dict(os.environ) if env is None else env
    if guard.halted("all", root):
        return "halted"
    if not force and not due(root, now):
        return "already done this week"
    if guard.classify(OUT, guard.load_rules())[0] != "state":
        return "refused: RULES.json does not list autonomy/notebooklm_pack.md as a machine-notes file"
    try:
        posts = json.loads((root / "poster/queue.json").read_text(encoding="utf-8")).get("posts", [])
    except Exception:
        posts = []
    try:
        metrics = json.loads((root / "autonomy/metrics.json").read_text(encoding="utf-8"))
    except Exception:
        metrics = {}
    hits, why = None, "no YouTube Data API key (secret YT_API_KEY) exists, so the machine does not search public videos"
    key = str(env.get("YT_API_KEY", "")).strip()
    if key:
        try:
            hits = niche_hits(key, now, get)
        except Exception as e:
            hits, why = None, f"the search failed this week ({type(e).__name__})"
    (root / OUT).parent.mkdir(parents=True, exist_ok=True)
    (root / OUT).write_text(render(now, own_reels(posts, metrics, now), hits, why), encoding="utf-8", newline="\n")
    return "written"


if __name__ == "__main__":
    print("notebooklm pack:", run(force="--force" in sys.argv))
