"""The Trust Ladder: moves up only at a met gate (with evidence in the log), drops one step on a missed slot / Meta warning / harmful revert,
never loosens the permanent DENY list, and is shown in the daily report."""
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "autonomy"))
import alerts  # noqa: E402
import guard  # noqa: E402
import improve  # noqa: E402
import ladder  # noqa: E402
import report  # noqa: E402

IST = guard.IST
T0 = datetime(2026, 11, 14, 21, 0, tzinfo=IST)


def post(title, when, ok=True, nets=("youtube", "instagram", "facebook"), results=None):
    res = results if results is not None else {n: {"ok": ok} for n in nets}
    return {"title": f"{title} DASHX", "when": when.isoformat(), "networks": list(nets), "results": res, "status": "done"}


def step1_started(now=T0):
    st, lines = ladder.evaluate(ladder.new_state(), [], "", {}, now, True, True)
    return st, lines


def at_step(step, since, first=None):
    st = ladder.new_state()
    st["first_run"] = (first or since).isoformat(timespec="minutes")
    st["step"], st["step_since"] = step, since.isoformat(timespec="minutes")
    st["history"] = [{"at": since.isoformat(timespec="minutes"), "from": s, "to": s + 1, "why": "t"} for s in range(1, step)]
    return st


class Up(unittest.TestCase):
    def test_first_run_is_logged_and_step_stays_1(self):
        st, lines = step1_started()
        self.assertEqual(st["step"], 1)
        self.assertEqual(st["first_run"], T0.isoformat(timespec="minutes"))
        self.assertIn("| ladder | start |", lines[0])
        self.assertEqual(st["progress"], "0 of 2 clean reels after the first run")

    def test_two_clean_reels_after_the_first_run_move_to_step_2_with_evidence(self):
        st, _ = step1_started()
        posts = [post("A", T0 + timedelta(hours=3)), post("B", T0 + timedelta(hours=15))]
        now = T0 + timedelta(hours=16)
        st, lines = ladder.evaluate(st, posts, "", {}, now, True, True)
        self.assertEqual(st["step"], 2)
        self.assertTrue(any("| ladder | step_up | 1->2 |" in l and "A, B" in l for l in lines), lines)
        self.assertEqual(st["progress"], "0 of 7 days")

    def test_reels_from_before_the_first_run_do_not_count(self):
        st, _ = step1_started()
        posts = [post("old1", T0 - timedelta(hours=10)), post("old2", T0 - timedelta(hours=30))]
        st, _ = ladder.evaluate(st, posts, "", {}, T0 + timedelta(hours=5), True, True)
        self.assertEqual(st["step"], 1)

    def test_one_clean_reel_is_not_enough_and_a_new_failure_restarts_the_count(self):
        st, _ = step1_started()
        posts = [post("A", T0 + timedelta(hours=3)), post("B", T0 + timedelta(hours=15), results={"youtube": {"ok": True}, "instagram": {"ok": False, "error": "x"}, "facebook": {"ok": True}})]
        st, _ = ladder.evaluate(st, posts, "", {}, T0 + timedelta(hours=16), True, True)
        self.assertEqual(st["step"], 1)
        self.assertIn("failure or duplicate", st["blocker"])
        posts.append(post("C", T0 + timedelta(hours=27)))
        st, _ = ladder.evaluate(st, posts, "", {}, T0 + timedelta(hours=28), True, True)
        self.assertEqual(st["step"], 1)                                 # only one clean reel after the failure
        posts.append(post("D", T0 + timedelta(hours=39)))
        st, _ = ladder.evaluate(st, posts, "", {}, T0 + timedelta(hours=40), True, True)
        self.assertEqual(st["step"], 2)

    def test_a_duplicate_post_blocks_the_gate(self):
        st, _ = step1_started()
        posts = [post("A", T0 + timedelta(hours=3)), post("A", T0 + timedelta(hours=4)), post("B", T0 + timedelta(hours=15))]
        st, _ = ladder.evaluate(st, posts, "", {}, T0 + timedelta(hours=16), True, True)
        self.assertEqual(st["step"], 1)

    def test_step_2_needs_7_days_and_shows_progress(self):
        st = at_step(2, T0)
        st, _ = ladder.evaluate(st, [], "", {}, T0 + timedelta(days=3, hours=2), True, True)
        self.assertEqual((st["step"], st["progress"]), (2, "3 of 7 days"))
        st, lines = ladder.evaluate(st, [], "", {}, T0 + timedelta(days=7), True, True)
        self.assertEqual(st["step"], 3)
        self.assertTrue(any("step_up | 2->3" in l and "7 days" in l for l in lines))

    def test_step_3_never_moves_to_4_by_itself(self):
        st = at_step(3, T0)
        for days in (30, 60, 400):
            st, _ = ladder.evaluate(st, [], "", {"views_trend": 5}, T0 + timedelta(days=days), True, True)
            self.assertEqual(st["step"], 3)
        self.assertTrue(st["owner_ready"])
        self.assertIn("owner's yes in chat", st["blocker"])
        st, _ = ladder.evaluate(st, [], "", {}, T0 + timedelta(days=40), True, True)
        self.assertIn("not measurable", st["blocker"])                 # missing views data never counts as fine
        self.assertFalse(st["owner_ready"])

    def test_one_step_per_evaluation(self):
        st = at_step(1, T0 - timedelta(days=20))
        st["first_run"] = (T0 - timedelta(days=20)).isoformat()
        posts = [post("A", T0 - timedelta(days=19)), post("B", T0 - timedelta(days=18))]
        st, _ = ladder.evaluate(st, posts, "", {}, T0, True, True)
        self.assertEqual(st["step"], 2)                                  # not 3, although 20 days have passed


class Drop(unittest.TestCase):
    def _drop(self, st, posts, log_text, now):
        st, lines = ladder.evaluate(st, posts, log_text, {}, now, True, True)
        return st, lines

    def test_missed_slot_drops_one_step_and_raises_an_alert(self):
        st = at_step(3, T0 - timedelta(days=10))
        posts = [post("Gone", T0 - timedelta(hours=3), results={})]
        st, lines = self._drop(st, posts, "", T0)
        self.assertEqual(st["step"], 2)
        self.assertTrue(any("| ladder | drop | 3->2 |" in l and "missed slot" in l and "DASHX ALERT raised" in l for l in lines), lines)
        s = alerts.Signals(T0, posts, ladder=st)
        self.assertIn("LADDER_DROP", [p.id for p in alerts.detect(s)])
        self.assertEqual(alerts.level(s, alerts.detect(s))[0], "red")
        self.assertEqual(st["progress"], "0 of 7 days")                  # the gate restarts on the lower step

    def test_missed_slot_is_not_counted_twice(self):
        st = at_step(3, T0 - timedelta(days=10))
        posts = [post("Gone", T0 - timedelta(hours=3), results={})]
        st, _ = self._drop(st, posts, "", T0)
        st, lines = self._drop(st, posts, "", T0 + timedelta(hours=1))
        self.assertEqual(st["step"], 2)
        self.assertEqual(lines, [])

    def test_a_slot_only_a_few_minutes_late_is_not_missed(self):
        st = at_step(2, T0 - timedelta(days=2))
        posts = [post("Late", T0 - timedelta(minutes=40), results={})]
        st, _ = self._drop(st, posts, "", T0)
        self.assertEqual(st["step"], 2)

    def test_meta_warning_drops_one_step(self):
        st = at_step(2, T0 - timedelta(days=2))
        posts = [post("W", T0 - timedelta(hours=3), results={"youtube": {"ok": True}, "facebook": {"ok": False, "error": "Your account is restricted: community guidelines"}, "instagram": {"ok": True}})]
        st, lines = self._drop(st, posts, "", T0)
        self.assertEqual(st["step"], 1)
        self.assertTrue(any("Meta warning" in l for l in lines))

    def test_harmful_revert_drops_one_step(self):
        st = at_step(2, T0 - timedelta(days=2))
        log_text = f"- {(T0 - timedelta(hours=2)).strftime('%Y-%m-%d %H:%M')} IST | improve | auto_revert | add the trend situation x | new failure\n"
        st, lines = self._drop(st, [], log_text, T0)
        self.assertEqual(st["step"], 1)
        self.assertTrue(any("harmful revert" in l for l in lines))

    def test_an_old_revert_from_before_this_step_does_not_count(self):
        st = at_step(2, T0 - timedelta(days=2))
        log_text = f"- {(T0 - timedelta(days=5)).strftime('%Y-%m-%d %H:%M')} IST | improve | auto_revert | x | y\n"
        st, _ = self._drop(st, [], log_text, T0)
        self.assertEqual(st["step"], 2)

    def test_the_floor_is_step_1_but_the_alert_is_still_raised(self):
        st = at_step(1, T0 - timedelta(days=1))
        st, lines = self._drop(st, [post("Gone", T0 - timedelta(hours=3), results={})], "", T0)
        self.assertEqual(st["step"], 1)
        self.assertTrue(any("stays at 1" in l and "ALERT" in l for l in lines))
        self.assertIsNotNone(st["drop_alert_until"])

    def test_the_drop_alert_closes_after_7_days(self):
        st = at_step(2, T0 - timedelta(days=2))
        st, _ = self._drop(st, [post("Gone", T0 - timedelta(hours=3), results={})], "", T0)
        self.assertIn("LADDER_DROP", [p.id for p in alerts.detect(alerts.Signals(T0 + timedelta(days=6), [], ladder=st))])
        self.assertNotIn("LADDER_DROP", [p.id for p in alerts.detect(alerts.Signals(T0 + timedelta(days=8), [], ladder=st))])


class Safe(unittest.TestCase):
    def test_bad_state_means_step_1(self):
        for bad in ({"step": 4, "history": []}, {"step": 3, "history": []}, {"step": 2, "history": [{"to": 3}]}, {"step": "2"}, "x", None):
            with tempfile.TemporaryDirectory() as d:
                (Path(d) / "autonomy").mkdir()
                (Path(d) / "autonomy/TRUST_LADDER.md").write_bytes((REPO / "autonomy/TRUST_LADDER.md").read_bytes())
                (Path(d) / "autonomy/status.json").write_text(json.dumps({"ladder": bad}), encoding="utf-8")
                self.assertEqual(ladder.current_step(Path(d)), 1, bad)

    def test_a_valid_step_2_is_honoured_and_a_changed_ladder_file_freezes_it(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "autonomy").mkdir()
            (root / "autonomy/TRUST_LADDER.md").write_bytes((REPO / "autonomy/TRUST_LADDER.md").read_bytes())
            (root / "autonomy/status.json").write_text(json.dumps({"ladder": at_step(2, T0)}), encoding="utf-8")
            self.assertEqual(ladder.current_step(root), 2)
            (root / "autonomy/TRUST_LADDER.md").write_text("Step 1 - everything ON\n", encoding="utf-8")
            self.assertEqual(ladder.current_step(root), 1)
            s = alerts.load_signals(root, T0)
            self.assertIn("LADDER_FILE", [p.id for p in alerts.detect(s)])
            st, lines = ladder.evaluate(at_step(2, T0), [], "", {}, T0, True, False, "changed")
            self.assertEqual(st["step"], 1)
            self.assertTrue(any("frozen" in l for l in lines))

    def test_a_stop_file_holds_the_machine_at_step_1(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "autonomy").mkdir()
            (root / "autonomy/TRUST_LADDER.md").write_bytes((REPO / "autonomy/TRUST_LADDER.md").read_bytes())
            (root / "autonomy/status.json").write_text(json.dumps({"ladder": at_step(2, T0)}), encoding="utf-8")
            (root / "STOP_AUTONOMY").write_text("", encoding="utf-8")
            self.assertEqual(ladder.current_step(root), 1)

    def test_self_improvement_is_off_on_step_1_and_on_from_step_2(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "autonomy").mkdir()
            (root / "autonomy/TRUST_LADDER.md").write_bytes((REPO / "autonomy/TRUST_LADDER.md").read_bytes())
            self.assertEqual(improve.run(root, T0, git=object()), "ladder_step1")
            self.assertIn("ladder | self-improvement is OFF", (root / "autonomy/log.md").read_text(encoding="utf-8"))
            (root / "autonomy/status.json").write_text(json.dumps({"ladder": at_step(2, T0)}), encoding="utf-8")
            with mock.patch.object(improve, "improve_step", return_value="went_on"):
                self.assertEqual(improve.run(root, T0, git=object()), "went_on")
            with mock.patch.object(improve, "improve_step", return_value="went_on"):          # watching an existing change is never blocked by the ladder
                (root / "autonomy/status.json").write_text(json.dumps({"ladder": new_ladder_1()}), encoding="utf-8")
                self.assertEqual(improve.run(root, T0, git=object(), watch_only=True), "idle")


def new_ladder_1():
    return ladder.new_state()


class Rules(unittest.TestCase):
    def test_the_ladder_file_is_protected_and_sealed(self):
        rules = guard.load_rules()                                          # the seal verifies
        self.assertEqual(guard.classify("autonomy/TRUST_LADDER.md", rules)[0], "deny")
        for variant in ("AUTONOMY/trust_ladder.md", "autonomy\\TRUST_LADDER.md", "autonomy/x/../TRUST_LADDER.md", "autonomy/TRUST_LADDER.md."):
            self.assertEqual(guard.classify(variant, rules)[0], "deny", variant)
        self.assertIn("autonomy/TRUST_LADDER.md", rules["deny"]["paths"])
        self.assertTrue(ladder.ladder_file_ok(REPO)[0])
        self.assertNotIn("autonomy/TRUST_LADDER.md", rules["state_files"]["paths"])

    def test_the_permanent_deny_list_was_not_loosened(self):
        rules = guard.load_rules()
        required = {"autonomy/RULES.json", "autonomy/RULES.sha256", "autonomy/guard.py", ".github/**", "poster/**", "STOP_*", "reelfactory/STOP_*", "**/STOP_*", "**/.env", "**/*secret*",
                    "**/*token*", "**/*credential*", "**/*.pem", "**/*.key", "reelfactory/factory/youtube.py", "reelfactory/factory/queue.py", "reelfactory/queue_config.json",
                    "reelfactory/factory/qc.py", "reelfactory/voices.json"}
        self.assertTrue(required <= set(rules["deny"]["paths"]))
        for p in ("poster/queue.py", "reelfactory/queue_config.json", ".github/workflows/dashx-poster.yml", "reelfactory/factory/youtube.py", "reelfactory/factory/qc.py", "reelfactory/voices.json", "autonomy/guard.py", "autonomy/ladder.py"):
            self.assertEqual(guard.classify(p, rules)[0], "deny", p)
        for p in ("reelfactory/scripts/refill_bank.py", "reelfactory/scripts/story_rules.py"):         # the two not-yet-approved ALLOW items stay off
            self.assertNotEqual(guard.classify(p, rules)[0], "allow", p)

    def test_no_module_writes_the_ladder_file(self):
        for f in (REPO / "autonomy").glob("*.py"):
            src = f.read_text(encoding="utf-8")
            if f.name in ("simulate.py", "simulate_scout.py"):
                continue
            self.assertNotIn("TRUST_LADDER.md\").write", src, f.name)
            self.assertNotRegex(src, r"(write_text|write_bytes|open)\([^)]*TRUST_LADDER", f.name)

    def test_the_ladder_file_text_matches_the_gates_in_the_code(self):
        t = (REPO / "autonomy/TRUST_LADDER.md").read_text(encoding="utf-8")
        self.assertIn("2 reels posted cleanly", t)
        self.assertIn(f"{ladder.DAYS[2]} days", t)
        self.assertIn(f"{ladder.DAYS[3]} days", t)
        self.assertIn("Step 4", t)


class Report(unittest.TestCase):
    def test_the_daily_report_shows_step_progress_and_blocker(self):
        st = at_step(2, T0 - timedelta(days=3))
        st, _ = ladder.evaluate(st, [], "", {}, T0, True, True)
        txt = report.build(alerts.Signals(T0, [], ladder=st))
        self.assertIn("### Trust Ladder", txt)
        self.assertIn("Step 2 - Careful self-improvement", txt)
        self.assertIn("3 of 7 days", txt)
        self.assertIn("Blocker: none", txt)

    def test_the_report_shows_a_blocker_and_the_drop(self):
        st = at_step(2, T0 - timedelta(days=3))
        st, _ = ladder.evaluate(st, [post("Gone", T0 - timedelta(hours=3), results={})], "", {}, T0, True, True)
        txt = report.build(alerts.Signals(T0, [post("Gone", T0 - timedelta(hours=3), results={})], ladder=st))
        self.assertIn("Step 1 - Watch", txt)
        self.assertIn("DROPPED a step recently", txt)
        self.assertIn("Machine ek Trust Ladder step neeche aa gayi", txt)

    def test_step_1_report_shows_the_clean_reel_gate(self):
        st, _ = step1_started()
        txt = report.build(alerts.Signals(T0, [], ladder=st))
        self.assertIn("0 of 2 clean reels after the first run", txt)
        self.assertIn("Gate to Step 2", txt)


class EndToEnd(unittest.TestCase):
    def test_alerts_run_writes_the_state_and_the_log_once(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "autonomy").mkdir()
            (root / "poster").mkdir()
            (root / "autonomy/TRUST_LADDER.md").write_bytes((REPO / "autonomy/TRUST_LADDER.md").read_bytes())
            (root / "poster/queue.json").write_text(json.dumps({"posts": []}), encoding="utf-8")
            out = alerts.run(root, T0, api=None)
            st = json.loads((root / "autonomy/status.json").read_text(encoding="utf-8"))
            self.assertEqual(st["ladder"]["step"], 1)
            self.assertEqual(st["ladder"]["first_run"], T0.isoformat(timespec="minutes"))
            log1 = (root / "autonomy/log.md").read_text(encoding="utf-8")
            self.assertEqual(log1.count("| ladder | start |"), 1)
            alerts.run(root, T0 + timedelta(minutes=30), api=None)
            self.assertEqual((root / "autonomy/log.md").read_text(encoding="utf-8").count("| ladder | start |"), 1)
            self.assertIn("level", out)


if __name__ == "__main__":
    unittest.main()
