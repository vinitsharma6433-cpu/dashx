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


def build(s: alerts.Signals) -> str:
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
    if problems:
        L += ["", "### Open alerts (also in the GitHub issue DASHX ALERT)", *(f"- {p.title}" for p in problems)]
    return "\n".join(L) + "\n"


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


def run(root: Path = ROOT, now: datetime | None = None) -> str:
    s = alerts.load_signals(root, now)
    if guard.halted("all", root):
        print(f"{guard.halted('all', root)} is on: report does nothing")
        return "halted"
    section = build(s)
    day = s.now.strftime("%Y-%m-%d")
    p = root / OUT
    p.parent.mkdir(parents=True, exist_ok=True)
    assert OUT in alerts.ALLOWED_OUT
    p.write_text(merge_into_file(p.read_text(encoding="utf-8") if p.exists() else "", section, day), encoding="utf-8", newline="\n")
    return day


if __name__ == "__main__":
    print("daily report written for", run())
