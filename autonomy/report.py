"""DASHX Autonomy, Phase 7: the daily report (status/daily.md, written once a day around 21:00 IST). Standard library only, free.

Plain facts from files the machine already keeps: reels posted today on the 3 networks, failures, fixes, self-changes made and reverted,
the trends used, what the learning loop found, story-bank days left, Gemini quota used, and the autonomy status. The newest report is on
top; the last 14 days are kept. Running it twice on the same day replaces that day's section. Error texts and secrets are never copied.
"""
from __future__ import annotations

import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import alerts  # noqa: E402
import guard  # noqa: E402
import ladder  # noqa: E402

ROOT = guard.ROOT
IST = guard.IST
OUT = "status/daily.md"
KEEP_DAYS = 14
REELS_PER_DAY = 2
NETS = ("youtube", "instagram", "facebook")


def _cell(p: dict, net: str, now: datetime) -> str:
    if net not in p.get("networks", []):
        return "-"
    r = p.get("results", {}).get(net)
    due = datetime.fromisoformat(p["when"])
    if not r:
        return "waiting" if due > now else "not posted"
    if r.get("skipped_late"):
        return "skipped (too late)"
    if r.get("ok"):
        return "scheduled" if (r.get("scheduled") and due > now) else "posted"
    return f"FAILED ({alerts_class(str(r.get('error', '')))})"


def alerts_class(err: str) -> str:
    e = err.lower()
    for key in ("token", "timeout", "permission", "quota", "processing", "not public", "secrets missing"):
        if key in e:
            return key
    return "other"


def today_lines(log_text: str, day: str, kinds: tuple[str, ...], col: int = 1) -> list[str]:
    out = []
    for ln in log_text.splitlines():
        parts = ln.split(" | ")
        if ln.startswith(f"- {day}") and len(parts) >= 4 and parts[col] in kinds:
            out.append(f"{parts[0].split()[2]}: {parts[2]} - {parts[3][:140]}" + (f" ({parts[4][:60]})" if len(parts) > 4 and parts[4] else ""))
    return out


def build(s: alerts.Signals, root: Path = ROOT) -> str:
    day = s.now.strftime("%Y-%m-%d")
    problems = alerts.detect(s)
    st = alerts.status_json(s, problems)
    L: list[str] = [f"## {day}", f"<!-- day: {day} -->", f"Report time: {s.now.strftime('%H:%M')} IST. Autonomy status: **{st['level'].upper()}**"
                    + (f" ({'; '.join(st['reasons'])})" if st["reasons"] else ""), ""]
    # reels today
    todays = sorted([p for p in s.posts if p.get("when", "")[:10] == day], key=lambda p: p["when"])
    L += ["### Reels today (3 networks)"]
    if todays:
        L += ["| Reel | Slot | YouTube | Instagram | Facebook |", "|---|---|---|---|---|"]
        for p in todays:
            L.append(f"| {p.get('title', '?').replace(' DASHX', '')} | {p['when'][11:16]} | " + " | ".join(_cell(p, n, s.now) for n in NETS) + " |")
    else:
        L.append("No reel was due today.")
    late = lambda p, c: c == "not posted" and s.now - datetime.fromisoformat(p["when"]) > timedelta(minutes=30)      # noqa: E731  due more than 30 min ago and still nothing
    fails = [f"{p.get('title', '?').replace(' DASHX', '')} / {n}: {_cell(p, n, s.now)}" + (" (late, more than 30 min after the slot)" if late(p, _cell(p, n, s.now)) else "")
             for p in todays for n in NETS if _cell(p, n, s.now).startswith("FAILED") or late(p, _cell(p, n, s.now))]
    L += ["", "### Failures", *(f"- {x}" for x in fails)] if fails else ["", "### Failures", "None today."]
    for l in today_lines(s.log_text, day, ("report",)):
        L.append(f"- (heal report) {l}")
    L += [""] + postmortem(s, day, todays, problems)
    # fixes + self-changes
    fixes = today_lines(s.log_text, day, ("fix",))
    L += ["", "### Fixes the machine made", *(f"- {x}" for x in fixes)] if fixes else ["", "### Fixes the machine made", "None needed."]
    imp = today_lines(s.log_text, day, ("improve",), col=1)
    L += ["", "### Self-changes (made / reverted)", *(f"- {x}" for x in imp)] if imp else ["", "### Self-changes (made / reverted)", "None today."]
    if s.watch.get("status") == "watching":
        L.append(f"- Now watching: {s.watch.get('idea', '')} (merged {s.watch.get('merged_at', '')[:16]})")
    # trends
    tops = [t for t in s.trends.get("topics", []) if str(t.get("expires", "")) >= day][:2]
    L += ["", "### Trends used in the story prompt", *(f"- {t['topic']}: {t.get('story_angle', '')[:140]}" for t in tops)] if tops else ["", "### Trends used in the story prompt", "None (no fresh trend file)."]
    # learning
    lr = s.learning
    L += ["", "### What the learning loop found"]
    if lr:
        L.append(f"- Reels with data: {lr.get('reels_with_data', 0)} (need {lr.get('need', 5)}). Steering: {'ON' if lr.get('enough_data') else 'OFF (not enough data yet)'}.")
        for dim in ("format", "hook_type"):
            g = {k: v for k, v in lr.get("groups", {}).get(dim, {}).items() if v.get("avg") is not None}
            if g:
                best = max(g, key=lambda k: g[k]["avg"])
                L.append(f"- Best {dim}: {best} (average score {g[best]['avg']}, {g[best]['n']} reels).")
        for k, v in lr.get("availability", {}).items():
            L.append(f"- Data source {k}: {str(v)[:110]}")
        if any(str(v).startswith("DENIED") for v in lr.get("availability", {}).values()):
            L.append("- NEEDS YOUR DECISION: a stats source was denied. The machine will not ask for a new permission by itself.")
    else:
        L.append("The learning loop has not run yet.")
    # bank and quota
    m = re.search(r"(\d+) stories left", s.refill_daily)
    left = int(m.group(1)) if m else None
    qd = alerts_quota_day(s.now)
    calls = int(s.usage.get("calls", 0)) if s.usage.get("day") == qd else 0
    L += ["", "### Story bank and Gemini quota",
          f"- Stories left: {left if left is not None else 'unknown'}" + (f" = about {left // REELS_PER_DAY} days at {REELS_PER_DAY} reels a day" if left is not None else ""),
          f"- Gemini calls used in this quota day: {calls}/{int(s.usage.get('cap', 12) or 12)}"]
    L += [""] + ladder.report_lines(s.ladder, s.now)
    try:
        import pattern_engine  # noqa: PLC0415
        L += [""] + pattern_engine.brief(root)
    except Exception:
        pass
    g = s.usage.get("grade") if isinstance(s.usage.get("grade"), dict) else {}
    if g:
        low = [t for t, r in g.items() if not r.get("ok")]
        L.append(f"- Editor grade of the hand-imported stories: {len(g)} graded so far, {len(low)} below the bar"
                 + (f" ({', '.join(low[:6])}{'...' if len(low) > 6 else ''}). They stay in the bank until the owner decides." if low else "."))
    if left is not None and left < alerts.LOW_STOCK:
        L.append(f"- **{'CRITICAL' if left < alerts.CRITICAL_STOCK else 'LOW'} STOCK**: {left} stories left (alert below {alerts.LOW_STOCK}, loud alert below {alerts.CRITICAL_STOCK}). Posting and the schedule are not changed.")
    if problems:
        L += ["", "### Open alerts (also in the GitHub issue DASHX ALERT)", *(f"- {p.title}" for p in problems)]
    return "\n".join(L) + "\n"


CAUSE = {   # failure class -> (likely cause, what to do). Plain words, no error text is ever copied.
    "token": ("a login token expired or lost a permission", "only the owner can renew it (the DASHX ALERT issue has the steps)"),
    "permission": ("the platform refused a permission", "only the owner can check the app permissions"),
    "timeout": ("the network or the platform was slow", "the machine retries once by itself; nothing to do if the next reel is fine"),
    "quota": ("a daily platform limit was reached", "it resets by itself the next day"),
    "processing": ("the platform could not process the video in time", "the machine retries once; check the reel on that app if it repeats"),
    "not public": ("the video was not public yet when the next step ran", "usually fixes itself on the next poster check"),
    "secrets missing": ("a secret is missing in GitHub", "only the owner can add it"),
    "other": ("an unknown error", "watch tomorrow's report; the DASHX ALERT issue opens if it needs the owner"),
}


def postmortem(s: alerts.Signals, day: str, todays: list[dict], problems: list) -> list[str]:
    """One short post-mortem per thing that went wrong today: what happened, the likely cause, what the machine did, what is left for the owner."""
    out = ["### Post-mortem"]
    items = []
    for p in todays:
        for n in NETS:
            c = _cell(p, n, s.now)
            title = p.get("title", "?").replace(" DASHX", "")
            if c.startswith("FAILED"):
                cls = re.search(r"\((.*)\)", c).group(1)
                cause, todo = CAUSE.get(cls, CAUSE["other"])
                items.append(f"- **{title} / {n}**: failed. Likely cause: {cause}. Next: {todo}.")
            elif c == "not posted" and s.now - datetime.fromisoformat(p["when"]) > timedelta(minutes=30):
                items.append(f"- **{title} / {n}**: not posted 30 minutes after the slot. Likely cause: the poster run was late or stopped. "
                             "The heal check restarts the poster by itself; the Trust Ladder drops a step if the whole slot is missed.")
    for ln in s.log_text.splitlines():
        if ln.startswith(f"- {day}") and ("| improve | auto_revert |" in ln or "| ladder | drop |" in ln or "| fix |" in ln):
            parts = ln.split(" | ")
            what = {"auto_revert": "a self-change was undone after it hurt a reel", "drop": "the Trust Ladder dropped one step"}.get(parts[2] if len(parts) > 2 else "", "the machine fixed something by itself")
            items.append(f"- {ln[13:18]} IST: {what} ({(parts[3] if len(parts) > 3 else '')[:120]}).")
    for p in problems:
        items.append(f"- Needs the owner: {p.title} (see the DASHX ALERT issue).")
    return out + (items or ["Nothing went wrong today."])


def alerts_quota_day(now: datetime) -> str:
    from datetime import timezone
    return ((now.astimezone(timezone.utc)) - timedelta(hours=8)).date().isoformat()


def merge_into_file(existing: str, section: str, day: str, keep_days: int = KEEP_DAYS) -> str:
    """New report on top; the same day replaced; only the last `keep_days` days kept."""
    head = "# DASHX daily report\nWritten by the machine every day around 21:00 IST (autonomy/report.py). Newest first.\n\n"
    parts = re.split(r"(?m)^(?=## \d{4}-\d\d-\d\d$)", existing or "")
    old = [p for p in parts if re.match(r"## \d{4}-\d\d-\d\d\n", p) and not p.startswith(f"## {day}\n")]
    days = [section] + old
    days = sorted(days, key=lambda p: p[3:13], reverse=True)[:keep_days]
    return head + "\n".join(d.rstrip() + "\n" for d in days)


LATE_UNTIL_HOUR = 12        # GitHub runs the 21:00 IST cron hours late; a run before noon IST writes YESTERDAY's report


def report_time(now: datetime) -> datetime:
    """The moment the report describes. 21:00 or later: today. Before noon: yesterday at 23:59 (a late run of last night's report). Else: now."""
    now = now.astimezone(IST)
    if now.hour < LATE_UNTIL_HOUR:
        return (now - timedelta(days=1)).replace(hour=23, minute=59, second=0, microsecond=0)
    return now


def due(root: Path, now: datetime) -> bool:
    """True when a report should be written now: 21:00 IST or later and today's section is missing, or a morning run and yesterday's is missing."""
    now = now.astimezone(IST)
    if LATE_UNTIL_HOUR <= now.hour < 21:
        return False
    day = report_time(now).strftime("%Y-%m-%d")
    p = root / OUT
    return not (p.exists() and f"<!-- day: {day} -->" in p.read_text(encoding="utf-8"))


def run(root: Path = ROOT, now: datetime | None = None) -> str:
    now = (now or datetime.now(IST)).astimezone(IST)
    s = alerts.load_signals(root, report_time(now))
    if guard.halted("all", root):
        print(f"{guard.halted('all', root)} is on: report does nothing")
        return "halted"
    section = build(s, root)
    day = s.now.strftime("%Y-%m-%d")
    p = root / OUT
    p.parent.mkdir(parents=True, exist_ok=True)
    assert OUT in alerts.ALLOWED_OUT
    p.write_text(merge_into_file(p.read_text(encoding="utf-8") if p.exists() else "", section, day), encoding="utf-8", newline="\n")
    try:                                              # the weekly Pattern Engine decides by itself if it is due; it never breaks the report
        import pattern_engine  # noqa: PLC0415
        print("pattern_engine:", pattern_engine.run(root, now))
    except Exception as e:
        print(f"pattern_engine: skipped ({type(e).__name__})")
    return day


if __name__ == "__main__":
    print("daily report written for", run())
