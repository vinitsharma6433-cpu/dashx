"""Patch A (grade stop reason + dry-run grading that saves nothing) and patch C (3 weak stories held out of picking through the existing
used.md mechanism). Patch B (a daily Bruno-series quota) is NOT part of this change. All Gemini calls are mocked."""
import argparse
import json
import random
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent / "autonomy"))
import refill_bank as rb  # noqa: E402

BANK0 = "# bank\n\n## Alpha | अ\nplot: p\nending: e!\n\n## Beta | ब\nplot: p\nending: e!\n"
GOOD = (True, {"meerut_feel": 8, "twist": 7, "funny": 8, "natural_hindi": 8, "kid_safe": True, "typos": [], "issue": "ok"})
SERIES_STORY = """## Bruno Files Test {n} | ब्रूनो फ़ाइल्स {n}
plot: Bruno finds a clue.
ending: केस खुला!
hook: क्या मिला? 🐾
card: नया सुराग!
series: Bruno Files
ep: {ep}
- face-off | sachin | bruno | x | sachin: ब्रूनो, ये क्या है!
- run-up | surya | sachin | | surya: देखो!
- shot | sachin | bruno | | sachin: चलो!
- face-off | sachin | bruno | y | sachin: अब क्या होगा?
"""


class Base(unittest.TestCase):
    def setUp(self):
        d = Path(tempfile.mkdtemp())
        self.bank, self.usage, self.req, self.log, self.daily, self.dry = d / "bank.md", d / "usage.json", d / "req.json", d / "log.md", d / "daily.txt", d / "dry.md"
        self.bank.write_text(BANK0, encoding="utf-8")
        self.usage.write_text(json.dumps({"day": "x", "calls": 0, "cap": 12}), encoding="utf-8")
        self.req.write_text(json.dumps({"titles": ["Alpha", "Beta"]}), encoding="utf-8")
        self.p = [mock.patch.object(rb, n, v) for n, v in (("BANK", self.bank), ("USAGE", self.usage), ("GRADE_REQUEST", self.req), ("LOG", self.log),
                                                            ("DAILY", self.daily), ("DRY", self.dry), ("KEY", "k"))]
        for x in self.p:
            x.start()
        rb.GRADES.clear()
        rb.DRY_GRADES.clear()
        rb.GRADE_NOTE[0] = ""
        rb.CALLS.update(n=0, cap=12)
        rb.STATE.update(models=["m0"], idx=0, quota_hit=False, last_raw="", net_retried=False, native_tried=False)

    def tearDown(self):
        for x in self.p:
            x.stop()
        rb.GRADES.clear()
        rb.DRY_GRADES.clear()
        rb.GRADE_NOTE[0] = ""


class PatchA(Base):
    def run_main(self, usable, dry, judge):
        args = argparse.Namespace(target=2, max_calls=12, max_bank=60, dry_run=dry, probe=False, seed=None)
        with mock.patch.object(rb, "usable_count", lambda: (usable, 100)), mock.patch.object(rb, "judge", judge), mock.patch.object(rb, "gemini_models", lambda: ["m0"]):
            rb.run(args)

    def test_a_dry_run_grades_but_saves_nothing(self):
        def judge(b):
            rb.CALLS["n"] += 1
            return GOOD
        before_log = self.log.exists()
        self.run_main(99, True, judge)
        self.assertEqual(sorted(rb.DRY_GRADES), ["Alpha", "Beta"])                            # graded in memory (and printed)
        self.assertEqual(rb.GRADES, {})
        self.assertNotIn("grade", json.loads(self.usage.read_text(encoding="utf-8")))         # not saved in the usage file
        self.assertEqual(self.log.exists(), before_log)                                       # not written to refill_log.md
        self.assertIn("(dry run: grades not saved)", rb.GRADE_NOTE[0])
        self.assertEqual(json.loads(self.usage.read_text(encoding="utf-8"))["calls"], 2)      # but the calls ARE counted in the cap

    def test_a_real_run_still_saves_the_grades(self):
        def judge(b):
            rb.CALLS["n"] += 1
            return GOOD
        self.run_main(99, False, judge)
        self.assertEqual(sorted(json.loads(self.usage.read_text(encoding="utf-8"))["grade"]), ["Alpha", "Beta"])
        self.assertIn("grade PASS | Alpha", self.log.read_text(encoding="utf-8"))

    def test_the_stop_reason_goes_into_the_daily_line(self):
        def judge(b):
            rb.CALLS["n"] += 1
            return False, {"issue": "judge unavailable (HTTP 503)"}
        self.run_main(99, False, judge)
        line = self.daily.read_text(encoding="utf-8")
        self.assertIn("grading stopped: judge unavailable (HTTP 503)", line)
        self.assertIn("2 still to grade", line)
        self.assertNotIn("grade", json.loads(self.usage.read_text(encoding="utf-8")))

    def test_the_grade_never_exceeds_the_cap(self):
        rb.CALLS.update(n=11, cap=12)
        self.usage.write_text(json.dumps({"day": rb.quota_day(), "calls": 11, "cap": 12}), encoding="utf-8")
        calls = []

        def judge(b):
            rb.CALLS["n"] += 1
            calls.append(1)
            return GOOD
        self.run_main(99, False, judge)
        self.assertEqual(len(calls), 1)                                                       # 1 call left: 1 story graded
        self.assertLessEqual(rb.CALLS["n"], 12)


class PatchC(unittest.TestCase):
    HELD = ("Bruno the Umpire", "Bruno vs Pigeon", "Bruno Hides the Ball")

    def test_the_three_held_stories_are_in_used_md_and_cannot_be_picked(self):
        import daily
        hist = daily.History(daily.ms.USED)
        done = " ".join(hist.recent_titles(500))
        for t in self.HELD:
            self.assertIn(t, done, t)
        for b in daily.parse_dialogue_bank():
            if b["title_en"] in self.HELD:
                self.assertTrue(b["title_hi"] in done or b["title_en"] in done)                # exactly the check usable_count and the factory use

    def test_they_stay_in_the_bank_and_nothing_else_changed(self):
        bank = (ROOT / "stories/dialogue_bank.md").read_text(encoding="utf-8")
        for t in self.HELD:
            self.assertIn(f"## {t} |", bank)
        used = (ROOT / "stories/used.md").read_text(encoding="utf-8")
        self.assertEqual(sum(1 for ln in used.splitlines() if ln.startswith("- HOLD ")), 3)

    def test_a_hold_row_has_no_closing_column(self):
        used = (ROOT / "stories/used.md").read_text(encoding="utf-8")
        for ln in used.splitlines():
            if ln.startswith("- HOLD "):
                self.assertEqual(ln.count("|"), 3)                                             # date | slug | title | plot: the endings list is not touched


if __name__ == "__main__":
    unittest.main()
