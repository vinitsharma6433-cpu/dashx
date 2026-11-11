"""Phase 2 tests: self-healing (autonomy/heal.py). No network, no GitHub: a fake API records what would be dispatched."""
import copy
import json
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "autonomy"))
import guard as g  # noqa: E402
import heal as h  # noqa: E402

RULES = g.load_rules()
NOW = datetime(2026, 11, 11, 15, 0, tzinfo=g.IST)


def run(id_, status="completed", concl="success", event="workflow_dispatch", ago_min=60):
    t = NOW - timedelta(minutes=ago_min)
    return {"id": id_, "status": status, "conclusion": concl, "event": event, "created": t, "updated": t}


def post(title="reel", when=None, nets=("youtube", "instagram", "facebook"), res=None, notes=None, status="scheduled", comments=True):
    return {"title": title, "media": f"https://x/{title}.mp4", "when": (when or NOW + timedelta(hours=5)).isoformat(),
            "networks": list(nets), "results": res or {}, "notes": notes or {}, "status": status, "comments": ["c"] if comments else []}


def snap(posts=None, runs=None, bank=20, usage=None, log="", stops=None, now=NOW):
    base = {"poster": [], "factory": [], "refill": []}
    base.update(runs or {})
    return h.Snap(now, base, posts if posts is not None else [], bank, usage or {"day": h.quota_day(now.astimezone(g.timezone.utc)), "calls": 0, "cap": 12}, h.quota_day(now.astimezone(g.timezone.utc)), log, stops or {})


class FakeAPI:
    def __init__(self, fail=False):
        self.sent, self.fail = [], fail

    def dispatch(self, wf, inputs, ref="main"):
        if self.fail:
            raise RuntimeError("boom")
        self.sent.append((wf, inputs))

    def runs(self, wf):
        return []


def names(acts):
    return [a.name for a in acts]


class DeadPoster(unittest.TestCase):
    P = [post()]

    def test_dead_loop_is_redispatched(self):
        a = h.plan(snap(self.P, {"poster": [run(1, ago_min=45)]}), RULES)
        self.assertEqual(names(a), ["poster_redispatch"])
        self.assertEqual(a[0].workflow, "dashx-poster.yml")

    def test_running_loop_is_left_alone(self):
        self.assertEqual(h.plan(snap(self.P, {"poster": [run(1, "in_progress", None, ago_min=5)]}), RULES), [])
        self.assertEqual(h.plan(snap(self.P, {"poster": [run(1, "queued", None, ago_min=1)]}), RULES), [])

    def test_a_just_finished_run_gets_a_grace_period(self):
        self.assertEqual(h.plan(snap(self.P, {"poster": [run(1, ago_min=5)]}), RULES), [])

    def test_max_two_per_hour(self):
        line = lambda m: f"- {(NOW - timedelta(minutes=m)).strftime('%Y-%m-%d %H:%M')} IST | fix | poster_redispatch | why | dispatched\n"
        a = h.plan(snap(self.P, {"poster": [run(1, ago_min=60)]}, log=line(10) + line(40)), RULES)
        self.assertEqual(names(a), ["poster_redispatch_limit"])
        self.assertEqual(a[0].kind, "report")
        a = h.plan(snap(self.P, {"poster": [run(1, ago_min=60)]}, log=line(10) + line(90)), RULES)   # one in the last hour: still allowed
        self.assertEqual(names(a), ["poster_redispatch"])

    def test_nothing_waiting_means_no_dispatch(self):
        done = post(status="done", when=NOW - timedelta(hours=3), res={n: {"ok": True} for n in ("youtube", "instagram", "facebook")})
        self.assertEqual(h.plan(snap([done], {"poster": [run(1, ago_min=90)]}), RULES), [])
        far = post(when=NOW + timedelta(hours=60))
        self.assertEqual(h.plan(snap([far], {"poster": [run(1, ago_min=90)]}), RULES), [])

    def test_stop_poster_wins(self):
        self.assertEqual(h.plan(snap(self.P, {"poster": [run(1, ago_min=90)]}, stops={"poster": "STOP_POSTER"}), RULES), [])

    def test_poster_gave_up_on_purpose_is_not_a_reason(self):
        gave_up = post(when=NOW - timedelta(hours=1), nets=("instagram",), res={"instagram": {"ok": False, "tries": 3, "error": "x"}})
        self.assertEqual(h.plan(snap([gave_up], {"poster": [run(1, ago_min=90)]}), RULES) and [x for x in h.plan(snap([gave_up], {"poster": [run(1, ago_min=90)]}), RULES) if x.name == "poster_redispatch"], [])


class NetworkRetry(unittest.TestCase):
    def failed(self, **kw):
        res = {"youtube": {"ok": True}, "facebook": {"ok": False, "tries": 3, "error": "Graph timeout"}}
        res.update(kw.pop("res", {}))
        return post(when=NOW - timedelta(hours=2), res=res, notes=kw.pop("notes", {}), nets=("youtube", "facebook"))

    def test_one_failed_network_is_retried_once(self):
        p = self.failed()
        a = h.plan(snap([p]), RULES)
        self.assertIn("network_retry", names(a))

    def test_duplicate_guard_blocks_a_possibly_live_post(self):
        for notes in ({"fb_video_id": "123"}, {"fb_status": "published"}):
            a = h.plan(snap([self.failed(notes=notes)]), RULES)
            self.assertNotIn("network_retry", names(a), notes)
            self.assertIn("network_failed", names(a), notes)
        a = h.plan(snap([self.failed(res={"facebook": {"ok": False, "tries": 3, "link": "https://fb/x", "error": "e"}})]), RULES)
        self.assertNotIn("network_retry", names(a))

    def test_not_twice(self):
        a = h.plan(snap([self.failed(notes={"heal_retry_facebook": "2026-11-11T10:00:00+05:30"})]), RULES)
        self.assertNotIn("network_retry", names(a))

    def test_token_problem_is_reported_not_retried(self):
        a = h.plan(snap([self.failed(res={"facebook": {"ok": False, "tries": 3, "error": "Cannot call API for app (code 200)"}})]), RULES)
        self.assertNotIn("network_retry", names(a))
        self.assertIn("token_or_permission", names(a))

    def test_too_old_is_not_retried(self):
        old = post(when=NOW - timedelta(hours=45), nets=("facebook",), res={"facebook": {"ok": False, "tries": 3, "error": "x"}})
        self.assertEqual([x for x in h.plan(snap([old]), RULES) if x.name == "network_retry"], [])

    def test_execute_clears_only_that_network_and_marks_it(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "poster").mkdir()
            other = post("other", res={"youtube": {"ok": True}})
            p = self.failed()
            (root / "poster" / "queue.json").write_text(json.dumps({"posts": [other, p]}), encoding="utf-8")
            s = snap([p])
            out = h.execute(h.plan(s, RULES), s, RULES, FakeAPI(), root=root)
            q = json.loads((root / "poster" / "queue.json").read_text(encoding="utf-8"))["posts"]
            self.assertEqual(q[1]["results"]["facebook"], {})
            self.assertTrue(q[1]["results"]["youtube"]["ok"])           # untouched
            self.assertIn("heal_retry_facebook", q[1]["notes"])
            self.assertEqual(q[0], other)                                # other posts untouched
            self.assertIn("| fix | network_retry |", (root / "autonomy" / "log.md").read_text(encoding="utf-8"))
            self.assertTrue(out)
            # the guard is checked AGAIN at write time: after the mark, a second execute must not clear it
            q[1]["results"]["facebook"] = {"ok": False, "tries": 3, "error": "again"}
            (root / "poster" / "queue.json").write_text(json.dumps({"posts": q}), encoding="utf-8")
            h.execute(h.plan(s, RULES), s, RULES, FakeAPI(), root=root)
            q2 = json.loads((root / "poster" / "queue.json").read_text(encoding="utf-8"))["posts"]
            self.assertEqual(q2[1]["results"]["facebook"]["tries"], 3)


class MissingComment(unittest.TestCase):
    def ig(self, **notes):
        n = {"ig_media_id": "99", "ig_comment": ["failed 400"]}
        n.update(notes)
        return post(when=NOW - timedelta(hours=3), nets=("instagram",), status="done",
                    res={"instagram": {"ok": True, "link": "https://ig/x", "at": (NOW - timedelta(hours=3)).isoformat()}}, notes=n)

    def test_missing_comment_is_backfilled(self):
        self.assertIn("comment_backfill", names(h.plan(snap([self.ig()]), RULES)))

    def test_ok_comment_is_left(self):
        self.assertNotIn("comment_backfill", names(h.plan(snap([self.ig(ig_comment=["ok"])]), RULES)))

    def test_max_two_tries(self):
        self.assertNotIn("comment_backfill", names(h.plan(snap([self.ig(heal_comment_ig=2)]), RULES)))

    def test_old_posts_are_not_touched(self):
        old = self.ig()
        old["when"] = (NOW - timedelta(days=5)).isoformat()
        old["results"]["instagram"]["at"] = old["when"]
        self.assertNotIn("comment_backfill", names(h.plan(snap([old]), RULES)))

    def test_facebook_waits_while_the_poster_is_still_retrying(self):
        fb = post(when=NOW - timedelta(hours=3), nets=("facebook",), res={"facebook": {"ok": True, "scheduled": True, "at": (NOW - timedelta(hours=5)).isoformat()}},
                  notes={"fb_video_id": "7", "fb_comment_tries": 2})
        self.assertNotIn("comment_backfill", names(h.plan(snap([fb]), RULES)))
        fb["notes"]["fb_comment_tries"] = 5
        self.assertIn("comment_backfill", names(h.plan(snap([fb]), RULES)))

    def test_execute_counts_tries_and_calls_backfill_for_that_post_only(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "poster").mkdir()
            p = self.ig()
            (root / "poster" / "queue.json").write_text(json.dumps({"posts": [p]}), encoding="utf-8")
            calls = []
            s = snap([p])
            h.execute(h.plan(s, RULES), s, RULES, FakeAPI(), root=root, comment_fn=lambda post_, net: calls.append((post_["title"], net)) or True)
            self.assertEqual(calls, [("reel", "instagram")])
            q = json.loads((root / "poster" / "queue.json").read_text(encoding="utf-8"))["posts"][0]
            self.assertEqual(q["notes"]["heal_comment_ig"], 1)


class FactoryAndBank(unittest.TestCase):
    def test_failed_scheduled_factory_is_redispatched_once(self):
        fr = [run(50, concl="failure", event="schedule", ago_min=200)]
        ps = [post(when=NOW + timedelta(hours=5), status="done")]       # nothing for the poster to do: only the factory problem remains
        a = h.plan(snap(ps, {"factory": fr}), RULES)
        self.assertEqual(names(a), ["factory_redispatch"])
        self.assertEqual(a[0].inputs, {"count": "2", "test_only": "false"})
        again = f"- {NOW.strftime('%Y-%m-%d %H:%M')} IST | fix | factory_redispatch | why [50] | dispatched\n"
        self.assertEqual(h.plan(snap(ps, {"factory": fr}, log=again), RULES), [])

    def test_manual_or_test_run_failures_do_not_trigger_a_real_run(self):
        self.assertEqual(h.plan(snap([], {"factory": [run(51, concl="failure", event="workflow_dispatch")]}), RULES), [])

    def test_enough_reels_queued_means_no_redispatch(self):
        ps = [post(f"r{i}", when=NOW + timedelta(hours=5 + i)) for i in range(3)]
        self.assertEqual([x for x in h.plan(snap(ps, {"factory": [run(52, concl="failure", event="schedule")]}), RULES) if x.name == "factory_redispatch"], [])

    def test_later_success_means_no_redispatch(self):
        fr = [run(54, concl="success", event="schedule", ago_min=30), run(53, concl="failure", event="schedule", ago_min=200)]
        self.assertEqual(h.plan(snap([], {"factory": fr}), RULES), [])

    def test_stop_queue_stops_factory_heal(self):
        self.assertEqual(h.plan(snap([], {"factory": [run(55, concl="failure", event="schedule")]}, stops={"self_change": "STOP_QUEUE"}), RULES), [])

    def test_low_bank_triggers_refill_inside_the_quota(self):
        a = h.plan(snap(bank=3), RULES)
        self.assertEqual(names(a), ["refill_dispatch"])
        self.assertEqual(a[0].inputs, {"target": "2", "max_calls": "12", "dry_run": "false"})

    def test_no_refill_when_quota_is_used(self):
        a = h.plan(snap(bank=3, usage={"day": h.quota_day(NOW.astimezone(g.timezone.utc)), "calls": 11, "cap": 12}), RULES)
        self.assertEqual(names(a), ["low_bank_no_quota"])

    def test_yesterdays_calls_do_not_count(self):
        a = h.plan(snap(bank=3, usage={"day": "2000-01-01", "calls": 12, "cap": 12}), RULES)
        self.assertEqual(names(a), ["refill_dispatch"])

    def test_refill_once_per_quota_day_and_not_while_busy(self):
        qd = h.quota_day(NOW.astimezone(g.timezone.utc))
        tagged = f"- {NOW.strftime('%Y-%m-%d %H:%M')} IST | fix | refill_dispatch | why [{qd}] | dispatched\n"
        self.assertEqual(h.plan(snap(bank=3, log=tagged), RULES), [])
        self.assertEqual(h.plan(snap(bank=3, runs={"refill": [run(9, "in_progress", None, ago_min=2)]}), RULES), [])
        self.assertEqual(h.plan(snap(bank=3, runs={"refill": [run(9, ago_min=120)]}), RULES), [])    # ran 2 h ago

    def test_healthy_bank_and_unknown_bank_do_nothing(self):
        self.assertEqual(h.plan(snap(bank=21), RULES), [])
        self.assertEqual(h.plan(snap(bank=None), RULES), [])

    def test_stop_refill_wins(self):
        self.assertEqual(h.plan(snap(bank=3, stops={"refill": "STOP_REFILL"}), RULES), [])


class DuplicateGuard(unittest.TestCase):
    def test_finds_duplicates(self):
        a, b = post("a"), post("b")
        b["when"] = a["when"]
        self.assertTrue(any("share one slot" in x for x in h.duplicates([a, b], NOW)))
        c = post("c"); d = post("d"); d["media"] = c["media"]
        self.assertTrue(any("same media" in x for x in h.duplicates([c, d], NOW)))
        e = post("e", res={"youtube": {"link": "L"}}); f = post("f", res={"youtube": {"link": "L"}})
        self.assertTrue(any("link used by two" in x for x in h.duplicates([e, f], NOW)))

    def test_old_history_is_ignored(self):
        a, b = post("a", when=NOW - timedelta(days=30)), post("b", when=NOW - timedelta(days=30))
        b["media"] = a["media"]
        self.assertEqual(h.duplicates([a, b], NOW), [])

    def test_retry_safe_cases(self):
        self.assertTrue(h.retry_safe(post(res={"facebook": {"ok": False, "tries": 3, "error": "timeout"}}), "facebook")[0])
        self.assertFalse(h.retry_safe(post(res={"instagram": {"ok": True}}), "instagram")[0])
        self.assertFalse(h.retry_safe(post(notes={"ig_media_id": "1"}, res={"instagram": {"ok": False}}), "instagram")[0])


class ExecuteRules(unittest.TestCase):
    def test_other_workflows_are_refused(self):
        with tempfile.TemporaryDirectory() as d:
            api = FakeAPI()
            s = snap()
            h.execute([h.Action("dispatch", "x", "why", "hf-ad.yml")], s, RULES, api, root=Path(d))
            self.assertEqual(api.sent, [])
            self.assertIn("REFUSED", (Path(d) / "autonomy" / "log.md").read_text(encoding="utf-8"))

    def test_dispatch_failure_is_logged_not_raised(self):
        with tempfile.TemporaryDirectory() as d:
            s = snap()
            h.execute([h.Action("dispatch", "poster_redispatch", "why", "dashx-poster.yml")], s, RULES, FakeAPI(fail=True), root=Path(d))
            self.assertIn("dispatch failed", (Path(d) / "autonomy" / "log.md").read_text(encoding="utf-8"))

    def test_every_fix_is_logged_and_reports_are_not_repeated_in_a_day(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            s = snap()
            api = FakeAPI()
            h.execute([h.Action("dispatch", "poster_redispatch", "dead", "dashx-poster.yml")], s, RULES, api, root=root)
            self.assertEqual(api.sent[0][0], "dashx-poster.yml")
            rep = [h.Action("report", "token_or_permission", "needs owner")]
            h.execute(rep, s, RULES, api, root=root)
            s2 = snap(log=(root / "autonomy" / "log.md").read_text(encoding="utf-8"))
            h.execute(rep, s2, RULES, api, root=root)
            text = (root / "autonomy" / "log.md").read_text(encoding="utf-8")
            self.assertEqual(text.count("| report | token_or_permission |"), 1)
            self.assertEqual(text.count("| fix | poster_redispatch |"), 1)

    def test_dry_run_writes_nothing_and_dispatches_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            api = FakeAPI()
            out = h.execute([h.Action("dispatch", "poster_redispatch", "dead", "dashx-poster.yml")], snap(), RULES, api, root=Path(d), dry=True)
            self.assertEqual(api.sent, [])
            self.assertFalse((Path(d) / "autonomy").exists())
            self.assertTrue(out[0].startswith("WOULD"))

    def test_healing_can_only_write_the_two_listed_files(self):
        self.assertEqual(RULES["healing"]["may_write"], ["poster/queue.json", "autonomy/log.md"])
        self.assertTrue(h._may_write("poster/queue.json", RULES))
        for p in ("poster/poster.py", "poster/loop.sh", ".github/workflows/dashx-poster.yml", "autonomy/RULES.json", "autonomy/guard.py", "STOP_POSTER", "../x"):
            self.assertFalse(h._may_write(p, RULES), p)

    def test_the_real_rules_and_workflows_are_never_touched_by_a_run(self):
        before = {p: p.read_bytes() for p in [REPO / "autonomy" / "RULES.json", REPO / "autonomy" / "RULES.sha256", REPO / "autonomy" / "guard.py"]
                  + list((REPO / ".github" / "workflows").glob("*.yml")) + list((REPO / "poster").glob("*.py")) + [REPO / "poster" / "loop.sh"]}
        with tempfile.TemporaryDirectory() as d:
            s = snap([post()], {"poster": [run(1, ago_min=90)]}, bank=2)
            h.execute(h.plan(s, RULES), s, RULES, FakeAPI(), root=Path(d))
        self.assertEqual(before, {p: p.read_bytes() for p in before})

    def test_main_stops_on_kill_switch_without_touching_github(self):
        class Boom:
            def __init__(self, *a, **k): raise AssertionError("GitHub must not be called")
        old, oldh = h.GitHub, g.halted
        try:
            h.GitHub = Boom
            g.halted = lambda scope="all", root=g.ROOT: "STOP_AUTONOMY"
            self.assertEqual(h.main([]), 0)
        finally:
            h.GitHub, g.halted = old, oldh

    def test_main_stops_when_rules_are_tampered(self):
        oldl = g.load_rules
        try:
            def bad(*a, **k): raise g.RulesTampered("x")
            g.load_rules = bad
            self.assertEqual(h.main(["--dry"]), 1)
        finally:
            g.load_rules = oldl

    def test_never_list_things_do_not_exist_in_heal(self):
        src = (REPO / "autonomy" / "heal.py").read_text(encoding="utf-8").lower()
        for word in ("like(", "follow", "/messages", "scrape", "selenium", "cookie", "subprocess", "os.system", "chrome"):
            self.assertNotIn(word, src, word)


if __name__ == "__main__":
    unittest.main()
