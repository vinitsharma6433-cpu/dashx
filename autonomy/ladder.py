"""DASHX Autonomy: the Trust Ladder (the roadmap is autonomy/TRUST_LADDER.md, owner-approved, protected in RULES.json). Standard library only.

The machine is on ONE step at a time. It moves UP only when that step's written gate is met (and writes the evidence to autonomy/log.md).
It drops ONE step on a missed slot, a Meta warning or a harmful revert, and raises a DASHX ALERT (alerts.py reads the state written here).
Step 4 (Scout auto-apply) is NEVER entered by the machine: it needs the owner's yes in chat. Step 1 is the floor.

State lives in autonomy/status.json under the key "ladder" (an existing machine-notes file). It is checked on every read: a step outside 1..3,
or a history that does not match the step, or a TRUST_LADDER.md that no longer matches the hash sealed in RULES.json, means "step 1, frozen".
What each step switches on is read by the other modules through current_step(): self-improvement (improve.py) needs step >= 2.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import guard  # noqa: E402

ROOT = guard.ROOT
IST = guard.IST
LADDER_FILE = "autonomy/TRUST_LADDER.md"
STATUS = "autonomy/status.json"
LOG = "autonomy/log.md"
MISSED_AFTER_MIN = 90                 # a slot with no successful post 90 minutes after its time is a missed slot
CLEAN_AFTER_MIN = 30
NEED_CLEAN_REELS = 2
DAYS = {2: 7, 3: 30}                  # days needed on step 2 (to reach 3) and on step 3 (to be ready for step 4)
FLAG_RE = re.compile(r"flagged|restricted|suspend|disabled|checkpoint|action blocked|spam|violat|community guidelines|account (is )?(locked|limited)|warning", re.I)
NAMES = {
    1: "Step 1 - Watch (watchdog, self-heal, daily report, alert issue; self-improvement OFF)",
    2: "Step 2 - Careful self-improvement (max 1 change a day, 3 files, allowed files only, auto-revert watch)",
    3: "Step 3 - Wider self-improvement (same allowed files and blocked windows)",
}


# ---------------------------------------------------------------- is the ladder file still the one the owner sealed?
def ladder_file_ok(root: Path = ROOT, rules: dict | None = None) -> tuple[bool, str]:
    try:
        rules = rules or guard.load_rules()
        want = rules["protected_files"][LADDER_FILE]
        have = guard.digest(root / LADDER_FILE)
    except Exception as e:
        return False, f"cannot verify {LADDER_FILE}: {type(e).__name__}"
    return (have == want), ("" if have == want else f"{LADDER_FILE} does not match the hash sealed in RULES.json")


# ---------------------------------------------------------------- state
def new_state() -> dict:
    return {"step": 1, "step_since": None, "first_run": None, "history": [], "handled": [], "drop_alert_until": None, "last_drop": "",
            "owner_ready": False, "progress": "", "blocker": "", "evidence": ""}


def valid(st) -> bool:
    try:
        if not isinstance(st, dict) or st.get("step") not in (1, 2, 3):
            return False
        h = st.get("history", [])
        if not isinstance(h, list):
            return False
        last = h[-1]["to"] if h else 1
        return last == st["step"]
    except Exception:
        return False


def load(root: Path = ROOT) -> dict:
    try:
        st = json.loads((root / STATUS).read_text(encoding="utf-8")).get("ladder")
    except Exception:
        st = None
    if st is None:
        return new_state()
    return st if valid(st) else {**new_state(), "invalid": True}


def current_step(root: Path = ROOT) -> int:
    """The step the machine is allowed to act on. 1 (the floor) whenever anything is unclear, broken or stopped."""
    try:
        if guard.halted("all", root):
            return 1
        ok, _ = ladder_file_ok(root)
        st = load(root)
        return st["step"] if ok and not st.get("invalid") else 1
    except Exception:
        return 1


def _t(s):
    return datetime.fromisoformat(s) if s else None


# ---------------------------------------------------------------- facts from the queue
def _due(p: dict):
    try:
        return datetime.fromisoformat(p["when"])
    except Exception:
        return None


def reel_state(p: dict, now: datetime) -> str:
    """'clean' | 'failed' | 'missed' | 'open' for a reel that is due."""
    due = _due(p)
    if due is None or due > now:
        return "open"
    res, nets = p.get("results", {}) or {}, p.get("networks", []) or []
    if any(r.get("ok") is False and not r.get("skipped_late") for r in res.values()):
        return "failed"
    if nets and not any(r.get("ok") for r in res.values()):
        return "missed" if now - due >= timedelta(minutes=MISSED_AFTER_MIN) else "open"
    if all((res.get(n) or {}).get("ok") for n in nets) and now - due >= timedelta(minutes=CLEAN_AFTER_MIN):
        return "clean"
    return "open"


def find_events(st: dict, posts: list[dict], log_text: str, now: datetime) -> list[tuple[str, str, str]]:
    """(kind, key, short text) for every missed slot, Meta warning and harmful revert on this step that was not handled yet."""
    since, seen, out = _t(st.get("step_since")), set(st.get("handled", [])), []
    if since is None:
        return out
    for p in posts:
        due = _due(p)
        if due is None or due < since or due > now:
            continue
        title = str(p.get("title", "?")).replace(" DASHX", "")
        if reel_state(p, now) == "missed" and f"missed:{p['when']}" not in seen:
            out.append(("missed slot", f"missed:{p['when']}", f"{title} ({p['when'][:16]}) was not posted on any network"))
        for net in ("facebook", "instagram"):
            err = str(((p.get("results") or {}).get(net) or {}).get("error", ""))
            if err and FLAG_RE.search(err) and f"meta:{p['when']}:{net}" not in seen:
                out.append(("Meta warning", f"meta:{p['when']}:{net}", f"{title} on {net}: the answer looked like a warning or restriction"))
    for ln in log_text.splitlines():
        if ln.startswith("- ") and "| improve | auto_revert |" in ln:
            try:
                t = datetime.strptime(ln[2:18], "%Y-%m-%d %H:%M").replace(tzinfo=IST)
            except ValueError:
                continue
            if t >= since and f"revert:{ln[2:18]}" not in seen:
                out.append(("harmful revert", f"revert:{ln[2:18]}", f"a self-change was reverted after it hurt a reel ({ln[2:18]})"))
    return out


def clean_progress(st: dict, posts: list[dict], now: datetime) -> tuple[int, str, str]:
    """Step 1 gate: clean reels after the first run; a failure or a duplicate after it restarts the count."""
    fr = _t(st.get("first_run"))
    if fr is None:
        return 0, "", "the first autonomy run has not happened yet"
    after = sorted([p for p in posts if _due(p) and fr <= _due(p) <= now], key=_due)
    titles: dict[str, int] = {}
    for p in after:
        titles[p.get("title", "")] = titles.get(p.get("title", ""), 0) + 1
    last_bad, why = None, ""
    for p in after:
        s = reel_state(p, now)
        if s in ("failed", "missed") or titles.get(p.get("title", ""), 0) > 1:
            last_bad, why = _due(p), f"a failure or duplicate after the first run ({str(p.get('title', '?')).replace(' DASHX', '')}): the clean count restarted"
    good = [p for p in after if reel_state(p, now) == "clean" and (last_bad is None or _due(p) > last_bad)]
    return len(good), ", ".join(str(p.get("title", "?")).replace(" DASHX", "") for p in good[:NEED_CLEAN_REELS]), why


def views_not_falling(learning: dict):
    """True / False / None (not measurable). Uses the learning loop's own numbers only; missing data never counts as 'fine'."""
    try:
        v = learning.get("views_trend")
        return None if v is None else bool(v >= 0)
    except Exception:
        return None


# ---------------------------------------------------------------- one evaluation (pure except for what it returns)
def evaluate(st: dict, posts: list[dict], log_text: str, learning: dict, now: datetime, rules_ok: bool, ladder_ok: bool, ladder_why: str = "") -> tuple[dict, list[str]]:
    """Returns (new state, log lines). Moves at most ONE step, up or down, per evaluation."""
    st = json.loads(json.dumps(st if valid(st) else new_state()))
    lines: list[str] = []

    def log(kind, what, why, extra=""):
        lines.append(f"- {now.strftime('%Y-%m-%d %H:%M')} IST | ladder | {kind} | {what} | {why}" + (f" | {extra}" if extra else ""))

    if not rules_ok or not ladder_ok:
        st["blocker"] = "frozen at step 1: " + (ladder_why or "the rule file does not verify")
        st["progress"] = "frozen"
        if st["step"] != 1:
            st["history"].append({"at": now.isoformat(timespec="minutes"), "from": st["step"], "to": 1, "why": "frozen: rule or ladder file not verified"})
            log("frozen", f"{st['step']}->1", "rule file or TRUST_LADDER.md did not verify; everything stays at step 1")
            st["step"], st["step_since"] = 1, now.isoformat(timespec="minutes")
        return st, lines
    if not st.get("first_run"):
        st["first_run"], st["step_since"] = now.isoformat(timespec="minutes"), now.isoformat(timespec="minutes")
        log("start", "step 1", "first autonomy run succeeded (rule file and ladder file verified)")
    events = find_events(st, posts, log_text, now)
    if events:
        old = st["step"]
        new = max(1, old - 1)
        what = "; ".join(f"{k}: {t}" for k, _, t in events)[:300]
        st["handled"] = (st.get("handled", []) + [k for _, k, _ in events])[-60:]
        st["history"].append({"at": now.isoformat(timespec="minutes"), "from": old, "to": new, "why": what})
        st["step"], st["step_since"] = new, now.isoformat(timespec="minutes")
        st["drop_alert_until"], st["last_drop"], st["owner_ready"] = (now + timedelta(days=7)).isoformat(timespec="minutes"), what, False
        log("drop", f"{old}->{new}" if new != old else f"stays at {old}", what, "DASHX ALERT raised")
    else:
        st = _maybe_up(st, posts, learning, now, log)
    st["progress"], st["blocker"], st["evidence"] = _progress(st, posts, learning, now)
    return st, lines


def _progress(st: dict, posts: list[dict], learning: dict, now: datetime) -> tuple[str, str, str]:
    step = st["step"]
    if step == 1:
        n, ev, why = clean_progress(st, posts, now)
        return f"{n} of {NEED_CLEAN_REELS} clean reels after the first run", why, ev
    since = _t(st.get("step_since")) or now
    need = DAYS[step]
    days = max(0, (now - since).days)
    blocker = ""
    if step == 3 and days >= need:
        nf = views_not_falling(learning)
        blocker = "" if nf else ("reel views are not measurable yet (the learning loop has no views data)" if nf is None else "reel views are falling")
        if not blocker:
            blocker = "READY for step 4: it needs the owner's yes in chat (the machine never moves there by itself)"
    return f"{min(days, need)} of {need} days", blocker, ""


def _maybe_up(st: dict, posts: list[dict], learning: dict, now: datetime, log) -> dict:
    step = st["step"]
    if step == 1:
        n, ev, _ = clean_progress(st, posts, now)
        if n >= NEED_CLEAN_REELS:
            _up(st, now, log, f"first autonomy run succeeded and {n} reels posted cleanly after it (no new failure, no duplicate): {ev}")
    elif step == 2:
        days = (now - (_t(st.get("step_since")) or now)).days
        if days >= DAYS[2]:
            _up(st, now, log, f"{days} days on step 2 with zero harmful reverts, zero missed slots, zero Meta warnings")
    elif step == 3:
        days = (now - (_t(st.get("step_since")) or now)).days
        st["owner_ready"] = bool(days >= DAYS[3] and views_not_falling(learning))
    return st


def _up(st: dict, now: datetime, log, evidence: str) -> None:
    old = st["step"]
    st["step"], st["step_since"] = old + 1, now.isoformat(timespec="minutes")
    st["history"].append({"at": now.isoformat(timespec="minutes"), "from": old, "to": old + 1, "why": evidence[:300]})
    log("step_up", f"{old}->{old + 1}", evidence[:300])


# ---------------------------------------------------------------- the notes
def write_log(root: Path, lines: list[str]) -> None:
    if not lines:
        return
    if guard.classify(LOG, guard.load_rules())[0] != "state":
        raise PermissionError(f"{LOG} is not a machine-notes file")
    p = root / LOG
    p.parent.mkdir(parents=True, exist_ok=True)
    if not p.exists():
        p.write_text("# DASHX Autonomy log\nOne line per fix or report. Written by the machine.\n\n", encoding="utf-8", newline="\n")
    with open(p, "a", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")


def report_lines(st: dict, now: datetime) -> list[str]:
    """The Trust Ladder block of the daily report (status/daily.md)."""
    if not st or st.get("invalid"):
        return ["### Trust Ladder", "- State unreadable or invalid: the machine is held at step 1 until the next clean evaluation."]
    step = st.get("step", 1)
    target = {1: "Step 2", 2: "Step 3", 3: "Step 4 (owner's yes in chat)"}[step]
    out = ["### Trust Ladder", f"- Current: **{NAMES[step]}**",
           f"- Gate to {target}: {st.get('progress') or 'not evaluated yet'}"]
    if step == 1:
        out.append("- Gate rule: first autonomy run succeeded AND 2 reels posted cleanly after it (no new failure, no duplicate).")
    elif step == 2:
        out.append("- Gate rule: 7 days with zero harmful reverts and zero missed slots.")
    else:
        out.append("- Gate rule: 30 days, zero missed slots, zero Meta warnings, reel views not falling; then the owner says yes in chat.")
    out.append(f"- Blocker: {st.get('blocker') or 'none'}")
    if st.get("history"):
        h = st["history"][-1]
        out.append(f"- Last move: {h['from']} -> {h['to']} on {h['at'][:16]} ({h.get('why', '')[:140]})")
    until = _t(st.get("drop_alert_until"))
    if until and until > now:
        out.append(f"- DROPPED a step recently and an alert is open until {until.strftime('%Y-%m-%d')}: {st.get('last_drop', '')[:160]}")
    return out
