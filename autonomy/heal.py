"""DASHX Autonomy, Phase 2: self-healing. Standard library only (the comment backfill reuses poster.meta_comments, nothing else).

What it fixes by itself (every number comes from the sealed RULES.json, section `healing`):
  1. dead poster loop      -> re-dispatch the poster (at most 2 per hour)
  2. one failed network    -> retry that network ONCE (clears results.<net>), only when it is proven safe (no duplicate-post risk)
  3. missing comment       -> run the comment backfill for that one post (max 2 tries)
  4. failed Reel Factory   -> re-dispatch it ONCE per failed run
  5. low bank              -> trigger Story Refill, only inside the Gemini quota (cap - calls >= 4), once per quota day
Everything else is only REPORTED in autonomy/log.md. Every fix and every report is logged there.

It never edits RULES.json, guard.py, a workflow, poster logic or a kill switch. It only dispatches the three workflows listed in the
rules and only writes poster/queue.json (data) and autonomy/log.md. Kill switches (STOP_AUTONOMY / STOP_POSTER / STOP_QUEUE / STOP_REFILL) win.
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import guard  # noqa: E402

ROOT = guard.ROOT
IST = guard.IST
LOG = "autonomy/log.md"
QUEUE = "poster/queue.json"
WF = {"poster": "dashx-poster.yml", "factory": "dashx-reel-factory.yml", "refill": "dashx-story-refill.yml"}
ACTIVE = ("queued", "in_progress", "waiting", "pending", "requested")
META = ("facebook", "instagram")
MAX_META_TRIES = 3            # same number as poster/poster.py
LOOKAHEAD_H = 36              # poster uploads up to 36 h ahead
LATE_H = 48                   # poster never posts older than this
TOKEN_WORDS = re.compile(r"token|oauth|expired|permission|cannot call api|\b190\b|\b200\b|invalid|session", re.I)
NOTE_ID = {"facebook": "fb_video_id", "instagram": "ig_media_id"}


# ---------------------------------------------------------------- data
@dataclass
class Snap:
    now: datetime
    runs: dict[str, list[dict]]            # key (poster/factory/refill) -> runs, newest first: id,status,conclusion,event,created,updated
    posts: list[dict]
    bank_left: int | None
    usage: dict                            # refill_usage.json
    quota_day: str
    log_text: str = ""
    stops: dict[str, str | None] = field(default_factory=dict)   # scope -> kill switch name


@dataclass
class Action:
    kind: str                              # dispatch | edit_queue | backfill_comment | report
    name: str                              # poster_redispatch, network_retry, ...
    why: str
    workflow: str = ""
    inputs: dict = field(default_factory=dict)
    post_title: str = ""
    network: str = ""
    tag: str = ""                          # remembered in the log so a fix is never repeated (run id, quota day, ...)


# ---------------------------------------------------------------- helpers
def _dt(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(IST)


def _count_in_log(log: str, name: str, since: datetime) -> int:
    n = 0
    for ln in log.splitlines():
        m = re.match(r"- (\d{4}-\d\d-\d\d \d\d:\d\d) IST \| fix \| (\w+) \|", ln)
        if m and m.group(2) == name and datetime.strptime(m.group(1), "%Y-%m-%d %H:%M").replace(tzinfo=IST) >= since:
            n += 1
    return n


def _tagged(log: str, name: str, tag: str) -> bool:
    return any(f"| fix | {name} |" in ln and f"[{tag}]" in ln for ln in log.splitlines())


def _pending(p: dict, now: datetime) -> bool:
    """Work the poster still has to do for this post (not done, not too old, within its 36 h look-ahead)."""
    if p.get("status") == "done":
        return False
    due = datetime.fromisoformat(p["when"])
    if now - due > timedelta(hours=LATE_H) or due - now > timedelta(hours=LOOKAHEAD_H):
        return False
    res, notes = p.get("results", {}), p.get("notes", {})
    for n in p["networks"]:
        r = res.get(n, {})
        if r.get("skipped_late"):
            continue
        if not r.get("ok"):
            if n in META and r.get("tries", 0) >= MAX_META_TRIES:
                continue                        # the poster gave up on purpose (duplicate protection)
            return True
        if due <= now and ((n == "youtube" and r.get("scheduled") and not notes.get("yt_engaged"))
                           or (n == "facebook" and r.get("scheduled") and not notes.get("fb_engaged") and notes.get("fb_comment_tries", 0) < 5)):
            return True
    return False


def retry_safe(p: dict, net: str) -> tuple[bool, str]:
    """DUPLICATE-POST GUARD. A network may be retried only when there is NO sign it was posted. Otherwise refuse (report only)."""
    r = p.get("results", {}).get(net, {})
    notes = p.get("notes", {})
    if r.get("ok") or r.get("link"):
        return False, "already posted (result has ok/link)"
    if notes.get(NOTE_ID.get(net, "?")):
        return False, f"{NOTE_ID[net]} exists, the reel may be live"
    if net == "facebook" and notes.get("fb_status") and str(notes["fb_status"]).lower() not in ("unknown", "error", "failed"):
        return False, "Facebook reported a video state: it may be live"
    if notes.get(f"heal_retry_{net}"):
        return False, "already retried once by the machine"
    if r.get("skipped_late"):
        return False, "skipped as too old"
    if TOKEN_WORDS.search(str(r.get("error", ""))):
        return False, "token/permission problem: a retry cannot fix it, the owner must"
    return True, "no sign of a post"


def duplicates(posts: list[dict], now: datetime) -> list[str]:
    """Report-only checks (posts from the last 48 h or still waiting): two entries for one slot, one media file queued twice, one link used by two entries."""
    out, seen_slot, seen_media, seen_link = [], {}, {}, {}
    for p in posts:
        t = p.get("title", "?")
        try:
            if now - datetime.fromisoformat(p["when"]) > timedelta(hours=LATE_H):
                continue
        except Exception:
            continue
        slot = (p.get("when", "")[:16], tuple(sorted(p.get("networks", []))))
        if slot in seen_slot and slot[0]:
            out.append(f"two posts share one slot {slot[0]}: {seen_slot[slot]} and {t}")
        seen_slot.setdefault(slot, t)
        m = p.get("media")
        if m:
            if m in seen_media:
                out.append(f"same media queued twice: {seen_media[m]} and {t}")
            seen_media.setdefault(m, t)
        for n, r in p.get("results", {}).items():
            if r.get("link"):
                if r["link"] in seen_link and seen_link[r["link"]] != t:
                    out.append(f"one {n} link used by two posts: {seen_link[r['link']]} and {t}")
                seen_link.setdefault(r["link"], t)
    return out


# ---------------------------------------------------------------- the plan (pure: no network, no files)
def plan(s: Snap, rules: dict) -> list[Action]:
    H = rules["healing"]
    acts: list[Action] = []
    now = s.now
    posts = s.posts

    # 1. dead poster loop -> re-dispatch (max N per hour)
    pr = s.runs.get("poster", [])
    if not s.stops.get("poster") and any(_pending(p, now) for p in posts):
        if not any(r["status"] in ACTIVE for r in pr):
            last = pr[0]["updated"] if pr else None
            idle = (now - last) if last else timedelta(days=9)
            if idle >= timedelta(minutes=H["poster_idle_minutes"]):
                if _count_in_log(s.log_text, "poster_redispatch", now - timedelta(hours=1)) < H["poster_redispatch_per_hour"]:
                    acts.append(Action("dispatch", "poster_redispatch", f"no poster run active for {int(idle.total_seconds() // 60)} min and posts are waiting", WF["poster"]))
                else:
                    acts.append(Action("report", "poster_redispatch_limit", "poster loop is dead but the limit of 2 re-dispatches per hour is used up"))

    # 2. one failed network -> retry once; 3. missing comment -> backfill
    for p in posts:
        if p.get("status") == "done":
            continue
        due = datetime.fromisoformat(p["when"])
        res, notes = p.get("results", {}), p.get("notes", {})
        for net in META:
            r = res.get(net)
            if net not in p["networks"] or not r or r.get("ok") or r.get("tries", 0) < MAX_META_TRIES or r.get("skipped_late"):
                continue
            if now - due > timedelta(hours=H["retry_max_age_hours"]):
                acts.append(Action("report", "network_too_old", f"{p['title']}: {net} failed and is too old to retry", post_title=p["title"], network=net))
                continue
            ok, why = retry_safe(p, net)
            if ok and not s.stops.get("poster"):
                acts.append(Action("edit_queue", "network_retry", f"{p['title']}: {net} failed {r.get('tries')} times, {why}", post_title=p["title"], network=net))
            else:
                acts.append(Action("report", "network_failed", f"{p['title']}: {net} failed, NOT retried: {why}", post_title=p["title"], network=net))
    for p in posts:
        if not (p.get("comments") or p.get("comment")):
            continue
        if now - datetime.fromisoformat(p["when"]) > timedelta(hours=H["retry_max_age_hours"]):
            continue
        res, notes = p.get("results", {}), p.get("notes", {})
        for net, key, done_flag in (("instagram", "ig", None), ("facebook", "fb", "fb_engaged")):
            r = res.get(net, {})
            if net not in p["networks"] or not r.get("ok") or not notes.get(NOTE_ID[net]) or notes.get(f"{key}_comment") == ["ok"]:
                continue
            if done_flag and not (notes.get("fb_comment_tries", 0) >= 5 or notes.get(done_flag)):
                continue                      # the poster is still retrying the Facebook comment itself
            if done_flag and notes.get(done_flag) and notes.get(f"{key}_comment") is None:
                continue                      # nothing was ever attempted and the poster considers it done: leave it
            at = r.get("at") or p["when"]
            if now - _dt(at) < timedelta(minutes=H["comment_min_age_minutes"]) or datetime.fromisoformat(p["when"]) > now:
                continue                      # the reel may not be public yet
            if notes.get(f"heal_comment_{key}", 0) >= H["comment_retry_times"] or s.stops.get("poster"):
                continue
            acts.append(Action("backfill_comment", "comment_backfill", f"{p['title']}: no first comment on {net}", post_title=p["title"], network=net))

    # 4. failed Reel Factory -> re-dispatch ONCE per failed run
    fr = s.runs.get("factory", [])
    if fr and not s.stops.get("self_change") and not any(r["status"] in ACTIVE for r in fr):
        last = next((r for r in fr if r["status"] == "completed"), None)
        upcoming = [p for p in posts if p.get("status") != "done" and datetime.fromisoformat(p["when"]) > now]
        if (last and last["conclusion"] == "failure" and last["event"] == "schedule" and now - last["created"] < timedelta(hours=14)
                and not any(r["conclusion"] == "success" and r["created"] > last["created"] for r in fr) and len(upcoming) < 3):
            if not _tagged(s.log_text, "factory_redispatch", str(last["id"])):
                acts.append(Action("dispatch", "factory_redispatch", f"Reel Factory run {last['id']} failed and only {len(upcoming)} reel(s) are queued",
                                   WF["factory"], {"count": "2", "test_only": "false"}, tag=str(last["id"])))

    # 5. low bank -> Story Refill, only inside the Gemini quota, once per quota day
    left = (H["low_bank_stories"])
    if s.bank_left is not None and s.bank_left <= left and not s.stops.get("refill"):
        calls = int(s.usage.get("calls", 0)) if s.usage.get("day") == s.quota_day else 0
        cap = int(s.usage.get("cap", 12))
        rr = s.runs.get("refill", [])
        busy = any(r["status"] in ACTIVE for r in rr) or any(now - r["created"] < timedelta(hours=6) for r in rr)
        if cap - calls < H["refill_min_calls_left"]:
            acts.append(Action("report", "low_bank_no_quota", f"bank is low ({s.bank_left} stories) but Gemini quota is used ({calls}/{cap}); waiting for the reset"))
        elif not busy and not _tagged(s.log_text, "refill_dispatch", s.quota_day):
            acts.append(Action("dispatch", "refill_dispatch", f"bank is low ({s.bank_left} stories), Gemini calls {calls}/{cap}",
                               WF["refill"], {"target": "2", "max_calls": str(cap), "dry_run": "false"}, tag=s.quota_day))

    # duplicate guard + other things: report only
    for d in duplicates(posts, now):
        acts.append(Action("report", "duplicate_guard", d))
    for p in posts:
        for net, r in p.get("results", {}).items():
            if not r.get("ok") and not r.get("skipped_late") and TOKEN_WORDS.search(str(r.get("error", ""))) and p.get("status") != "done":
                acts.append(Action("report", "token_or_permission", f"{p['title']}: {net} error needs the owner: {str(r.get('error'))[:120]}", post_title=p["title"], network=net))
    if len(pr) >= 3 and all(r["status"] == "completed" and r["conclusion"] == "failure" for r in pr[:3]):
        acts.append(Action("report", "poster_runs_failing", "the last 3 poster runs failed"))
    return acts


# ---------------------------------------------------------------- GitHub (only the Actions API, with the job's own GITHUB_TOKEN)
class GitHub:
    def __init__(self, repo: str | None = None, token: str | None = None):
        self.repo = repo or os.environ.get("GITHUB_REPOSITORY", "")
        self._tok = token or os.environ.get("GITHUB_TOKEN", "")

    def _req(self, method: str, path: str, body: dict | None = None):
        req = urllib.request.Request(f"https://api.github.com/repos/{self.repo}{path}", method=method,
                                     data=json.dumps(body).encode() if body is not None else None,
                                     headers={"Authorization": f"Bearer {self._tok}", "Accept": "application/vnd.github+json", "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read()
            return json.loads(raw) if raw else {}

    def runs(self, workflow: str) -> list[dict]:
        j = self._req("GET", f"/actions/workflows/{workflow}/runs?per_page=10")
        return [{"id": r["id"], "status": r["status"], "conclusion": r.get("conclusion"), "event": r["event"],
                 "created": _dt(r["created_at"]), "updated": _dt(r["updated_at"])} for r in j.get("workflow_runs", [])]

    def dispatch(self, workflow: str, inputs: dict, ref: str = "main") -> None:
        self._req("POST", f"/actions/workflows/{workflow}/dispatches", {"ref": ref, "inputs": inputs})


# ---------------------------------------------------------------- collect + execute
def quota_day(now_utc: datetime | None = None) -> str:
    return ((now_utc or datetime.now(timezone.utc)) - timedelta(hours=8)).date().isoformat()


def _read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def collect(api, root: Path = ROOT, now: datetime | None = None) -> Snap:
    now = (now or datetime.now(IST)).astimezone(IST)
    runs = {}
    for k, f in WF.items():
        try:
            runs[k] = api.runs(f)
        except Exception as e:
            runs[k] = []
            print(f"::warning::could not read {f}: {type(e).__name__}")
    bank = None
    try:
        t = (root / "reelfactory/stories/refill_daily.txt").read_text(encoding="utf-8")
        m = re.search(r"refill (\d{4}-\d\d-\d\d): (\d+) stories left", t)
        if m and (now.date() - datetime.fromisoformat(m.group(1)).date()).days <= 2:
            bank = int(m.group(2))
    except Exception:
        pass
    log = ""
    try:
        log = (root / LOG).read_text(encoding="utf-8")
    except Exception:
        pass
    return Snap(now, runs, _read_json(root / QUEUE, {"posts": []}).get("posts", []), bank,
                _read_json(root / "reelfactory/stories/refill_usage.json", {}), quota_day(), log,
                {s: guard.halted(s, root) for s in ("poster", "self_change", "refill")})


def _log(root: Path, now: datetime, kind: str, name: str, why: str, result: str, tag: str = "") -> None:
    line = f"- {now.strftime('%Y-%m-%d %H:%M')} IST | {kind} | {name} | {why}{' [' + tag + ']' if tag else ''} | {result}\n"
    p = root / LOG
    p.parent.mkdir(parents=True, exist_ok=True)
    if not p.exists():
        p.write_text("# DASHX Autonomy log\nOne line per fix or report. Written by the machine (autonomy/heal.py).\n\n", encoding="utf-8", newline="\n")
    with open(p, "a", encoding="utf-8", newline="\n") as f:
        f.write(line)


def _may_write(path: str, rules: dict) -> bool:
    n = guard.normalize(path)
    return n is not None and n in rules["healing"]["may_write"]


def _post(posts: list[dict], title: str) -> dict | None:
    return next((p for p in posts if p.get("title") == title), None)


def default_comment_fn(post: dict, net: str) -> bool:
    """Real comment backfill: reuses poster.meta_comments (poster/ is not modified). Needs META_PAGE_TOKEN."""
    sys.path.insert(0, str(ROOT / "poster"))
    import poster as P  # noqa: PLC0415
    tok = os.environ.get("META_PAGE_TOKEN", "").strip()
    if not tok:
        return False
    key = "ig" if net == "instagram" else "fb"
    notes = post.setdefault("notes", {})
    notes.pop(f"{key}_comment", None)
    P.meta_comments(post, notes[NOTE_ID[net]], tok, key)
    return notes.get(f"{key}_comment") == ["ok"]


def execute(acts: list[Action], s: Snap, rules: dict, api, root: Path = ROOT, comment_fn=default_comment_fn, dry: bool = False) -> list[str]:
    """Do the planned fixes. Every fix and report goes to autonomy/log.md. Returns short result lines."""
    out, now = [], s.now
    queue_path = root / QUEUE
    q = _read_json(queue_path, {"posts": []})
    q_dirty = False
    seen_reports = set()
    for ln in s.log_text.splitlines():
        parts = ln.split(" | ")
        if len(parts) >= 5 and parts[1] == "report" and now.strftime("%Y-%m-%d") in parts[0]:
            seen_reports.add(parts[2] + "|" + parts[3])
    for a in acts:
        if a.kind == "report":
            key = a.name + "|" + a.why
            if key in seen_reports:
                continue                           # one report per problem per day
            out.append(f"REPORT {a.name}: {a.why}")
            if not dry:
                _log(root, now, "report", a.name, a.why, "not fixed (owner/other)")
            continue
        if dry:
            out.append(f"WOULD {a.name}: {a.why}"); continue
        if a.kind == "dispatch":
            if a.workflow not in rules["healing"]["may_dispatch"]:
                _log(root, now, "report", a.name, f"{a.workflow} is not on the may_dispatch list", "REFUSED"); continue
            try:
                api.dispatch(a.workflow, a.inputs)
                res = "dispatched"
            except Exception as e:
                res = f"dispatch failed: {type(e).__name__}"
            _log(root, now, "fix", a.name, a.why, res, a.tag)
            out.append(f"{a.name}: {res}")
        elif a.kind in ("edit_queue", "backfill_comment"):
            if not _may_write(QUEUE, rules):
                _log(root, now, "report", a.name, "queue.json is not on the may_write list", "REFUSED"); continue
            p = _post(q["posts"], a.post_title)
            if not p:
                continue
            if a.kind == "edit_queue":
                ok, why = retry_safe(p, a.network)           # checked AGAIN right before the write
                if not ok:
                    _log(root, now, "report", "network_failed", f"{a.post_title}: {a.network} NOT retried: {why}", "duplicate guard"); continue
                p["results"][a.network] = {}
                p.setdefault("notes", {})[f"heal_retry_{a.network}"] = now.isoformat()
                res = "cleared once; the poster retries it at its next check"
            else:
                key = "ig" if a.network == "instagram" else "fb"
                p.setdefault("notes", {})[f"heal_comment_{key}"] = p["notes"].get(f"heal_comment_{key}", 0) + 1
                try:
                    res = "comment posted" if comment_fn(p, a.network) else "comment still not ok (tries counted)"
                except Exception as e:
                    res = f"comment backfill failed: {type(e).__name__}"
            q_dirty = True
            _log(root, now, "fix", a.name, a.why, res)
            out.append(f"{a.name}: {res}")
    if q_dirty:
        queue_path.write_text(json.dumps(q, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    return out


def main(argv: list[str]) -> int:
    dry = "--dry" in argv
    stop = guard.halted("all")
    if stop:
        print(f"{stop} is on: autonomy does nothing")
        return 0
    try:
        rules = guard.load_rules()
    except guard.RulesTampered as e:
        print(f"::error::RULES TAMPERED ({e}). Autonomy stopped. Owner must check autonomy/RULES.json.")
        return 1
    api = GitHub()
    s = collect(api)
    for line in execute(plan(s, rules), s, rules, api, dry=dry):
        print(line)
    print("heal check done", s.now.isoformat())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
