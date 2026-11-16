import datetime
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "autonomy"))
import pattern_advisor as ad  # noqa: E402

D = datetime.date(2026, 11, 16)


def agg(date, n, **fields):
    counts = {f: {} for f in ad.FIELDS}
    counts.update(fields)
    return {"generated": date, "sources_analysed": n, "counts": counts}


class History(unittest.TestCase):
    def test_keeps_last_weeks_and_replaces_same_date(self):
        h = []
        for i in range(1, 16):                                   # 15 weeks of entries: only the last HISTORY_WEEKS (12) stay
            h = ad.update_history(h, agg(f"2026-10-{i:02d}", 3))
        self.assertEqual(len(h), ad.HISTORY_WEEKS)
        h = ad.update_history(h, agg("2026-10-15", 5))
        self.assertEqual(len(h), ad.HISTORY_WEEKS)
        self.assertEqual(h[-1]["sources_analysed"], 5)

    def test_rising(self):
        h = [agg("2026-11-02", 4, hook_type={"question": 3, "shock": 1}),
             agg("2026-11-09", 4, hook_type={"question": 1, "shock": 3})]
        r = ad.rising_patterns(h)
        self.assertEqual((r[0]["field"], r[0]["value"]), ("hook_type", "shock"))
        self.assertEqual(ad.rising_patterns(h[:1]), [])
        self.assertEqual(ad.rising_patterns(None), [])


class Propose(unittest.TestCase):
    A = agg("2026-11-16", 4, hook_type={"curiosity": 3, "question": 1},
            structure={"setup_twist_end": 4}, shareable_because={"tag_a_friend": 2, "none": 2})

    def test_small_sample_gives_nothing(self):
        self.assertEqual(ad.propose_experiments(agg("2026-11-16", 2, hook_type={"curiosity": 2}), [], today=D), [])

    def test_gap_proposed_with_fixed_sentence(self):
        own = [{"hook_type": "question"}] * 5
        out = ad.propose_experiments(self.A, own, today=D)
        ids = [p["id"] for p in out]
        self.assertIn("hook_type:curiosity:2026-11-16", ids)
        p = next(x for x in out if x["value"] == "curiosity")
        self.assertEqual(p["proposal"], "Try the hook type 'curiosity' in about 1 of 5 new stories.")
        self.assertEqual(p["confidence"], "medium")

    def test_already_covered_not_proposed(self):
        own = [{"hook_type": "curiosity"}] * 4 + [{"hook_type": "question"}]
        out = ad.propose_experiments(self.A, own, today=D)
        self.assertFalse(any(p["field"] == "hook_type" for p in out))

    def test_limit_and_none_other_skipped(self):
        out = ad.propose_experiments(self.A, [], today=D)
        self.assertLessEqual(len(out), ad.MAX_PROPOSALS_PER_WEEK)
        self.assertFalse(any(p["value"] in ("none", "other") for p in out))

    def test_no_own_data_is_low_confidence(self):
        out = ad.propose_experiments(self.A, [], today=D)
        self.assertTrue(all(p["confidence"].startswith("low") for p in out))

    def test_blocked_idea_skipped_then_allowed_after_expiry(self):
        blocked = [{"field": "hook_type", "value": "curiosity", "until": "2026-11-20"}]
        out = ad.propose_experiments(self.A, [], blocked=blocked, today=D, limit=10)
        self.assertFalse(any(p["value"] == "curiosity" for p in out))
        out2 = ad.propose_experiments(self.A, [], blocked=blocked, today=datetime.date(2026, 11, 21), limit=10)
        self.assertTrue(any(p["value"] == "curiosity" for p in out2))

    def test_proposal_text_only_from_templates(self):
        out = ad.propose_experiments(self.A, [], today=D, limit=10)
        for p in out:
            self.assertEqual(p["proposal"], ad.TEMPLATES[p["field"]].format(v=p["value"]))


class Evaluate(unittest.TestCase):
    EXP = {"field": "hook_type", "value": "curiosity"}

    def rows(self, tagged, other):
        return ([{"hook_type": "curiosity", "views_per_day": x} for x in tagged]
                + [{"hook_type": "question", "views_per_day": x} for x in other])

    def test_wait_when_too_few(self):
        r = ad.evaluate_experiment(self.EXP, self.rows([100, 100], [50, 50]), today=D)
        self.assertEqual(r["verdict"], "wait")

    def test_keep(self):
        r = ad.evaluate_experiment(self.EXP, self.rows([120, 130, 140], [50, 60, 70]), today=D)
        self.assertEqual(r["verdict"], "keep")
        self.assertGreaterEqual(r["lift"], ad.KEEP_LIFT)

    def test_drop_blocks_for_21_days(self):
        r = ad.evaluate_experiment(self.EXP, self.rows([10, 12, 11], [100, 90, 110]), today=D)
        self.assertEqual(r["verdict"], "drop")
        self.assertEqual(r["block"], {"field": "hook_type", "value": "curiosity", "until": "2026-12-07"})   # 21 days (owner's new spec; was 14)

    def test_inconclusive_waits(self):
        r = ad.evaluate_experiment(self.EXP, self.rows([100, 100, 100], [100, 100, 100]), today=D)
        self.assertEqual(r["verdict"], "wait")

    def test_zero_baseline_waits(self):
        r = ad.evaluate_experiment(self.EXP, self.rows([5, 5, 5], [0, 0]), today=D)
        self.assertEqual(r["verdict"], "wait")


class Report(unittest.TestCase):
    def test_block(self):
        out = ad.propose_experiments(Propose.A, [], today=D)
        text = ad.report_block(out, [{"field": "hook_type", "value": "shock", "rise": 0.5}])
        self.assertIn("proposals only, nothing applied", text)
        self.assertIn("Rising in the niche: hook_type=shock", text)
        self.assertIn("No experiment proposed", ad.report_block([], []))


if __name__ == "__main__":
    unittest.main()
