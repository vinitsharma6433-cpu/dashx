"""DASHX Autonomy, Phase 4: learning loop. Standard library only (the YouTube token comes from poster.yt_token, reused read-only).

READ-ONLY. It uses only the access we already have (rules: RULES.json `learning`):
  - YouTube Data API videos.list statistics (views, likes, comments)        - existing YouTube token
  - Instagram like_count / comments_count of our own posts                   - existing Meta token
  - Facebook likes / comments counts of our own reels                        - existing Meta token
  - our own hook score of the first spoken line (recomputed from the bank), format, characters, slot
If a source says "denied" it is recorded in learning.json under `availability` (the owner decides about a new permission) and the loop
carries on. It never asks for a scope, never changes a token, never prints one.

Score (0-100, simple): 60 percent reach (views per day, YouTube) + 40 percent reaction (likes + comments per day, all networks), each
measured against the MEDIAN of the reels we have data for (x / median, capped at 2, shown as 0-100). Below 5 reels with data nothing
is scored and nothing is steered. Output: autonomy/metrics.json (raw numbers), autonomy/learning.json (scores, groups, availability),
autonomy/slot_hints.json (a suggestion for one of the two existing slots; the slots themselves never change).
"""
from __future__ import annotations

import json
import re
import statistics
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import guard  # noqa: E402

ROOT = guard.ROOT
IST = guard.IST
GRAPH = "https://graph.facebook.com/v21.0"
NAMES = ("sachin", "surya", "dadaji", "aunty", "pintu", "golu", "meena", "coach", "bruno", "pappu", "chhotu", "mintu")
_ROW = re.compile(r"^- [\w-]+ \| (\w*) \| (\w*) \|", re.M)
STATE_OUT = ("autonomy/metrics.json", "autonomy/learning.json", "autonomy/slot_hints.json", "autonomy/log.md")


# ---------------------------------------------------------------- features of a reel (from the story bank)
def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def parse_bank(text: str) -> dict[str, dict]:
    """slug of the English title -> {format, cast, hook, first_line}. Never raises."""
    out = {}
    for blk in re.split(r"\n(?=## )", text or ""):
        if not blk.startswith("## "):
            continue
        try:
            en = blk.splitlines()[0][3:].split("|")[0].strip()
            cast = sorted({x for pair in _ROW.findall(blk) for x in pair if x in NAMES})
            rows = [ln for ln in blk.splitlines() if ln.startswith("- ") and ln.count("|") == 4]
            first = rows[0].split("|", 4)[-1].split("//")[0].split(":", 1)[-1].strip() if rows else ""
            hook = (re.search(r"^hook:[ \t]*(.*)$", blk, re.M) or [None, ""])[1].strip()
            if re.search(r"^series:[ \t]*\S", blk, re.M):
                fmt = "series"
            elif "pappu" in cast and "chhotu" in cast:
                fmt = "shop"
            elif "pappu" in cast and "mintu" in cast:
                fmt = "rivalry"
            else:
                fmt = "normal"
            out[slug(en)] = {"format": fmt, "cast": cast, "hook": hook, "first_line": first}
        except Exception:
            continue
    return out


def hook_type(text: str) -> str:
    """A simple style label for a hook line: question / number / exclaim / statement."""
    t = text or ""
    if "?" in t or "？" in t:
        return "question"
    if re.search(r"[0-9०-९]", t):
        return "number"
    if "!" in t:
        return "exclaim"
    return "statement"


def first_line_score(line: str) -> float | None:
    try:
        sys.path.insert(0, str(ROOT / "reelfactory" / "scripts"))
        import story_rules  # noqa: PLC0415
        return float(story_rules.hook_score(line)["score"])
    except Exception:
        return None


# ---------------------------------------------------------------- collectors (read-only calls, token never printed)
class Denied(Exception):
    pass


def _get(url: str, headers: dict | None = None) -> dict:
    req = urllib.request.Request(url, headers=headers or {"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            msg = json.loads(e.read()).get("error", {})
            detail = msg.get("message", "") if isinstance(msg, dict) else str(msg)
        except Exception:
            detail = ""
        detail = re.sub(r"(access_token|token)=[^&\s]+", r"\1=***", detail)[:140]
        if e.code in (400, 401, 403):
            raise Denied(f"HTTP {e.code}: {detail}") from None
        raise RuntimeError(f"HTTP {e.code}") from None


def yt_stats(ids: list[str], token: str) -> dict[str, dict]:
    out = {}
    for i in range(0, len(ids), 50):
        j = _get("https://www.googleapis.com/youtube/v3/videos?part=statistics&id=" + ",".join(ids[i:i + 50]), {"Authorization": "Bearer " + token})
        for it in j.get("items", []):
            s = it.get("statistics", {})
            out[it["id"]] = {"views": int(s.get("viewCount", 0)), "likes": int(s.get("likeCount", 0)), "comments": int(s.get("commentCount", 0))}
    return out


def ig_stats(media_id: str, token: str) -> dict:
    j = _get(f"{GRAPH}/{media_id}?" + urllib.parse.urlencode({"fields": "like_count,comments_count", "access_token": token}))
    return {"likes": int(j.get("like_count", 0)), "comments": int(j.get("comments_count", 0))}


def fb_stats(video_id: str, token: str) -> dict:
    j = _get(f"{GRAPH}/{video_id}?" + urllib.parse.urlencode({"fields": "likes.summary(true).limit(0),comments.summary(true).limit(0)", "access_token": token}))
    return {"likes": int(j.get("likes", {}).get("summary", {}).get("total_count", 0)), "comments": int(j.get("comments", {}).get("summary", {}).get("total_count", 0))}


class Live:
    """The real collectors. Tokens come from the job's environment (the existing secrets); nothing is printed."""
    def __init__(self, env: dict):
        self.env = env

    def yt_token(self) -> str | None:
        if not all(self.env.get(k) for k in ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN")):
            return None
        sys.path.insert(0, str(ROOT / "poster"))
        import poster as P  # noqa: PLC0415
        return P.yt_token()

    def meta_token(self) -> str | None:
        return (self.env.get("META_PAGE_TOKEN") or "").strip() or None

    yt = staticmethod(yt_stats)
    ig = staticmethod(ig_stats)
    fb = staticmethod(fb_stats)


# ---------------------------------------------------------------- collect
def video_ids(p: dict) -> dict[str, str]:
    """Ids of the live posts: from notes, or (older posts) from the saved link. Only networks that were posted ok."""
    notes, res, out = p.get("notes", {}), p.get("results", {}), {}
    link = lambda n: str(res.get(n, {}).get("link", ""))      # noqa: E731
    if res.get("youtube", {}).get("ok"):
        m = re.search(r"/shorts/([\w-]{6,})", link("youtube"))
        vid = notes.get("yt_video_id") or (m.group(1) if m else "")
        if vid:
            out["youtube"] = vid
    if res.get("facebook", {}).get("ok"):
        m = re.search(r"/reel/(\d+)", link("facebook"))
        vid = notes.get("fb_video_id") or (m.group(1) if m else "")
        if vid:
            out["facebook"] = vid
    if res.get("instagram", {}).get("ok"):
        l = link("instagram")
        vid = notes.get("ig_media_id") or (l.split(":", 1)[1] if l.startswith("instagram:") else "")
        if vid:
            out["instagram"] = vid
    return out


def candidates(posts: list[dict], now: datetime, rules: dict) -> list[dict]:
    L = rules["learning"]
    out = []
    for p in posts:
        try:
            due = datetime.fromisoformat(p["when"])
        except Exception:
            continue
        age = now - due
        if age < timedelta(hours=L["min_age_hours"]) or age > timedelta(days=L["window_days"]):
            continue
        if "DASHX" not in p.get("title", "") or p.get("title", "").startswith("META TEST"):
            continue
        out.append(p)
    return out


def collect(posts: list[dict], now: datetime, rules: dict, live) -> tuple[dict, dict]:
    """(metrics by title, availability by source). A denied source is skipped from then on."""
    avail: dict[str, str] = {}
    metrics: dict[str, dict] = {}
    cand = candidates(posts, now, rules)
    yt_ids = {video_ids(p)["youtube"]: p["title"] for p in cand if "youtube" in video_ids(p)}
    if yt_ids:
        try:
            tok = live.yt_token()
            if not tok:
                avail["youtube_statistics"] = "no token in this job"
            else:
                for vid, st in live.yt(list(yt_ids), tok).items():
                    metrics.setdefault(yt_ids[vid], {})["youtube"] = st
                avail["youtube_statistics"] = "ok"
        except Denied as e:
            avail["youtube_statistics"] = f"DENIED ({e}): owner must decide about a YouTube read scope"
        except Exception as e:
            avail["youtube_statistics"] = f"error {type(e).__name__}"
    mt = live.meta_token()
    for net, key, fn in (("instagram", "instagram_counts", live.ig), ("facebook", "facebook_counts", live.fb)):
        todo = [p for p in cand if net in video_ids(p)]
        if not todo:
            continue
        if not mt:
            avail[key] = "no token in this job"
            continue
        for p in todo:
            try:
                metrics.setdefault(p["title"], {})[net] = fn(video_ids(p)[net], mt)
                avail[key] = "ok"
            except Denied as e:
                avail[key] = f"DENIED ({e}): owner must decide about this Meta permission"
                break                                   # do not keep calling a denied endpoint
            except Exception as e:
                avail.setdefault(key, f"error {type(e).__name__}")
    return metrics, avail


# ---------------------------------------------------------------- score + groups
def _rel(x: float, med: float) -> float:
    if med <= 0:
        return 0.5 if x <= 0 else 1.0
    return min(x / med, 2.0) / 2.0


def score_reels(posts: list[dict], metrics: dict, bank: dict, now: datetime, rules: dict) -> list[dict]:
    L = rules["learning"]
    rows = []
    for p in candidates(posts, now, rules):
        m = metrics.get(p["title"])
        if not m:
            continue
        days = max((now - datetime.fromisoformat(p["when"])).total_seconds() / 86400, 0.25)
        views = m.get("youtube", {}).get("views", 0)
        react = sum(v.get("likes", 0) + v.get("comments", 0) for v in m.values())
        feat = bank.get(slug(p["title"].replace(" DASHX", "")))
        if not feat:
            continue                                      # only story-bank dialogue reels are compared with each other (not ads or old narration)
        slot = datetime.fromisoformat(p["when"]).strftime("%H:%M")
        rows.append({"title": p["title"], "views_per_day": round(views / days, 2), "reactions_per_day": round(react / days, 2),
                     "format": feat.get("format"), "cast": feat.get("cast", []), "slot": slot,
                     "hook_type": hook_type(feat.get("hook", "")),
                     "hook_score": first_line_score(feat.get("first_line", ""))})
    if len(rows) < L["min_reels_with_data"]:
        return rows
    mv = statistics.median(r["views_per_day"] for r in rows)
    mr = statistics.median(r["reactions_per_day"] for r in rows)
    W = L["score_weights"]
    for r in rows:
        r["score"] = round(100 * (W["reach"] * _rel(r["views_per_day"], mv) + W["reaction"] * _rel(r["reactions_per_day"], mr)), 1)
    return rows


def groups(rows: list[dict], rules: dict) -> dict:
    """dimension -> value -> {avg, n}. Only values with enough reels (min_group_size) get an average."""
    need = rules["learning"]["min_group_size"]
    acc: dict[str, dict[str, list[float]]] = {"format": {}, "hook_type": {}, "character": {}, "slot": {}}
    for r in rows:
        if "score" not in r:
            continue
        for dim, vals in (("format", [r["format"]]), ("hook_type", [r["hook_type"]]), ("character", r["cast"]), ("slot", [r["slot"]])):
            for v in vals:
                if v:
                    acc[dim].setdefault(v, []).append(r["score"])
    return {d: {v: {"avg": round(sum(s) / len(s), 1), "n": len(s)} for v, s in vs.items() if len(s) >= need} | {v: {"avg": None, "n": len(s)} for v, s in vs.items() if len(s) < need}
            for d, vs in acc.items()}


def slot_hint(grp: dict, rules: dict) -> dict:
    s = {k: v for k, v in grp.get("slot", {}).items() if v["avg"] is not None}
    if len(s) < 2:
        return {"best_slot": None, "note": "not enough data for both slots yet", "slots": s}
    best = max(s, key=lambda k: s[k]["avg"])
    return {"best_slot": best, "slots": s, "note": "A suggestion only. The two slots (12:30 and 20:30) are fixed in queue_config.json and the machine never changes them."}


# ---------------------------------------------------------------- run
def _write_state(root: Path, rel: str, data) -> None:
    if rel not in STATE_OUT or guard.classify(rel, guard.load_rules())[0] != "state":
        raise PermissionError(f"{rel} is not a machine-notes file")
    (root / rel).parent.mkdir(parents=True, exist_ok=True)
    (root / rel).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def _read(root: Path, rel: str, default):
    try:
        return json.loads((root / rel).read_text(encoding="utf-8"))
    except Exception:
        return default


def run(root: Path = ROOT, now: datetime | None = None, force: bool = False, live=None) -> dict | None:
    now = (now or datetime.now(IST)).astimezone(IST)
    if guard.halted("all", root):
        print(f"{guard.halted('all', root)} is on: learning loop does nothing")
        return None
    rules = guard.load_rules()
    L = rules["learning"]
    old = _read(root, "autonomy/learning.json", {})
    try:
        if not force and now - datetime.fromisoformat(old["updated"]) < timedelta(hours=L["refresh_after_hours"]):
            print("learning.json is fresh, nothing to do")
            return None
    except Exception:
        pass
    posts = _read(root, "poster/queue.json", {"posts": []}).get("posts", [])
    bank = parse_bank((root / "reelfactory/stories/dialogue_bank.md").read_text(encoding="utf-8")) if (root / "reelfactory/stories/dialogue_bank.md").exists() else {}
    posts_story = [p for p in posts if slug(p.get("title", "").replace(" DASHX", "")) in bank]      # dialogue reels from the story bank only
    metrics, avail = collect(posts_story, now, rules, live)
    store = _read(root, "autonomy/metrics.json", {"reels": {}})
    for title, m in metrics.items():                       # keep the latest numbers per reel
        store["reels"][title] = dict(m, at=now.isoformat(timespec="minutes"))
    store["reels"] = {t: v for t, v in store["reels"].items() if any(p.get("title") == t for p in posts)}
    rows = score_reels(posts, {t: {k: v for k, v in m.items() if k != "at"} for t, m in store["reels"].items()}, bank, now, rules)
    grp = groups(rows, rules)
    enough = len([r for r in rows if "score" in r]) >= L["min_reels_with_data"]
    out = {"updated": now.isoformat(timespec="minutes"), "enough_data": enough, "reels_with_data": len(rows),
           "need": L["min_reels_with_data"], "availability": avail, "needs_owner_for_more": L["not_available_without_owner"],
           "reels": rows, "groups": grp,
           "steer": {"dimensions": L["steer_dimensions"], "explore_share": L["explore_share"], "active": enough}}
    _write_state(root, "autonomy/metrics.json", store)
    _write_state(root, "autonomy/learning.json", out)
    if enough:
        _write_state(root, "autonomy/slot_hints.json", slot_hint(grp, rules))
    denied = [k for k, v in avail.items() if str(v).startswith("DENIED")]
    lp = root / "autonomy" / "log.md"
    lp.parent.mkdir(parents=True, exist_ok=True)
    with open(lp, "a", encoding="utf-8", newline="\n") as f:
        f.write(f"- {now.strftime('%Y-%m-%d %H:%M')} IST | info | learning | {len(rows)} reels with data (need {L['min_reels_with_data']}), steering {'ON' if enough else 'OFF'}; availability: "
                + ", ".join(f"{k}={str(v)[:24]}" for k, v in avail.items()) + f"{'; NEEDS OWNER: ' + ', '.join(denied) if denied else ''} | written\n")
    return out


if __name__ == "__main__":
    import os
    try:
        d = run(force="--force" in sys.argv, live=Live(dict(os.environ)))
    except guard.RulesTampered as e:
        print(f"::error::RULES TAMPERED ({e}). Learning loop stopped.")
        sys.exit(1)
    if d:
        print(f"reels with data: {d['reels_with_data']} (need {d['need']}); steering {'ON' if d['steer']['active'] else 'OFF'}")
        for k, v in d["availability"].items():
            print(f"  {k}: {v}")
