"""DASHX Pattern Engine: the ONE weekly self-learning pipeline (a small 'NotebookLM' inside the repo). Standard library only.

  our reels (autonomy/learning.json: views_per_day, reactions_per_day + the 7 genome tags from the story bank)
    -> weekly genome stats (decay, single tags, 2-way combinations, 3-way only with 60+ tagged reels)
    -> experiments: UCB1 (seeded by the ISO week), 80/20 blueprint, KEEP / DROP / MUTATE / WAIT, quarantine 21 days
  public niche Shorts (ONLY with a YouTube Data API key that already exists; otherwise this part is skipped and the brief says so)
    -> pattern_analyzer (enum labels only, instruction-like text dropped, at most min(calls_left, 5) Gemini calls a week)
    -> pattern_advisor (gaps between the niche and our own reels)
  outputs (every one is enums, numbers or our own reel slugs; never an outside title, quote, comment or channel name):
    autonomy/trend_patterns.json   this week's result      autonomy/trend_history.json   the 12-week window
    autonomy/notebooklm_pack.md    the pack for manual NotebookLM use (autonomy/notebooklm.py)
    status/daily.md                a brief of at most 15 lines (autonomy/report.py calls brief())

PROPOSE-ONLY: nothing here edits story generation, bank selection, the queue or any other file. KEEP / DROP / MUTATE and the blueprint are
lines in the report. Phase 2 (retention diagnostics) is written but OFF until DASHX_PATTERN_PHASE2=on AND YouTube Analytics data exists.
All three outputs are written only when RULES.json lists them as machine-notes files (fail closed).
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import genome  # noqa: E402
import guard  # noqa: E402
import pattern_advisor as adv  # noqa: E402
import pattern_analyzer as pan  # noqa: E402

ROOT = guard.ROOT
IST = guard.IST
OUT_PATTERNS = "autonomy/trend_patterns.json"
OUT_HISTORY = "autonomy/trend_history.json"
OUT_PACK = "autonomy/notebooklm_pack.md"
USAGE = "reelfactory/stories/refill_usage.json"
OUTPUTS = (OUT_PATTERNS, OUT_HISTORY, OUT_PACK)
NICHE_QUERIES = ["gully cricket shorts hindi", "hindi cartoon comedy shorts", "kids family comedy shorts hindi"]
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
MODEL = "gemini-flash-latest"
REFILL_SHARE = 3            # calls of the daily cap that always stay free for the Story Refill
KEY_RE = re.compile(r"^(" + "|".join(adv.FIELDS) + r")=[a-z0-9_]+(\+(" + "|".join(adv.FIELDS) + r")=[a-z0-9_]+){0,2}$")


# ---------------------------------------------------------------- small helpers
def _rd(root: Path, rel: str, default):
    try:
        return json.loads((root / rel).read_text(encoding="utf-8"))
    except Exception:
        return default


def write_state(root: Path, rel: str, text: str) -> None:
    if guard.classify(rel, guard.load_rules())[0] != "state":
        raise PermissionError(f"{rel} is not a machine-notes file")
    (root / rel).parent.mkdir(parents=True, exist_ok=True)
    (root / rel).write_text(text, encoding="utf-8", newline="\n")


def quota_day(now: datetime) -> str:
    return ((now.astimezone(timezone.utc)) - timedelta(hours=8)).date().isoformat()


def calls_available(root: Path, now: datetime) -> int:
    """Calls this pipeline may still use today: the daily cap minus what is used minus the share the Story Refill keeps."""
    u = _rd(root, USAGE, {})
    used = int(u.get("calls", 0)) if u.get("day") == quota_day(now) else 0
    return max(0, int(u.get("cap", 12) or 12) - used - REFILL_SHARE)


def take_call(root: Path, now: datetime) -> bool:
    """Count ONE call in the Story Refill's daily counter (refill_usage.json), keeping the grade results in that file."""
    u = _rd(root, USAGE, {})
    day = quota_day(now)
    calls = int(u.get("calls", 0)) if u.get("day") == day else 0
    cap = int(u.get("cap", 12) or 12)
    if cap - calls - 1 < REFILL_SHARE:
        return False
    u.update({"day": day, "calls": calls + 1, "cap": cap})
    p = root / USAGE
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(u, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    return True


def ask_gemini(prompt: str, key: str) -> str:
    req = urllib.request.Request(GEMINI_URL, data=json.dumps({"model": MODEL, "messages": [{"role": "user", "content": prompt}], "temperature": 0,
                                                             "max_tokens": 600, "reasoning_effort": "low"}).encode(),
                                 headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:             # ONE attempt: a failed call is counted and never retried
        return json.loads(r.read().decode("utf-8"))["choices"][0]["message"]["content"] or ""


def http_json(url: str) -> dict:
    return json.loads(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "DASHX-autonomy/1.0"}), timeout=30).read())


def fetch_videos(key: str, now: datetime, get=http_json) -> list[dict]:
    """Public Shorts of the niche: search (3 queries) + one videos.list. Returns analyzer records; they live in memory only."""
    after = (now - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    ids: list[str] = []
    for q in NICHE_QUERIES:
        j = get("https://www.googleapis.com/youtube/v3/search?" + urllib.parse.urlencode({
            "part": "id", "type": "video", "videoDuration": "short", "order": "viewCount", "regionCode": "IN", "relevanceLanguage": "hi",
            "publishedAfter": after, "maxResults": 10, "q": q, "key": key}))
        ids += [i["id"]["videoId"] for i in j.get("items", []) if isinstance(i.get("id"), dict) and re.fullmatch(r"[A-Za-z0-9_-]{11}", str(i["id"].get("videoId", "")))]
    ids = list(dict.fromkeys(ids))[:30]
    if not ids:
        return []
    j = get("https://www.googleapis.com/youtube/v3/videos?" + urllib.parse.urlencode({"part": "snippet,contentDetails,statistics", "id": ",".join(ids), "key": key}))
    recs = pan.parse_youtube_items(j)
    for r, it in zip(recs, j.get("items", [])):
        r["published"] = str((it.get("snippet") or {}).get("publishedAt", ""))[:10]
    return [r for r in recs if re.fullmatch(r"[A-Za-z0-9_-]{11}", str(r.get("id", ""))) and (r.get("duration_sec") or 0) <= 60]


# ---------------------------------------------------------------- our own reels
def own_rows(root: Path) -> list[dict]:
    """Reels with performance data, from autonomy/learning.json (NOT from poster/queue.json). Tags are validated enums."""
    out = []
    for r in _rd(root, "autonomy/learning.json", {}).get("reels", []):
        try:
            out.append({"slug": str(r.get("title", "")).replace(" DASHX", ""), "views_per_day": float(r.get("views_per_day") or 0),
                        "reactions_per_day": float(r.get("reactions_per_day") or 0), "tags": genome.validate(r.get("tags")),
                        "posted": str(r.get("posted") or ""), "hook_score": r.get("hook_score")})
        except Exception:
            continue
    return out


def phase2_on(root: Path, env: dict) -> bool:
    """Retention diagnostics: ON only with DASHX_PATTERN_PHASE2=on AND YouTube Analytics data in autonomy/metrics.json."""
    if str(env.get("DASHX_PATTERN_PHASE2", "")).strip().lower() != "on":
        return False
    yt = (_rd(root, "autonomy/metrics.json", {}).get("insights") or {}).get("yt_analytics") or {}
    return str(yt.get("status", "")).startswith("ok") and bool(yt.get("by_reel"))


def phase2_scores(rows: list[dict], root: Path) -> tuple[list[float], str]:
    """Virality score per reel (phase 2). Falls back to views_per_day (and says so) when a metric is missing."""
    by = ((_rd(root, "autonomy/metrics.json", {}).get("insights") or {}).get("yt_analytics") or {}).get("by_reel", {})
    full = []
    for r in rows:
        m = by.get(r["slug"] + " DASHX") or {}
        views = r["views_per_day"]
        full.append({"views_per_day": views, "avg_percentage_viewed": m.get("avg_view_percent"),
                     "shares_per_1k_views": m.get("shares_per_1k_views"),
                     "sub_conversion_rate": (m.get("subs_gained") / m["views"]) if m.get("views") and m.get("subs_gained") is not None else None})

    def med(k):
        xs = sorted(x[k] for x in full if x.get(k) is not None)
        return xs[len(xs) // 2] if xs else 0
    medians = {k: med(k) for k in ("views_per_day", "avg_percentage_viewed", "shares_per_1k_views", "sub_conversion_rate")}
    res = [adv.virality(x, medians) for x in full]
    return [s for s, _ in res], ("full" if res and all(m == "full" for _, m in res) else "views_only (a retention metric is missing)")


# ---------------------------------------------------------------- one weekly run
def run(root: Path = ROOT, now: datetime | None = None, env: dict | None = None, get=None, ask=None, force: bool = False) -> str:
    now = (now or datetime.now(IST)).astimezone(IST)
    env = dict(os.environ) if env is None else env
    if guard.halted("all", root):
        return "halted"
    week = adv.week_tag(now.date())
    prev = _rd(root, OUT_PATTERNS, {})
    if not force and prev.get("week") == week:
        return "already done this week"
    rules = guard.load_rules()
    missing = [p for p in OUTPUTS if guard.classify(p, rules)[0] != "state"]
    if missing:
        return "refused: RULES.json does not list " + ", ".join(missing) + " as machine-notes files"
    today = now.date()
    hist = _rd(root, OUT_HISTORY, {})
    hist = {"niche": hist.get("niche", []) if isinstance(hist.get("niche"), list) else [], "own": hist.get("own", []) if isinstance(hist.get("own"), list) else [],
            "quarantine": hist.get("quarantine", []) if isinstance(hist.get("quarantine"), list) else []}
    hist["quarantine"] = [q for q in hist["quarantine"] if isinstance(q, dict) and KEY_RE.match(str(q.get("key", ""))) and str(q.get("until", "")) >= today.isoformat()]

    # --- our own reels: weekly stats (the weeks that still have reels in learning.json are recomputed)
    rows = own_rows(root)
    p2 = phase2_on(root, env)
    if rows:
        if p2:
            scores, mode = phase2_scores(rows, root)
        else:
            scores, mode = adv.reel_scores(rows), "views and reactions per day"
    else:
        scores, mode = [], "no reels with data yet"
    tagged_before = adv.tagged_total([e for e in hist["own"] if e["week"] not in {adv.week_tag(datetime.fromisoformat(r["posted"]).date()) for r in rows if r["posted"]}])
    tagged_now = sum(1 for r in rows if r["tags"])
    max_k = 3 if tagged_before + tagged_now >= adv.THREE_WAY_MIN_REELS else 2
    by_week: dict[str, list[int]] = {}
    for i, r in enumerate(rows):
        if r["posted"]:
            by_week.setdefault(adv.week_tag(datetime.fromisoformat(r["posted"]).date()), []).append(i)
    for wk, idx in by_week.items():
        hist["own"] = adv.update_own_history(hist["own"], wk, adv.week_stats([rows[i] for i in idx], [scores[i] for i in idx], max_k))
    # --- the public niche (optional): ONLY with a key that already exists
    external, niche_agg, hits = {"status": "skipped: no YouTube Data API key (secret YT_API_KEY) exists"}, None, None
    yt_key, gem_key = str(env.get("YT_API_KEY", "")).strip(), str(env.get("GEMINI_API_KEY", "")).strip()
    if yt_key and gem_key:
        try:
            vids = fetch_videos(yt_key, now, get or http_json)
            hits = sorted([{"link": f"https://www.youtube.com/shorts/{v['id']}", "views": v["views"], "published": v.get("published", "")} for v in vids], key=lambda h: -h["views"])[:10]
            left = calls_available(root, now)

            def call_model(prompt):
                if not take_call(root, now):
                    raise RuntimeError("no budget")
                return (ask or (lambda p: ask_gemini(p, gem_key)))(prompt)
            pats, log, used = pan.analyze(vids, call_model, left)
            niche_agg = pan.aggregate(pats, today.isoformat())
            hist["niche"] = adv.update_history(hist["niche"], niche_agg)
            external = {"status": "ok", "videos": len(vids), "patterns_labelled": len(pats), "model_calls": used}
        except Exception as e:
            external = {"status": f"failed ({type(e).__name__})"}
    elif yt_key:
        external = {"status": "skipped: no GEMINI_API_KEY in this workflow"}
    # --- advisor: verdicts, quarantine, experiments, blueprint
    now_week = week
    st, verdicts, newq = adv.decision_report(hist["own"], now_week, today, hist["quarantine"])
    for q in newq:
        if not adv.is_quarantined(hist["quarantine"], q["key"], today):
            hist["quarantine"].append(q)
    flat = [dict(r["tags"], views_per_day=r["views_per_day"]) for r in rows]
    proposals = adv.propose_experiments(niche_agg, flat, hist["niche"], None, today) if niche_agg else []
    rising = adv.rising_patterns(hist["niche"])
    bp = adv.blueprint(hist["own"], now_week, genome.ENUMS, today, hist["quarantine"], proposals)
    active = []
    for e in (prev.get("blueprint") or {}).get("experiments", []):
        k = e.get("key", "")
        if not KEY_RE.match(k):
            continue
        s = st.get(k, {"n": 0, "lift": None})
        active.append({"key": k, "n": s["n"], "lift": s["lift"], "status": verdicts.get(k, "wait").upper() + ("" if s["n"] >= adv.MIN_TAGGED_REELS else f" (needs {adv.MIN_TAGGED_REELS} reels)")})
    patterns = {k: dict(v, verdict=verdicts[k]) for k, v in sorted(st.items(), key=lambda kv: (-kv[1]["n"], kv[0])) if KEY_RE.match(k)}
    data = {"week": week, "updated": now.isoformat(timespec="minutes"), "reels_with_data": len(rows), "tagged_reels": tagged_now, "score_mode": mode,
            "phase2": "on" if p2 else "off", "max_combination": max_k, "external": external,
            "niche": ({"sources_analysed": niche_agg["sources_analysed"], "counts": niche_agg["counts"], "top": niche_agg["top"]} if niche_agg else None),
            "rising": rising[:3], "niche_proposals": [{"field": p["field"], "value": p["value"], "text": p["proposal"]} for p in proposals],
            "patterns": dict(list(patterns.items())[:60]), "experiments": active, "blueprint": bp}
    _assert_enum_only(data)
    write_state(root, OUT_PATTERNS, json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    hist["own"] = hist["own"][-adv.HISTORY_WEEKS:]
    write_state(root, OUT_HISTORY, json.dumps(hist, indent=1, ensure_ascii=False) + "\n")
    try:
        import notebooklm  # noqa: PLC0415
        notebooklm.write_pack(root, now, rows, scores, hits, data, why_no_hits=external["status"])
    except Exception as e:
        return f"written (notebooklm pack skipped: {type(e).__name__})"
    return "written"


def _assert_enum_only(data: dict) -> None:
    """Zero-leak guard: pattern keys must be genome keys; the niche counts must be genome values; everything else is a number or a fixed word."""
    for k in data.get("patterns", {}):
        if not KEY_RE.match(k):
            raise ValueError("a pattern key is not a genome key")
    for f, c in ((data.get("niche") or {}).get("counts") or {}).items():
        allowed = set(genome.ENUMS.get(f, ())) | {"none", "other", "unknown"} | set(pan.LENGTH_BUCKETS)
        if f not in genome.ENUMS and f != "length_bucket":
            raise ValueError("unknown niche field")
        if not set(c) <= allowed:
            raise ValueError("a niche value is not an enum value")


# ---------------------------------------------------------------- the brief for status/daily.md
def brief(root: Path = ROOT) -> list[str]:
    data = _rd(root, OUT_PATTERNS, {})
    rows = sorted(own_rows(root), key=lambda r: r["views_per_day"] + 20 * r["reactions_per_day"])
    pats = data.get("patterns") or {}
    bottom = []
    for r in rows[:2]:
        score = round(r["views_per_day"], 1)
        part = "no tag data yet"
        if isinstance(r.get("hook_score"), (int, float)) and r["hook_score"] < 45:
            part = "the first line (hook score is low)"
        else:
            worst = sorted(((pats[k]["lift"], k) for k in (f"{f}={v}" for f, v in r["tags"].items()) if k in pats and pats[k].get("lift") is not None))
            if worst:
                part = worst[0][1]
        bottom.append({"slug": r["slug"], "score": score, "part": part})
    return adv.brief_lines(data, bottom if len(rows) > 2 else [])


if __name__ == "__main__":
    print("pattern engine:", run(force="--force" in sys.argv))
