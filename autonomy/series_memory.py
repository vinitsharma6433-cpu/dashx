"""DASHX Autonomy, Phase 5: series and variety memory. Standard library only. Makes NO model call.

What it keeps (autonomy/memory.json, rebuilt from the story bank + the poster queue, so nothing can drift):
  - SERIES STATE for every series in the bank (Bruno Files ...): each episode (posted / queued / waiting), the next episode number, the
    PROMISE (the last spoken line of the latest episode) that the next episode must PAY OFF, and the older episodes it can call back to.
  - LAST 14 DAYS: the openings, hooks, endings and closing lines of the reels posted or queued in the last 14 days, so new stories and
    the daily pick do not repeat them.

What it does with it:
  1. prompt_text(): a short block for the story writer prompt (series promise/payoff/callback + "do not repeat these"). Same single
     Gemini call as before, only a longer prompt.
  2. in_order(): EPISODE ORDER. Among the stories the factory could make next, a series episode waits while a LOWER episode of the same
     series is also ready. A lower episode that fails the quality checks never blocks the next one (no dead end).
  3. penalty(): a soft rank penalty for a story whose opening, hook or ending repeats the last 14 days. It never rejects a story.
Every function is fail-open: on any error the factory and the writer behave exactly as before.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
ROOT = Path(__file__).resolve().parent.parent
IST = timedelta(hours=5, minutes=30)
WINDOW_DAYS = 14
MAX_PROMPT_CHARS = 900
PENALTY_MAX = 12


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")


def _words(s: str) -> set[str]:
    return {w for w in re.findall(r"[\wऀ-ॿ]+", (s or "").lower()) if len(w) > 1}


def similar(a: str, b: str) -> float:
    """Word overlap 0..1 (Jaccard). 1 = same words."""
    x, y = _words(a), _words(b)
    return len(x & y) / len(x | y) if x and y else 0.0


# ---------------------------------------------------------------- read the bank
def parse_bank(text: str) -> list[dict]:
    """The story blocks in file order: titles, series, ep, hook, ending, opening line, closing line."""
    out = []
    for blk in re.split(r"\n(?=## )", text or ""):
        if not blk.startswith("## "):
            continue
        try:
            head = blk.splitlines()[0][3:]
            en, _, hi = head.partition("|")
            rows = [ln for ln in blk.splitlines() if ln.startswith("- ") and ln.count("|") == 4]
            lines = []
            for r in rows:
                for part in r.split("|", 4)[-1].split("//"):
                    lines.append(part.split(":", 1)[-1].strip())
            f = lambda k: (re.search(rf"^{k}:[ \t]*(.*)$", blk, re.M) or [None, ""])[1].strip()   # noqa: E731
            ep = f("ep")
            out.append({"title_en": en.strip(), "title_hi": hi.strip(), "series": f("series"), "ep": int(ep) if ep.isdigit() else 0,
                        "hook": f("hook"), "ending": f("ending"), "opening": lines[0] if lines else "", "closing": lines[-1] if lines else "",
                        "plot": f("plot")})
        except Exception:
            continue
    return out


def _posts(queue_text: str) -> list[dict]:
    try:
        return json.loads(queue_text).get("posts", [])
    except Exception:
        return []


# ---------------------------------------------------------------- build memory.json
def build(bank_text: str, queue_text: str, now: datetime) -> dict:
    stories = parse_bank(bank_text)
    posts = _posts(queue_text)
    status: dict[str, str] = {}            # slug of title -> posted / queued
    recent_slugs: set[str] = set()
    for p in posts:
        try:
            due = datetime.fromisoformat(p["when"])
        except Exception:
            continue
        s = slug(p.get("title", "").replace(" DASHX", ""))
        status[s] = "posted" if due <= now else "queued"
        if now - timedelta(days=WINDOW_DAYS) <= due:
            recent_slugs.add(s)
    series: dict[str, dict] = {}
    for st in stories:
        if not st["series"]:
            continue
        s = series.setdefault(st["series"], {"episodes": []})
        s["episodes"].append({"ep": st["ep"], "title_en": st["title_en"], "title_hi": st["title_hi"], "status": status.get(slug(st["title_en"]), "waiting"),
                              "last_line": st["closing"], "ending": st["ending"]})
    for name, s in series.items():
        eps = sorted(s["episodes"], key=lambda e: e["ep"])
        s["episodes"] = eps
        done = [e for e in eps if e["status"] != "waiting"]
        latest = max(done, key=lambda e: e["ep"]) if done else None
        s["last_ep"] = latest["ep"] if latest else 0
        s["next_ep"] = (max(e["ep"] for e in eps) + 1) if eps else 1            # the NEXT NEW episode to write
        s["promise"] = latest["last_line"] if latest else ""
        s["promise_from"] = latest["title_en"] if latest else ""
        s["callback_candidates"] = [e["title_en"] for e in done][-3:]
        waiting = [e for e in eps if e["status"] == "waiting"]
        s["play_next"] = waiting[0]["title_en"] if waiting else ""            # the lowest waiting episode goes out first
    recent = [st for st in stories if slug(st["title_en"]) in recent_slugs]
    mem = {"updated": now.isoformat(timespec="minutes"), "window_days": WINDOW_DAYS, "series": series,
           "recent": {"titles": [st["title_en"] for st in recent], "openings": [st["opening"] for st in recent if st["opening"]],
                      "hooks": [st["hook"] for st in recent if st["hook"]], "endings": [st["ending"] for st in recent if st["ending"]],
                      "closings": [st["closing"] for st in recent if st["closing"]]}}
    return mem


# ---------------------------------------------------------------- use it
def load(root: Path | None = None) -> dict:
    try:
        return json.loads(((root or ROOT) / "autonomy" / "memory.json").read_text(encoding="utf-8"))
    except Exception:
        return {}


def prompt_text(fmt: str = "normal", root: Path | None = None) -> str:
    """Block for the writer prompt. "" when there is nothing to say or on any error."""
    try:
        m = load(root)
        parts = []
        if fmt == "series":
            for name, s in m.get("series", {}).items():
                if s.get("promise"):
                    cb = "; ".join(s.get("callback_candidates", [])[:2])
                    parts.append(f"SERIES MEMORY ({name}): the last episode ('{s['promise_from']}') ended on this promise: \"{s['promise']}\". "
                                 f"Episode {s['next_ep']} must PAY IT OFF in its first two spoken lines, then end on a NEW open question. "
                                 f"Include ONE small callback to an earlier episode ({cb}): refer to a thing or joke from it, not its title.")
        r = m.get("recent", {})
        if r.get("openings") or r.get("hooks"):
            def lst(k, n):
                return " | ".join(x for x in r.get(k, [])[-n:])
            parts.append("LAST 14 DAYS (do NOT repeat these openings, hooks or endings, and do not reuse their jokes): "
                         f"openings: {lst('openings', 5)}; hooks: {lst('hooks', 5)}; endings: {lst('endings', 5)}.")
        text = "\n".join(parts)
        if not text:
            return ""
        return (text[: MAX_PROMPT_CHARS - 1] + "…" if len(text) > MAX_PROMPT_CHARS else text) + "\n\n"
    except Exception:
        return ""


def in_order(cands: list[tuple], series_idx: int = 4, ep_idx: int = 5) -> list[tuple]:
    """EPISODE ORDER among the READY candidates: per series only the lowest episode stays. Never empties the list. Fail-open."""
    try:
        low: dict[str, int] = {}
        for c in cands:
            s, ep = c[series_idx], _int(c[ep_idx])
            if s and ep is not None:
                low[s] = ep if s not in low else min(low[s], ep)
        keep = [c for c in cands if not c[series_idx] or _int(c[ep_idx]) is None or _int(c[ep_idx]) == low[c[series_idx]]]
        return keep or cands
    except Exception:
        return cands


def _int(v):
    try:
        return int(v)
    except Exception:
        return None


def penalty(opening: str, hook: str, ending: str, root: Path | None = None) -> int:
    """0..PENALTY_MAX: how much the last 14 days already used this opening, hook or ending. A soft rank penalty, never a rejection."""
    try:
        r = load(root).get("recent", {})
        pts = 0
        for text, key, w in ((opening, "openings", 6), (hook, "hooks", 4), (ending, "endings", 4)):
            if text and any(similar(text, old) >= 0.6 for old in r.get(key, [])):
                pts += w
        return min(pts, PENALTY_MAX)
    except Exception:
        return 0


def write(root: Path, now: datetime | None = None) -> dict:
    """Rebuild autonomy/memory.json (a machine-notes file). Only this file is written."""
    import guard  # noqa: PLC0415
    now = (now or datetime.now(guard.IST)).astimezone(guard.IST)
    if guard.halted("all", root):
        return {}
    if guard.classify("autonomy/memory.json", guard.load_rules())[0] != "state":
        raise PermissionError("autonomy/memory.json is not a machine-notes file")
    bank = root / "reelfactory" / "stories" / "dialogue_bank.md"
    queue = root / "poster" / "queue.json"
    mem = build(bank.read_text(encoding="utf-8") if bank.exists() else "", queue.read_text(encoding="utf-8") if queue.exists() else "{}", now)
    (root / "autonomy").mkdir(parents=True, exist_ok=True)
    (root / "autonomy" / "memory.json").write_text(json.dumps(mem, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    return mem


if __name__ == "__main__":
    import guard
    try:
        m = write(ROOT)
    except guard.RulesTampered as e:
        print(f"::error::RULES TAMPERED ({e}). Series memory stopped.")
        sys.exit(1)
    for name, s in m.get("series", {}).items():
        print(f"{name}: last ep {s['last_ep']}, next new ep {s['next_ep']}, play next: {s['play_next'] or '-'}")
    print("recent (14 days):", len(m.get("recent", {}).get("titles", [])), "stories")
