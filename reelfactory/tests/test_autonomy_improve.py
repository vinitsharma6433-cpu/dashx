"""Phase 6 tests: self-improvement loop (autonomy/improve.py) with REAL git in a temporary repo and a temporary bare 'origin'. No GitHub, no network."""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "autonomy"))
import guard as g  # noqa: E402
import improve as im  # noqa: E402

RULES = g.load_rules()
NOW = datetime(2026, 11, 11, 15, 30, tzinfo=g.IST)
SIT = "reelfactory/stories/situations.json"
SITUATIONS = (REPO / SIT).read_text(encoding="utf-8")


def sh(cwd, *a):
    r = subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *a], cwd=cwd, capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, (a, r.stderr)
    return r.stdout.strip()


class FakeGH:
    def __init__(self, canary=(True, "QC scores [100] (need 100)")):
        self.canary, self.prs, self.canary_branches = canary, [], []

    def canary_reel(self, branch, qc):
        self.canary_branches.append(branch)
        return self.canary

    def open_pr(self, branch, title, body):
        self.prs.append((branch, title, body))
        return "https://github.com/x/y/pull/1"


def checks_ok(root, git):
    return True, "tests ok"


def checks_bad(root, git):
    return False, "unit tests failed: boom"


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.origin = self.tmp / "origin.git"
        self.work = self.tmp / "work"
        sh(self.tmp, "init", "-q", "--bare", "-b", "main", str(self.origin))
        sh(self.tmp, "clone", "-q", str(self.origin), str(self.work))
        sh(self.work, "checkout", "-q", "-b", "main")
        for rel, text in {SIT: SITUATIONS, "autonomy/trends.json": json.dumps(self.trends(), ensure_ascii=False),
                          "poster/queue.json": json.dumps({"posts": []}), "poster/poster.py": "# poster\n", ".github/workflows/w.yml": "name: w\n",
                          "autonomy/RULES.json": "{}\n"}.items():
            (self.work / rel).parent.mkdir(parents=True, exist_ok=True)
            (self.work / rel).write_text(text, encoding="utf-8", newline="\n")
        sh(self.work, "add", "-A")
        sh(self.work, "commit", "-q", "-m", "start")
        sh(self.work, "push", "-q", "origin", "main")
        self.git = im.Git(self.work)
        self.start = sh(self.work, "rev-parse", "HEAD")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    @staticmethod
    def trends():
        return {"topics": [
            {"id": "bhai_dooj_2026", "topic": "Bhai Dooj", "strength": 10, "expires": "2026-11-12", "story_situation": "a brother and sister settle a cricket argument the sibling way"},
            {"id": "gully_rules", "topic": "Gully rules", "strength": 5, "expires": "2026-11-14", "story_situation": "a house-rule argument: one-tip-one-hand and the wall is a six"}]}

    def go(self, now=NOW, gh=None, checks=checks_ok, **kw):
        kw.setdefault("now_fn", lambda: now)                     # the clock is the test's clock
        return im.run(self.work, now, self.git, gh or FakeGH(), checks, **kw)

    def situations(self, ref=None):
        txt = sh(self.work, "show", f"{ref}:{SIT}") if ref else (self.work / SIT).read_text(encoding="utf-8")
        return json.loads(txt)["situations"]

    def watch(self):
        return json.loads((self.work / im.WATCH).read_text(encoding="utf-8"))

    def log(self):
        return (self.work / im.LOG).read_text(encoding="utf-8")

    def origin_main(self):
        return sh(self.origin, "rev-parse", "main")

    def post(self, title, hours_from_merge, results=None, notes=None, merged=None):
        merged = merged or NOW
        nets = ["youtube", "instagram", "facebook"]
        res = results or {n: {"ok": True} for n in nets}
        return {"title": f"{title} DASHX", "when": (merged + timedelta(hours=hours_from_merge)).isoformat(), "networks": nets, "results": res, "notes": notes or {}, "status": "done"}

    def put_queue(self, posts):
        (self.work / "poster" / "queue.json").write_text(json.dumps({"posts": posts}), encoding="utf-8")


class Merge(Base):
    def test_a_good_change_is_merged_and_watched(self):
        gh = FakeGH()
        self.assertEqual(self.go(gh=gh), "merged")
        self.assertEqual(len(self.situations()), len(json.loads(SITUATIONS)["situations"]) + 1)
        self.assertIn("a brother and sister settle a cricket argument the sibling way", self.situations())
        w = self.watch()
        self.assertEqual((w["status"], w["idea"], w["need_reels"]), ("watching", "situation:bhai_dooj_2026", 2))
        self.assertEqual(w["files"], [SIT])
        self.assertEqual(self.origin_main(), sh(self.work, "rev-parse", "main"))                   # pushed
        self.assertEqual(sh(self.work, "branch", "--list", "autonomy/improve-*"), "")             # temp branch removed
        self.assertEqual(sh(self.origin, "branch", "--list", "autonomy/improve-*"), "")
        self.assertEqual(len(gh.canary_branches), 1)                                               # one test reel, on the temp branch
        self.assertTrue(gh.canary_branches[0].startswith("autonomy/improve-20261111"))
        self.assertIn("| improve | merged |", self.log())
        self.assertEqual(len((self.work / im.LEDGER).read_text(encoding="utf-8").splitlines()), 1)

    def test_only_allowed_and_note_files_changed(self):
        self.go()
        changed = set(sh(self.work, "diff", "--name-only", self.start, "main").splitlines())
        self.assertEqual(changed, {SIT, "autonomy/watch.json", "autonomy/changes.jsonl", "autonomy/log.md"})
        for protected in ("autonomy/RULES.json", "poster/poster.py", ".github/workflows/w.yml", "poster/queue.json"):
            self.assertNotIn(protected, changed)

    def test_the_change_is_one_small_line(self):
        self.go()
        added, removed = sh(self.work, "diff", "--numstat", self.start, "main", "--", SIT).split("\t")[:2]
        self.assertLessEqual(int(added) + int(removed), 3)

    def test_one_change_per_day_and_one_watch_at_a_time(self):
        self.go()
        self.assertEqual(self.go(now=NOW + timedelta(hours=1)), "watching")                         # watching: no second change
        self.assertEqual(len(self.situations()), len(json.loads(SITUATIONS)["situations"]) + 1)
        w = self.watch()
        w["status"] = "done"
        (self.work / im.WATCH).write_text(json.dumps(w), encoding="utf-8")
        self.assertEqual(self.go(now=NOW + timedelta(hours=2)), "limit")                           # the daily limit still holds


class Refusals(Base):
    def test_canary_test_reel_failure_blocks_the_idea_for_14_days(self):
        self.assertEqual(self.go(gh=FakeGH((False, "QC scores [96] (need 100)"))), "canary_failed")
        self.assertEqual(self.situations(), json.loads(SITUATIONS)["situations"])
        self.assertEqual(self.origin_main(), self.start)
        self.assertEqual(sh(self.origin, "branch", "--list", "autonomy/improve-*"), "")
        b = json.loads((self.work / im.BLOCKED).read_text(encoding="utf-8"))["ideas"]
        self.assertEqual(b["situation:bhai_dooj_2026"], (NOW + timedelta(days=14)).date().isoformat())
        self.assertIn("canary_failed", self.log())
        # next day: that idea is skipped, the next one is tried
        gh = FakeGH()
        self.assertEqual(self.go(now=NOW + timedelta(days=1), gh=gh), "merged")
        self.assertIn("a house-rule argument", " ".join(self.situations()))
        self.assertNotIn("brother and sister", " ".join(self.situations()))

    def test_unit_test_failure_blocks_too(self):
        gh = FakeGH()
        self.assertEqual(self.go(gh=gh, checks=checks_bad), "canary_failed")
        self.assertEqual(gh.canary_branches, [])                  # no test reel is even started
        self.assertEqual(self.origin_main(), self.start)

    def test_a_change_on_the_deny_list_becomes_a_pull_request(self):
        def evil(root, rules, now, blocked):
            return im.Proposal("evil", "edit a workflow", {".github/workflows/w.yml": "name: hacked\n", SIT: SITUATIONS})
        old = im.IMPROVERS["situation_from_trend"]
        try:
            im.IMPROVERS["situation_from_trend"] = evil
            gh = FakeGH()
            self.assertEqual(self.go(gh=gh), "pr")
        finally:
            im.IMPROVERS["situation_from_trend"] = old
        self.assertEqual(len(gh.prs), 1)
        self.assertEqual(self.origin_main(), self.start)           # nothing merged
        self.assertEqual(gh.canary_branches, [])
        self.assertIn("pr_for_owner", self.log())
        self.assertEqual((self.work / ".github/workflows/w.yml").read_text(encoding="utf-8"), "name: w\n")

    def test_the_rule_file_cannot_be_changed(self):
        def evil(root, rules, now, blocked):
            return im.Proposal("evil", "loosen the rules", {"autonomy/RULES.json": '{"limits": {}}\n'})
        old = im.IMPROVERS["situation_from_trend"]
        try:
            im.IMPROVERS["situation_from_trend"] = evil
            gh = FakeGH()
            self.assertEqual(self.go(gh=gh), "pr")
        finally:
            im.IMPROVERS["situation_from_trend"] = old
        self.assertEqual(self.origin_main(), self.start)
        self.assertEqual((self.work / "autonomy/RULES.json").read_text(encoding="utf-8"), "{}\n")

    def test_more_than_three_files_or_too_big_is_refused(self):
        def many(root, rules, now, blocked):
            return im.Proposal("many", "many files", {SIT: SITUATIONS + " ", "reelfactory/stories/characters.json": "{}\n", "reelfactory/stories/dialogue_bank.md": "x\n",
                                                      "reelfactory/factory/seo.py": "# x\n"})
        old = im.IMPROVERS["situation_from_trend"]
        try:
            im.IMPROVERS["situation_from_trend"] = many
            self.assertEqual(self.go(), "refused")
            im.IMPROVERS["situation_from_trend"] = lambda *a: im.Proposal("big", "big", {"reelfactory/stories/dialogue_bank.md": "\n".join(f"line {i}" for i in range(40)) + "\n"})
            self.assertEqual(self.go(now=NOW + timedelta(days=2)), "refused")
        finally:
            im.IMPROVERS["situation_from_trend"] = old
        self.assertEqual(self.origin_main(), self.start)

    def test_blocked_window_waits_and_makes_no_branch(self):
        for h, m in ((11, 0), (12, 30), (19, 15), (20, 30)):
            self.assertEqual(self.go(now=NOW.replace(hour=h, minute=m)), "wait", (h, m))
        self.assertEqual(sh(self.work, "branch", "--list", "autonomy/improve-*"), "")
        self.assertIn("try again after", self.log())

    def test_time_passing_into_a_window_stops_the_merge(self):
        calls = []

        def late():
            calls.append(1)
            return NOW.replace(hour=19, minute=10)               # the canary took so long that the slot window began
        self.assertEqual(self.go(now_fn=late), "refused_late")
        self.assertEqual(self.origin_main(), self.start)
        self.assertEqual(sh(self.origin, "branch", "--list", "autonomy/improve-*"), "")

    def test_kill_switches(self):
        for name in ("STOP_AUTONOMY", "STOP_QUEUE"):
            (self.work / name).write_text("", encoding="utf-8")
            self.assertEqual(self.go(), "halted", name)
            (self.work / name).unlink()
        self.assertEqual(self.origin_main(), self.start)

    def test_unstable_machine_makes_no_change(self):
        (self.work / "autonomy").mkdir(exist_ok=True)
        (self.work / im.LOG).write_text(f"- {(NOW - timedelta(days=1)).strftime('%Y-%m-%d %H:%M')} IST | improve | auto_revert | x | y\n", encoding="utf-8")
        self.assertEqual(self.go(), "unstable")
        (self.work / im.LOG).write_text(f"- {(NOW - timedelta(days=1)).strftime('%Y-%m-%d %H:%M')} IST | report | poster_runs_failing | x | y\n", encoding="utf-8")
        self.assertEqual(self.go(), "unstable")

    def test_no_idea_when_every_idea_is_blocked_or_unsafe(self):
        t = self.trends()
        t["topics"][0]["story_situation"] = "the best bat price offer"
        t["topics"][1]["expires"] = "2026-11-01"
        (self.work / "autonomy/trends.json").write_text(json.dumps(t), encoding="utf-8")
        self.assertEqual(self.go(), "no_idea")

    def test_dry_run_changes_nothing(self):
        self.assertEqual(self.go(dry=True), "dry")
        self.assertEqual(sh(self.work, "branch", "--list", "autonomy/improve-*"), "")
        self.assertEqual(self.origin_main(), self.start)


class Watch(Base):
    def merged(self):
        self.assertEqual(self.go(), "merged")
        return datetime.fromisoformat(self.watch()["merged_at"])

    def watch_run(self, hours=30, runs=None):
        return im.run(self.work, NOW + timedelta(hours=hours), self.git, FakeGH(), checks_ok, factory_runs=runs or [], watch_only=True)

    def test_two_clean_reels_keep_the_change(self):
        m = self.merged()
        self.put_queue([self.post("a", 5, merged=m), self.post("b", 10, merged=m)])
        self.assertEqual(self.watch_run(), "watch_ok")
        self.assertEqual(self.watch()["status"], "done")
        self.assertIn("a brother and sister", " ".join(self.situations()))

    def test_still_watching_until_two_reels_are_out(self):
        m = self.merged()
        self.put_queue([self.post("a", 5, merged=m)])
        self.assertEqual(self.watch_run(), "watching")
        self.assertEqual(self.watch()["status"], "watching")

    def test_a_new_failure_reverts_the_change_and_blocks_the_idea(self):
        m = self.merged()
        bad = {"youtube": {"ok": True}, "instagram": {"ok": False, "error": "Instagram processing ERROR: media upload failed", "tries": 1}, "facebook": {"ok": True}}
        self.put_queue([self.post("a", 5, merged=m), self.post("b", 10, results=bad, merged=m)])
        self.assertEqual(self.watch_run(), "reverted")
        self.assertEqual(self.situations(), json.loads(SITUATIONS)["situations"])                  # back to the original
        self.assertEqual(self.watch()["status"], "reverted")
        self.assertIn("instagram", self.watch()["reason"])
        self.assertEqual(self.origin_main(), sh(self.work, "rev-parse", "main"))                   # the revert is pushed
        self.assertIn("auto_revert", self.log())
        b = json.loads((self.work / im.BLOCKED).read_text(encoding="utf-8"))["ideas"]
        self.assertIn("situation:bhai_dooj_2026", b)
        self.assertEqual(b["situation:bhai_dooj_2026"], (NOW + timedelta(hours=30, days=14)).date().isoformat())
        self.assertTrue(sh(self.work, "log", "-1", "--format=%s", "HEAD").startswith("Autonomy"))

    def test_a_failure_that_was_already_there_is_not_new(self):
        flaky = {"youtube": {"ok": True}, "instagram": {"ok": False, "error": "request timeout", "tries": 1}, "facebook": {"ok": True}}
        self.put_queue([self.post("old1", -20, results=flaky), self.post("old2", -10, results=flaky)])
        sh(self.work, "add", "-A"); sh(self.work, "commit", "-q", "-m", "queue"); sh(self.work, "push", "-q", "origin", "main")
        self.start = sh(self.work, "rev-parse", "HEAD")
        m = self.merged()
        self.put_queue([self.post("old1", -20, results=flaky), self.post("old2", -10, results=flaky), self.post("a", 5, results=flaky, merged=m), self.post("b", 10, merged=m)])
        self.assertEqual(self.watch_run(), "watch_ok")
        self.assertIn("a brother and sister", " ".join(self.situations()))

    def test_a_failed_scheduled_factory_run_after_the_change_reverts(self):
        m = self.merged()
        runs = [{"id": 7, "conclusion": "failure", "event": "schedule", "created": m + timedelta(hours=3)},
                {"id": 6, "conclusion": "success", "event": "schedule", "created": m - timedelta(hours=20)}]
        self.assertEqual(self.watch_run(runs=runs), "reverted")
        self.assertIn("Reel Factory run 7", self.watch()["reason"])

    def test_a_test_run_failure_is_not_a_factory_failure(self):
        m = self.merged()
        runs = [{"id": 7, "conclusion": "failure", "event": "workflow_dispatch", "created": m + timedelta(hours=3)}]
        self.assertEqual(self.watch_run(runs=runs), "watching")

    def test_unsettled_reel_counts_after_three_hours(self):
        m = self.merged()
        half = {"youtube": {"ok": True}}
        self.put_queue([self.post("a", 5, results=half, merged=m)])
        self.assertEqual(self.watch_run(hours=5 + 1), "watching")
        self.assertEqual(self.watch_run(hours=5 + 4), "reverted")

    def test_gives_up_watching_after_five_days_without_failure(self):
        self.merged()
        self.assertEqual(self.watch_run(hours=24 * 6), "watch_ok")

    def test_revert_refuses_if_the_merge_touched_unexpected_files(self):
        self.merged()
        w = self.watch()
        w["files"] = ["something/else.json"]
        (self.work / im.WATCH).write_text(json.dumps(w), encoding="utf-8")
        bad = {"youtube": {"ok": False, "error": "x", "tries": 1}}
        self.put_queue([self.post("a", 5, results=bad, merged=datetime.fromisoformat(w["merged_at"]))])
        self.assertEqual(self.watch_run(), "revert_refused")
        self.assertIn("a brother and sister", " ".join(self.situations()))      # left as it is for the owner

    def test_revert_works_inside_a_blocked_window(self):
        m = self.merged()
        bad = {"youtube": {"ok": False, "error": "x", "tries": 1}}
        self.put_queue([self.post("a", 5, results=bad, merged=m)])
        out = im.run(self.work, NOW.replace(hour=12, minute=0) + timedelta(days=1), self.git, FakeGH(), checks_ok, factory_runs=[], watch_only=True)
        self.assertEqual(out, "reverted")


class Pieces(unittest.TestCase):
    def test_add_situation_changes_only_the_list(self):
        out = im.add_situation(SITUATIONS, "a new gali situation")
        a, b = json.loads(SITUATIONS), json.loads(out)
        self.assertEqual(b["situations"], a["situations"] + ["a new gali situation"])
        self.assertEqual({k: v for k, v in b.items() if k != "situations"}, {k: v for k, v in a.items() if k != "situations"})
        self.assertLessEqual(len(set(out.splitlines()) - set(SITUATIONS.splitlines())), 2)     # the new line + the previous line gaining a comma

    def test_qc_ok(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "output" / "ready" / "x").mkdir(parents=True)
            mf = Path(d) / "output" / "ready" / "x" / "manifest.json"
            mf.write_text(json.dumps([{"qc": 100}]), encoding="utf-8")
            self.assertTrue(im.qc_ok(Path(d), 100)[0])
            mf.write_text(json.dumps([{"qc": 100}, {"qc": 96}]), encoding="utf-8")
            self.assertFalse(im.qc_ok(Path(d), 100)[0])
            mf.write_text("[]", encoding="utf-8")
            self.assertFalse(im.qc_ok(Path(d), 100)[0])                                  # no reel, no pass

    def test_signatures(self):
        p = {"results": {"instagram": {"ok": False, "error": "Cannot call API token invalid"}, "youtube": {"ok": True}}, "notes": {"ig_comment": ["failed 400"], "fb_comment": ["ok"]}}
        self.assertEqual(im.signatures(p), {("instagram", "token"), ("ig_comment", "comment_failed")})

    def test_the_improver_code_never_edits_the_rules_or_workflows(self):
        src = (REPO / "autonomy" / "improve.py").read_text(encoding="utf-8")
        for w in ("RULES.json\", ", "guard.seal", "STOP_", ".github/", "poster/poster", "secrets."):
            self.assertNotIn(w, src, w)
        self.assertEqual(RULES["improve"]["improvers_enabled"], ["situation_from_trend"])
        self.assertEqual(g.classify("autonomy/improve.py", RULES)[0], "deny")
        self.assertEqual(g.classify("autonomy/watch.json", RULES)[0], "state")

    def test_situation_texts_pass_the_brand_rules(self):
        import trends as t
        for th in json.loads((REPO / "autonomy" / "trend_themes.json").read_text(encoding="utf-8"))["themes"] + json.loads((REPO / "autonomy" / "festivals.json").read_text(encoding="utf-8"))["days"]:
            s = th["situation"]
            self.assertTrue(t.is_safe_headline(s, RULES), s)
            self.assertLessEqual(len(s), 120, s)


if __name__ == "__main__":
    unittest.main()
