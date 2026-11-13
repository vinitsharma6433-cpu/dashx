"""DASHX Autonomy, Phase 8: hand-over simulation. Run on a TEST COPY (a temporary folder with its own local git 'origin'), never on the real repo.

    python autonomy/simulate.py              run every scenario and print PASS / FAIL with the evidence
    python autonomy/simulate.py --repo-report   also list what this BUILD changed in the real repo outside autonomy/ and tests

Scenarios (the 7 required + the rule-file guarantees + one full day):
  S1 dead poster loop            S5 a change touching a DENY file (must be refused)
  S2 one failed network          S6 a change inside a blocked window (must wait)
  S3 missing comment             S7 a trend topic that breaks the brand rules (must be dropped)
  S4 a bad self-change (must auto-revert)
  S8 the machine cannot edit RULES.json (every writer, tamper detection, static scan)
  S9 a full machine day on the copy: no protected file changes, only the machine's own notes
Nothing here posts, calls GitHub, calls a model or touches the real repo. The test copy is deleted at the end.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import alerts  # noqa: E402
import guard  # noqa: E402
import heal  # noqa: E402
import improve  # noqa: E402
import learning  # noqa: E402
import report  # noqa: E402
import series_memory  # noqa: E402
import trend_feed  # noqa: E402
import trends  # noqa: E402

REPO = guard.ROOT
IST = guard.IST
NOW = datetime(2026, 11, 13, 15, 30, tzinfo=IST)
SIT = "reelfactory/stories/situations.json"
RSS = b"<?xml version='1.0'?><rss><channel><title>t</title><item><title>Gully cricket tournament in Meerut lane</title></item><item><title>Board exam date sheet released</title></item></channel></rss>"


# ---------------------------------------------------------------- the test copy
def sh(cwd: Path, *a: str) -> str:
    r = subprocess.run(["git", "-c", "user.name=sim", "-c", "user.email=sim@sim", *a], cwd=cwd, capture_output=True, text=True, encoding="utf-8")
    if r.returncode:
        raise RuntimeError(f"git {a[0]}: {r.stderr.strip()[:150]}")
    return r.stdout.strip()


def rm_tree(path: Path) -> None:
    """Delete a folder tree, also the read-only files git leaves on Windows."""
    def fix(func, p, *exc):
        try:
            os.chmod(p, stat.S_IWRITE)
            func(p)
        except Exception:
            pass
    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=fix)
    else:
        shutil.rmtree(path, onerror=fix)


class Env:
    """A temporary copy of the files the machine works with + a local bare 'origin'. Deleted by close()."""
    COPY = ["autonomy", "poster", ".github/workflows", "status/index.html", "reelfactory/stories", "reelfactory/factory", "reelfactory/scripts", "reelfactory/queue_config.json"]

    def __init__(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="dashx-sim-"))
        self.root, self.origin = self.tmp / "work", self.tmp / "origin.git"
        for rel in self.COPY:
            src = REPO / rel
            dst = self.root / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            if src.is_dir():
                shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "upgrade_test", "STOP_*"))
            elif src.exists():
                shutil.copy2(src, dst)
        for stale in ("autonomy/log.md", "autonomy/trends.json", "autonomy/learning.json", "autonomy/metrics.json", "autonomy/memory.json", "autonomy/status.json", "autonomy/watch.json",
                      "autonomy/blocked_ideas.json", "autonomy/changes.jsonl", "autonomy/slot_hints.json"):
            (self.root / stale).unlink(missing_ok=True)
        sh(self.tmp, "init", "-q", "--bare", "-b", "main", str(self.origin))
        sh(self.root, "init", "-q", "-b", "main")
        sh(self.root, "remote", "add", "origin", str(self.origin))
        sh(self.root, "add", "-A")
        sh(self.root, "commit", "-q", "-m", "test copy")
        sh(self.root, "push", "-q", "-u", "origin", "main")
        self.git = improve.Git(self.root)
        self.start = sh(self.root, "rev-parse", "HEAD")

    def close(self):
        rm_tree(self.tmp)

    # queue helpers
    def queue(self) -> dict:
        return json.loads((self.root / "poster/queue.json").read_text(encoding="utf-8"))

    def put_queue(self, q: dict) -> None:
        (self.root / "poster/queue.json").write_text(json.dumps(q, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def add_post(self, title, hours_from_now, results=None, notes=None, nets=("youtube", "instagram", "facebook"), status="scheduled", comments=True, now=NOW) -> dict:
        p = {"title": f"{title} DASHX", "media": f"https://x/{title}.mp4", "when": (now + timedelta(hours=hours_from_now)).isoformat(), "networks": list(nets),
             "results": results or {}, "notes": notes or {}, "status": status, "comments": ["c"] if comments else []}
        q = self.queue()
        q["posts"].append(p)
        self.put_queue(q)
        return p

    def post(self, title) -> dict:
        return next(p for p in self.queue()["posts"] if p["title"] == f"{title} DASHX")

    def log(self) -> str:
        p = self.root / "autonomy/log.md"
        return p.read_text(encoding="utf-8") if p.exists() else ""

    def situations(self) -> list[str]:
        return json.loads((self.root / SIT).read_text(encoding="utf-8"))["situations"]

    def snapshot(self) -> dict[str, str]:
        out = {}
        for p in self.root.rglob("*"):
            if p.is_file() and ".git" not in p.relative_to(self.root).parts:
                out[p.relative_to(self.root).as_posix()] = hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
        return out


class FakeAPI:
    def __init__(self, runs=None):
        self.runs_by_wf, self.sent = runs or {}, []

    def runs(self, wf):
        return self.runs_by_wf.get(wf, [])

    def dispatch(self, wf, inputs, ref="main"):
        self.sent.append((wf, inputs))


class FakeGH:
    def __init__(self, canary=(True, "QC scores [100] (need 100)")):
        self.canary, self.prs, self.branches = canary, [], []

    def canary_reel(self, branch, qc):
        self.branches.append(branch)
        return self.canary

    def open_pr(self, branch, title, body):
        self.prs.append(branch)
        return "https://example.invalid/pull/1"


class FakeIssues:
    def __init__(self):
        self.items, self.n = [], 0

    def open_alerts(self):
        return [i for i in self.items if i["state"] == "open"]

    def create(self, body):
        self.n += 1
        self.items.append({"number": self.n, "title": alerts.TITLE, "body": body, "state": "open"})

    def update(self, n, body):
        next(i for i in self.items if i["number"] == n)["body"] = body

    def comment(self, n, text):
        pass

    def close(self, n):
        next(i for i in self.items if i["number"] == n)["state"] = "closed"


class FakeLive:
    def yt_token(self): return "t"
    def meta_token(self): return "m"
    def yt(self, ids, tok): return {i: {"views": 100 * (n + 1), "likes": n, "comments": 1} for n, i in enumerate(ids)}
    def ig(self, mid, tok): return {"likes": 2, "comments": 0}
    def fb(self, vid, tok): return {"likes": 1, "comments": 0}


def run_dict(id_, status="completed", concl="success", event="schedule", ago_min=45):
    t = NOW - timedelta(minutes=ago_min)
    return {"id": id_, "status": status, "conclusion": concl, "event": event, "created": t, "updated": t}


checks_ok = lambda root, git: (True, "unit tests and story checks ok")   # noqa: E731


# ---------------------------------------------------------------- result bookkeeping
@dataclass
class Result:
    code: str
    name: str
    checks: list[tuple[bool, str]] = field(default_factory=list)

    def check(self, ok: bool, what: str) -> None:
        self.checks.append((bool(ok), what))

    @property
    def ok(self) -> bool:
        return bool(self.checks) and all(c[0] for c in self.checks)


def heal_cycle(E: Env, api: FakeAPI, now: datetime, comment_fn=None):
    rules = guard.load_rules()
    s = heal.collect(api, E.root, now)
    acts = heal.plan(s, rules)
    out = heal.execute(acts, s, rules, api, E.root, comment_fn=comment_fn or (lambda p, n: True))
    return acts, out


# ---------------------------------------------------------------- scenarios
def s1_dead_loop() -> Result:
    r, E = Result("S1", "Dead poster loop is re-dispatched (max 2 per hour)"), Env()
    try:
        E.add_post("sim-pending", 5)
        api = FakeAPI({"dashx-poster.yml": [run_dict(1, ago_min=45)]})
        heal_cycle(E, api, NOW)
        r.check(api.sent == [("dashx-poster.yml", {})], f"1st check: poster re-dispatched ({len(api.sent)} dispatch)")
        heal_cycle(E, api, NOW + timedelta(minutes=10))
        r.check(len(api.sent) == 2, f"10 min later, still dead: 2nd re-dispatch ({len(api.sent)} total)")
        acts, _ = heal_cycle(E, api, NOW + timedelta(minutes=20))
        r.check(len(api.sent) == 2 and any(a.name == "poster_redispatch_limit" for a in acts), "20 min later: limit of 2 per hour holds, only reported")
        r.check(E.log().count("| fix | poster_redispatch |") == 2, "both re-dispatches are in autonomy/log.md")
        busy = FakeAPI({"dashx-poster.yml": [run_dict(2, "in_progress", None, ago_min=3)]})
        E2 = Env()
        try:
            E2.add_post("sim-pending", 5)
            heal_cycle(E2, busy, NOW)
            r.check(busy.sent == [], "a poster run that is alive is left alone")
            (E2.root / "STOP_POSTER").write_text("", encoding="utf-8")
            dead = FakeAPI({"dashx-poster.yml": [run_dict(1, ago_min=90)]})
            heal_cycle(E2, dead, NOW)
            r.check(dead.sent == [], "STOP_POSTER switch: no re-dispatch")
        finally:
            E2.close()
    finally:
        E.close()
    return r


def s2_failed_network() -> Result:
    r, E = Result("S2", "One failed network is retried ONCE, never when a duplicate is possible"), Env()
    try:
        failed = {"youtube": {"ok": True}, "facebook": {"ok": False, "tries": 3, "error": "Graph request timeout"}}
        E.add_post("sim-net-fail", -2, results=failed, nets=("youtube", "facebook"))
        E.add_post("sim-maybe-live", -2, results={"youtube": {"ok": True}, "facebook": {"ok": False, "tries": 3, "error": "Graph request timeout"}},
                   notes={"fb_video_id": "123"}, nets=("youtube", "facebook"))
        before_other = json.dumps([p for p in E.queue()["posts"] if p["title"] not in ("sim-net-fail DASHX", "sim-maybe-live DASHX")], sort_keys=True)
        api = FakeAPI({"dashx-poster.yml": [run_dict(1, "in_progress", None, ago_min=2)]})
        acts, _ = heal_cycle(E, api, NOW)
        p = E.post("sim-net-fail")
        r.check(p["results"]["facebook"] == {} and "heal_retry_facebook" in p["notes"], "failed Facebook result cleared once and marked")
        r.check(p["results"]["youtube"]["ok"] is True, "the YouTube result that worked is untouched")
        m = E.post("sim-maybe-live")
        r.check(m["results"]["facebook"].get("tries") == 3 and "heal_retry_facebook" not in m["notes"], "DUPLICATE GUARD: video id exists, so it may be live: NOT retried")
        r.check(any(a.name == "network_failed" for a in acts), "that one is only reported")
        r.check(json.dumps([x for x in E.queue()["posts"] if x["title"] not in ("sim-net-fail DASHX", "sim-maybe-live DASHX")], sort_keys=True) == before_other, "every other post in the queue is byte-for-byte the same")
        q = E.queue()
        next(x for x in q["posts"] if x["title"] == "sim-net-fail DASHX")["results"]["facebook"] = {"ok": False, "tries": 3, "error": "Graph request timeout"}
        E.put_queue(q)
        heal_cycle(E, api, NOW + timedelta(minutes=30))
        r.check(E.post("sim-net-fail")["results"]["facebook"].get("tries") == 3, "it failed again: NOT retried a second time")
    finally:
        E.close()
    return r


def s3_missing_comment() -> Result:
    r, E = Result("S3", "A missing first comment is backfilled (max 2 tries)"), Env()
    try:
        at = (NOW - timedelta(hours=3)).isoformat()
        E.add_post("sim-no-comment", -3, results={"instagram": {"ok": True, "link": "instagram:99", "at": at}}, notes={"ig_media_id": "99", "ig_comment": ["failed 400"]},
                   nets=("instagram",), status="done", now=NOW)
        calls = []
        api = FakeAPI({"dashx-poster.yml": [run_dict(1, "in_progress", None, ago_min=2)]})
        fn = lambda post, net: calls.append((post["title"], net)) or False   # noqa: E731  Meta still says no
        for i in range(4):
            heal_cycle(E, api, NOW + timedelta(minutes=30 * i), comment_fn=fn)
        r.check(calls == [("sim-no-comment DASHX", "instagram")] * 2, f"backfill called exactly 2 times in 4 checks: {len(calls)}")
        r.check(E.post("sim-no-comment")["notes"]["heal_comment_ig"] == 2, "tries are counted in the queue notes")
        E2 = Env()
        try:
            E2.add_post("sim-no-comment", -3, results={"instagram": {"ok": True, "link": "instagram:99", "at": at}}, notes={"ig_media_id": "99", "ig_comment": ["ok"]}, nets=("instagram",), status="done")
            c2 = []
            heal_cycle(E2, api, NOW, comment_fn=lambda p, n: c2.append(1) or True)
            r.check(c2 == [], "a comment that is already ok is never touched")
        finally:
            E2.close()
    finally:
        E.close()
    return r


def _trend_fetcher(url, rules):
    return RSS


def _s4(code: str, title: str, now: datetime, empty_queue: bool) -> Result:
    r, E = Result(code, title), Env()
    try:
        original = (E.root / SIT).read_bytes()
        if empty_queue:
            q0 = E.queue()                                  # the copy holds the REAL queue: posts it contains for today would be counted as the "next reels"
            q0["posts"] = []                                # so start the scenario with an empty queue (the real one is never touched)
            E.put_queue(q0)
            sh(E.root, "add", "-A")
            sh(E.root, "commit", "-q", "-m", "sim: empty queue")
            sh(E.root, "push", "-q", "origin", "main")
        trends.run(E.root, now, force=True, fetcher=_trend_fetcher)
        gh = FakeGH()
        out = improve.run(E.root, now, E.git, gh, checks_ok, now_fn=lambda: now)
        r.check(out == "merged", f"a good-looking change passed the canary and was merged ({out})")
        r.check(len(E.situations()) == len(json.loads(original)["situations"]) + 1, "one situation line was added")
        w = json.loads((E.root / "autonomy/watch.json").read_text(encoding="utf-8"))
        merged_at = datetime.fromisoformat(w["merged_at"])
        r.check(w["status"] == "watching", "watch window opened for the next 2 reels")
        for h, bad in ((5, False), (10, True)):
            res = {"youtube": {"ok": True}, "instagram": {"ok": True}, "facebook": {"ok": True}}
            if bad:
                res["instagram"] = {"ok": False, "error": "Instagram processing ERROR: media upload failed", "tries": 1}
            E.add_post(f"sim-after-{h}", h, results=res, status="done", now=merged_at)
        out2 = improve.run(E.root, now + timedelta(hours=30), E.git, FakeGH(), checks_ok, factory_runs=[], watch_only=True)
        r.check(out2 == "reverted", f"the 2nd reel after the change had a NEW failure: {out2}")
        r.check((E.root / SIT).read_bytes().replace(b"\r\n", b"\n") == original.replace(b"\r\n", b"\n"), "situations.json is back to exactly the original")
        blocked = json.loads((E.root / "autonomy/blocked_ideas.json").read_text(encoding="utf-8"))["ideas"]
        r.check(len(blocked) == 1 and list(blocked.values())[0] == (now + timedelta(hours=30, days=14)).date().isoformat(), f"idea blocked for 14 days: {blocked}")
        r.check("| improve | auto_revert |" in E.log(), "the reason is in autonomy/log.md")
        r.check(sh(E.root, "rev-parse", "main") == sh(E.origin, "rev-parse", "main"), "the revert is pushed to origin/main")
        # and a change that fails the canary is never merged
        E3 = Env()
        try:
            trends.run(E3.root, now, force=True, fetcher=_trend_fetcher)
            o = improve.run(E3.root, now, E3.git, FakeGH((False, "QC scores [96] (need 100)")), checks_ok, now_fn=lambda: now)
            r.check(o == "canary_failed" and sh(E3.root, "rev-parse", "main") == E3.start, "QC 96 in the test reel: nothing merged, main untouched")
        finally:
            E3.close()
    finally:
        E.close()
    return r


def _evil(files):
    def improver(root, rules, now, blocked):
        return improve.Proposal("evil", "simulated attack", dict(files))
    return improver


def s4_bad_self_change_reverts() -> Result:
    return _s4("S4", "A bad self-change is auto-reverted", NOW, empty_queue=True)


def s4b_populated_queue() -> Result:
    """The same, but on the REAL queue with its real recent posts (they are older than the change, so they must not count as 'the next 2 reels')."""
    qs = json.loads((REPO / "poster/queue.json").read_text(encoding="utf-8")).get("posts", [])
    last = max((datetime.fromisoformat(p["when"]) for p in qs if p.get("when")), default=NOW)
    t = max(NOW, last + timedelta(hours=1)).astimezone(guard.IST)
    rules = guard.load_rules()
    while guard.blocked_until(t, rules):
        t += timedelta(minutes=30)
    res = _s4("S4b", "A bad self-change is auto-reverted on a populated queue with real recent posts", t, empty_queue=False)
    res.check(len(qs) >= 5, f"the copy really held {len(qs)} real posts (latest {last.isoformat()[:16]}), none removed")
    return res


def s5_deny_files_refused() -> Result:
    r, E = Result("S5", "A change touching a DENY file is refused (pull request, never a merge)"), Env()
    old = improve.IMPROVERS["situation_from_trend"]
    try:
        attacks = {"a workflow": {".github/workflows/dashx-poster.yml": "name: hacked\n"},
                   "the rule file": {"autonomy/RULES.json": '{"limits": {"max_self_changes_per_day": 99}}\n'},
                   "the guard": {"autonomy/guard.py": "def check_change(*a, **k): return True\n"},
                   "poster logic": {"poster/poster.py": "print('posting everything')\n"},
                   "a kill switch": {"STOP_POSTER": ""},
                   "a secret file": {".env": "TOKEN=abc\n"},
                   "allowed + denied together": {SIT: (E.root / SIT).read_text(encoding="utf-8") + " ", "poster/loop.sh": "#!/bin/sh\n"}}
        gh = FakeGH()
        for label, files in attacks.items():
            improve.IMPROVERS["situation_from_trend"] = _evil(files)
            out = improve.run(E.root, NOW, E.git, gh, checks_ok, now_fn=lambda: NOW)
            r.check(out == "pr", f"{label}: result '{out}' (pull request for the owner)")
        r.check(sh(E.root, "rev-parse", "main") == E.start and sh(E.origin, "rev-parse", "main") == E.start, "main is exactly where it started")
        r.check(gh.branches == [], "no canary test reel was even started for any of them")
        r.check(len(gh.prs) == len(attacks), f"{len(gh.prs)} pull requests opened for the owner")
        rules = guard.load_rules()
        r.check(all(guard.check_change(list(f), NOW, E.root, rules).needs_human for f in attacks.values()), "the guard on its own says 'needs a human' for every one")
        r.check(not (E.root / "STOP_POSTER").exists(), "the kill switch file was not created")
    finally:
        improve.IMPROVERS["situation_from_trend"] = old
        E.close()
    return r


def s6_blocked_window_waits() -> Result:
    r, E = Result("S6", "A change inside a blocked window waits"), Env()
    try:
        trends.run(E.root, NOW, force=True, fetcher=_trend_fetcher)
        for h, m in ((11, 0), (11, 59), (12, 30), (19, 0), (19, 45), (20, 30)):
            t = NOW.replace(hour=h, minute=m)
            gh = FakeGH()
            out = improve.run(E.root, t, E.git, gh, checks_ok, now_fn=lambda t=t: t)
            r.check(out == "wait" and gh.branches == [], f"{h:02d}:{m:02d} IST -> {out}, no branch, no test reel")
        r.check(sh(E.root, "rev-parse", "main") == E.start, "main untouched after all the waits")
        late = NOW.replace(hour=19, minute=10)
        out = improve.run(E.root, NOW, E.git, FakeGH(), checks_ok, now_fn=lambda: late)
        r.check(out == "refused_late" and sh(E.origin, "rev-parse", "main") == E.start, f"the canary ran into the window (19:10): merge refused ({out})")
        ok = improve.run(E.root, NOW.replace(hour=21, minute=0), E.git, FakeGH(), checks_ok, now_fn=lambda: NOW.replace(hour=21, minute=0))
        r.check(ok == "merged", f"outside the windows (21:00 IST) the same change goes through ({ok})")
        r.check(improve.run(E.root, NOW.replace(hour=21, minute=5), E.git, FakeGH(), checks_ok, now_fn=lambda: NOW.replace(hour=21, minute=5), watch_only=True) == "watching",
                "and a second change the same day is not even tried (one at a time)")
    finally:
        E.close()
    return r


def s7_brand_breaking_trend_dropped() -> Result:
    r, E = Result("S7", "A trend topic that breaks the brand rules is dropped"), Env()
    try:
        rules = guard.load_rules()
        themes = json.loads((E.root / "autonomy/trend_themes.json").read_text(encoding="utf-8"))
        bad = dict(themes["themes"][0], id="bad_price", label="Cheap bat sale", angle="Show our best bat at a discount price", situation="the best bat price offer", keywords=["cricket"])
        bad2 = dict(themes["themes"][1], id="bad_player", label="Kohli fan", angle="A kid beats Kohli at IPL", situation="a kid beats Kohli", keywords=["cricket"])
        themes["themes"] = [bad, bad2] + themes["themes"][:3]
        cal = json.loads((E.root / "autonomy/festivals.json").read_text(encoding="utf-8"))
        headlines = {"news": ["Best cricket bat price offer today", "Kohli IPL match tonight", "Minister election rally in Meerut", "Man dies in accident near stadium",
                              "Police arrest man in cricket betting case", "Temple row grows over cricket ground", "Gully cricket tournament in Meerut lane"]}
        out = trends.build(NOW.date(), headlines, rules, themes, cal)
        ids = [t["id"] for t in out["topics"]]
        r.check("bad_price" not in ids and "bad_player" not in ids, f"price/brand/player topics dropped: kept {ids}")
        r.check(out["stats"]["dropped_unsafe"] == 6, f"6 of 7 headlines (politics, religion, tragedy, crime, brand, player) thrown away: {out['stats']['dropped_unsafe']}")
        dump = json.dumps(out, ensure_ascii=False).lower()
        r.check(not any(w in dump for w in ("minister", "election", "temple", "kohli", "police", "accident", "gully cricket tournament")), "no headline text is stored anywhere in trends.json")
        feed = trend_feed.pick([{"id": "x", "topic": "Cheap sale", "why_fits": "w", "story_angle": "the best price", "strength": 9, "expires": "2026-11-20"},
                                {"id": "y", "topic": "Fine", "why_fits": "w", "story_angle": "a safe angle", "strength": 1, "expires": "2026-11-20"}], NOW.date(), rules)
        r.check([f["id"] for f in feed] == ["y"], "the writer-prompt feed drops it even if the file was edited by hand")
        (E.root / "autonomy/trends.json").write_text(json.dumps({"topics": [{"id": "x", "topic": "T", "story_angle": "a", "story_situation": "the best bat price offer", "strength": 9, "expires": "2026-11-20"}]}), encoding="utf-8")
        r.check(improve.situation_from_trend(E.root, rules, NOW, set()) is None, "the self-improver will not turn it into a story seed either")
    finally:
        E.close()
    return r


def s8_rules_cannot_be_edited() -> Result:
    r, E = Result("S8", "The machine cannot edit RULES.json"), Env()
    try:
        rules = guard.load_rules()
        for p in ("autonomy/RULES.json", "autonomy/RULES.sha256", "autonomy/guard.py", "AUTONOMY/rules.json", "./autonomy/RULES.json", "autonomy\\RULES.json", "autonomy/x/../RULES.json", "autonomy/RULES.json."):
            r.check(guard.classify(p, rules)[0] == "deny", f"classify('{p}') = deny")
        r.check(not heal._may_write("autonomy/RULES.json", rules), "self-healing may not write it")
        r.check(not any(x in ("autonomy/RULES.json", "autonomy/RULES.sha256") for x in rules["state_files"]["paths"] + rules["healing"]["may_write"]), "it is on no write list")
        # static scan: no module except the owner's `seal` command can write the rule file or its seal
        bad = []
        for f in sorted((REPO / "autonomy").glob("*.py")):
            if f.name in ("guard.py", "simulate.py"):
                continue
            for n, ln in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
                if any(k in ln for k in ("RULES_PATH", "SEAL_PATH", "RULES.json", "RULES.sha256")) and any(w in ln for w in ("write_text", "write_bytes", "open(", "unlink", "rename", "replace(")):
                    bad.append(f"{f.name}:{n}")
        r.check(not bad, f"no module writes the rule file or its seal (static scan of {len(list((REPO / 'autonomy').glob('*.py')))} files) {bad}")
        guard_src = (REPO / "autonomy" / "guard.py").read_text(encoding="utf-8")
        r.check(guard_src.count("seal_path.write_text") == 1 and "def seal(" in guard_src and "OWNER ONLY" in guard_src, "the only writer is guard.seal(), a command for the owner")
        # tamper: every part of the machine stops
        tampered = E.tmp / "RULES.json"
        tampered.write_text((REPO / "autonomy/RULES.json").read_text(encoding="utf-8").replace('"max_self_changes_per_day": 1', '"max_self_changes_per_day": 99'), encoding="utf-8")
        old = (guard.RULES_PATH, guard.SEAL_PATH)
        try:
            guard.RULES_PATH = tampered
            raised = []
            for name, fn in (("trends", lambda: trends.run(E.root, NOW, force=True, fetcher=_trend_fetcher)), ("learning", lambda: learning.run(E.root, NOW, force=True, live=FakeLive())),
                             ("improve", lambda: improve.run(E.root, NOW, E.git, FakeGH(), checks_ok, now_fn=lambda: NOW)), ("guard.load_rules", guard.load_rules)):
                try:
                    fn()
                except guard.RulesTampered:
                    raised.append(name)
            r.check(raised == ["trends", "learning", "improve", "guard.load_rules"], f"edited rule file: all of these stop with RulesTampered: {raised}")
            d = guard.check_change([SIT], NOW, E.root)
            r.check(not d.ok and d.needs_human, "the guard refuses every change")
            r.check(heal.main(["--dry"]) == 1, "self-healing stops with an error")
            sig = alerts.load_signals(E.root, NOW)
            r.check([p.id for p in alerts.detect(sig)] == ["RULES_TAMPERED"], "an alert for the owner is raised (RULES_TAMPERED)")
        finally:
            guard.RULES_PATH, guard.SEAL_PATH = old
        r.check(guard.load_rules()["version"] == 1, "the real rule file still matches its seal")
    finally:
        E.close()
    return r


def s9_full_day_changes_nothing_protected() -> Result:
    r, E = Result("S9", "A full machine day changes no protected file"), Env()
    try:
        before = E.snapshot()
        rules = guard.load_rules()
        E.add_post("sim-pending", 5)
        E.add_post("sim-net-fail", -2, results={"youtube": {"ok": True}, "facebook": {"ok": False, "tries": 3, "error": "Graph request timeout"}}, nets=("youtube", "facebook"))
        E.add_post("sim-no-comment", -3, results={"instagram": {"ok": True, "at": (NOW - timedelta(hours=3)).isoformat()}}, notes={"ig_media_id": "9", "ig_comment": ["failed"]}, nets=("instagram",), status="done")
        sh(E.root, "add", "-A"); sh(E.root, "commit", "-q", "-m", "queue"); sh(E.root, "push", "-q", "origin", "main")
        before = E.snapshot()
        heal_cycle(E, FakeAPI({"dashx-poster.yml": [run_dict(1, ago_min=60)]}), NOW)
        trends.run(E.root, NOW, force=True, fetcher=_trend_fetcher)
        learning.run(E.root, NOW, force=True, live=FakeLive())
        series_memory.write(E.root, NOW)
        alerts.run(E.root, NOW, FakeIssues())
        report.run(E.root, NOW.replace(hour=21, minute=0))
        improve.run(E.root, NOW, E.git, FakeGH(), checks_ok, now_fn=lambda: NOW)
        after = E.snapshot()
        machine_outputs = set(rules["state_files"]["paths"]) | {"poster/queue.json", SIT}
        changed = {p for p in set(before) | set(after) if before.get(p) != after.get(p)}
        illegal = sorted(p for p in changed if p not in machine_outputs)
        r.check(not illegal, f"files changed: {sorted(changed)}")
        r.check(not illegal, "every changed file is one the machine is allowed to write (its notes, the queue fix, one story seed)")
        protected = [p for p in before if p.startswith(("autonomy/", ".github/", "poster/")) and p not in machine_outputs]
        r.check(all(before[p] == after[p] for p in protected), f"{len(protected)} protected files (rules, seal, guard, all machine code, workflows, poster code) are byte-for-byte unchanged")
        r.check(not any((E.root / n).exists() or (E.root / "reelfactory" / n).exists() for n in ("STOP_AUTONOMY", "STOP_POSTER", "STOP_QUEUE", "STOP_REFILL")), "no kill-switch file was created or removed")
        r.check(set(after) - set(before) <= machine_outputs, f"new files are only machine notes: {sorted(set(after) - set(before))}")
        r.check(sh(E.root, "status", "--porcelain", "--", ".github", "poster/poster.py", "poster/loop.sh", "autonomy/RULES.json", "autonomy/guard.py") == "", "git agrees: nothing under .github, poster logic, RULES.json or guard.py is modified")
    finally:
        E.close()
    return r


SCENARIOS = [s1_dead_loop, s2_failed_network, s3_missing_comment, s4_bad_self_change_reverts, s5_deny_files_refused, s6_blocked_window_waits,
             s7_brand_breaking_trend_dropped, s8_rules_cannot_be_edited, s9_full_day_changes_nothing_protected, s4b_populated_queue]


def repo_report() -> list[str]:
    """What this BUILD changed in the real repo (compared with the point where the autonomy branch started)."""
    try:
        base = subprocess.run(["git", "merge-base", "HEAD", "origin/main"], cwd=REPO, capture_output=True, text=True, encoding="utf-8").stdout.strip()
        names = subprocess.run(["git", "diff", "--name-status", base, "HEAD"], cwd=REPO, capture_output=True, text=True, encoding="utf-8").stdout.splitlines()
    except Exception:
        return ["(git not available)"]
    out = []
    for ln in names:
        st, _, path = ln.partition("\t")
        if path.startswith(("autonomy/", "reelfactory/tests/test_autonomy")):
            continue
        out.append(f"{st}  {path}")
    return out


def main(argv: list[str]) -> int:
    import simulate_scout  # Phase 9: the 6 scout scenarios C1..C6
    results = [fn() for fn in SCENARIOS + simulate_scout.SCOUT_SCENARIOS]
    for res in results:
        print(f"\n{res.code}  {res.name} ... {'PASS' if res.ok else 'FAIL'}")
        for ok, what in res.checks:
            print(f"    [{'ok' if ok else 'XX'}] {what}")
    passed = sum(1 for r in results if r.ok)
    print(f"\n{passed}/{len(results)} scenarios passed")
    if "--repo-report" in argv:
        print("\nFiles this build changed outside autonomy/ and the autonomy tests (all need the owner's review; the machine itself changes none of them):")
        for ln in repo_report():
            print("  " + ln)
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
