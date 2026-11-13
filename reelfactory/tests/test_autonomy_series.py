"""Phase 5 tests: series + variety memory (autonomy/series_memory.py) and its additive hooks in factory/pipeline.py and refill_bank.py."""
import json
import random
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "autonomy"))
sys.path.insert(0, str(REPO / "reelfactory" / "scripts"))
sys.path.insert(0, str(REPO / "reelfactory"))
import guard as g  # noqa: E402
import series_memory as sm  # noqa: E402

NOW = datetime(2026, 11, 11, 22, 0, tzinfo=g.IST)

BANK = """# header
## Bruno Files One | ब्रूनो एक
plot: Bruno hides the ball.
ending: गेंद कहाँ है
hook: गेंद कहाँ गई?
card: क
series: Bruno Files
ep: 1
- face-off | golu | surya | गेंद | golu: मैंने देखा! // surya: क्या देखा?
- catch | dadaji | golu | bruno | dadaji: गेंद कहाँ? // golu: कुर्सी के पीछे?

## Bruno Files Two | ब्रूनो दो
plot: p
ending: गड्ढा मिला
hook: कुर्सी के पीछे क्या?
series: Bruno Files
ep: 2
- face-off | golu | surya | पीछे | golu: कुर्सी के पीछे गड्ढा! // surya: किसका गड्ढा?
- catch | dadaji | golu | bruno | dadaji: अब कौन सा गड्ढा?

## Bruno Files Three | ब्रूनो तीन
plot: p
ending: ब्रूनो हँसा
hook: तीसरा गड्ढा?
series: Bruno Files
ep: 3
- face-off | golu | surya | गड्ढा | golu: तीसरा गड्ढा! // surya: बस करो!
- catch | dadaji | golu | bruno | dadaji: चलो खेलो!

## Two Whistles Talk | दो सीटी
plot: p
ending: आंटी की सीटी
hook: सीटी किसकी?
- face-off | pintu | coach | सीटी | pintu: ये मेरी सीटी है! // coach: नहीं, मेरी!
- catch | aunty | pintu | coach | aunty: अब सीटी मेरी!

## Old Story | पुरानी
plot: p
ending: पुराना अंत
hook: पुराना हुक
- face-off | pintu | coach | x | pintu: बहुत पुरानी शुरुआत // coach: ठीक
"""


def queue(entries):
    return json.dumps({"posts": [{"title": f"{t} DASHX", "when": (NOW + timedelta(hours=h)).isoformat()} for t, h in entries]})


class Parse(unittest.TestCase):
    def test_fields(self):
        s = sm.parse_bank(BANK)
        self.assertEqual([x["title_en"] for x in s], ["Bruno Files One", "Bruno Files Two", "Bruno Files Three", "Two Whistles Talk", "Old Story"])
        self.assertEqual((s[0]["series"], s[0]["ep"]), ("Bruno Files", 1))
        self.assertTrue(s[0]["opening"].startswith("मैंने देखा"))
        self.assertTrue(s[0]["closing"].endswith("?") and "कुर्सी" in s[0]["closing"])

    def test_garbage_never_raises(self):
        self.assertEqual(sm.parse_bank(None), [])
        self.assertIsInstance(sm.parse_bank("## \n## x |"), list)
        self.assertEqual(sm.build("", "not json", NOW)["series"], {})


class Build(unittest.TestCase):
    def mem(self, q):
        return sm.build(BANK, q, NOW)

    def test_series_state(self):
        m = self.mem(queue([("bruno-files-one", -30), ("two-whistles-talk", -5)]))
        s = m["series"]["Bruno Files"]
        eps = {e["ep"]: e["status"] for e in s["episodes"]}
        self.assertEqual(eps, {1: "posted", 2: "waiting", 3: "waiting"})
        self.assertEqual(s["last_ep"], 1)
        self.assertEqual(s["next_ep"], 4)                         # the next NEW episode to write
        self.assertEqual(s["play_next"], "Bruno Files Two")       # lowest waiting episode goes out first
        self.assertEqual(s["promise_from"], "Bruno Files One")
        self.assertIn("कुर्सी", s["promise"])                      # the promise = the last spoken line of the latest episode

    def test_queued_counts_as_started(self):
        m = self.mem(queue([("bruno-files-one", -30), ("bruno-files-two", 10)]))
        s = m["series"]["Bruno Files"]
        self.assertEqual(s["last_ep"], 2)
        self.assertEqual(s["play_next"], "Bruno Files Three")
        self.assertEqual(s["callback_candidates"], ["Bruno Files One", "Bruno Files Two"])

    def test_last_14_days_window(self):
        m = self.mem(queue([("two-whistles-talk", -24 * 3), ("old-story", -24 * 20)]))
        self.assertEqual(m["recent"]["titles"], ["Two Whistles Talk"])
        self.assertIn("ये मेरी सीटी है!", m["recent"]["openings"])
        self.assertNotIn("बहुत पुरानी शुरुआत", m["recent"]["openings"])


class Prompt(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        (self.root / "autonomy").mkdir()
        m = sm.build(BANK, queue([("bruno-files-one", -30), ("two-whistles-talk", -5)]), NOW)
        (self.root / "autonomy" / "memory.json").write_text(json.dumps(m, ensure_ascii=False), encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_series_prompt_has_promise_payoff_and_callback(self):
        t = sm.prompt_text("series", self.root)
        self.assertIn("SERIES MEMORY (Bruno Files)", t)
        self.assertIn("PAY IT OFF", t)
        self.assertIn("callback", t)
        self.assertIn("Episode 4", t)
        self.assertIn("LAST 14 DAYS", t)

    def test_normal_prompt_has_only_the_variety_block(self):
        t = sm.prompt_text("normal", self.root)
        self.assertNotIn("SERIES MEMORY", t)
        self.assertIn("do NOT repeat", t)
        self.assertIn("ये मेरी सीटी है!", t)

    def test_cap_and_safety(self):
        big = {"series": {}, "recent": {"openings": ["word " * 100] * 5, "hooks": ["h " * 100] * 5, "endings": ["e " * 100] * 5}}
        (self.root / "autonomy" / "memory.json").write_text(json.dumps(big), encoding="utf-8")
        self.assertLessEqual(len(sm.prompt_text("normal", self.root)), sm.MAX_PROMPT_CHARS + 3)

    def test_nothing_or_error_gives_empty(self):
        self.assertEqual(sm.prompt_text("series", Path(tempfile.mkdtemp())), "")
        (self.root / "autonomy" / "memory.json").write_text("not json", encoding="utf-8")
        self.assertEqual(sm.prompt_text("series", self.root), "")
        (self.root / "autonomy" / "memory.json").write_text(json.dumps({"series": {"X": "bad"}, "recent": 5}), encoding="utf-8")
        self.assertEqual(sm.prompt_text("series", self.root), "")


class Order(unittest.TestCase):
    def c(self, rank, series, ep, name="x"):
        return (rank, 0, {"n": name}, {}, series, ep)

    def test_lowest_episode_goes_first_even_with_a_lower_rank(self):
        cands = [self.c(95, "Bruno Files", "2", "e2"), self.c(80, "Bruno Files", "1", "e1"), self.c(90, "Bruno Files", "3", "e3")]
        out = sm.in_order(cands)
        self.assertEqual([c[2]["n"] for c in out], ["e1"])

    def test_other_stories_are_untouched(self):
        cands = [self.c(95, "", "", "plain"), self.c(80, "Bruno Files", "2", "e2"), self.c(70, "Bruno Files", "1", "e1")]
        out = sm.in_order(cands)
        self.assertEqual({c[2]["n"] for c in out}, {"plain", "e1"})

    def test_series_are_independent(self):
        out = sm.in_order([self.c(1, "A", "2", "a2"), self.c(1, "A", "1", "a1"), self.c(1, "B", "5", "b5"), self.c(1, "B", "4", "b4")])
        self.assertEqual({c[2]["n"] for c in out}, {"a1", "b4"})

    def test_a_missing_or_failed_lower_episode_never_blocks(self):
        # ep 1 failed the quality checks, so it is not a candidate: ep 2 may go
        out = sm.in_order([self.c(1, "Bruno Files", "2", "e2"), self.c(1, "Bruno Files", "3", "e3")])
        self.assertEqual([c[2]["n"] for c in out], ["e2"])

    def test_bad_ep_values_are_left_alone_and_the_list_is_never_empty(self):
        cands = [self.c(1, "S", "", "a"), self.c(1, "S", "x", "b")]
        self.assertEqual(sm.in_order(cands), cands)
        self.assertEqual(sm.in_order([]), [])
        self.assertEqual(sm.in_order(None), None)           # fail-open

    def test_pipeline_uses_the_same_tuple_positions(self):
        src = (REPO / "reelfactory" / "factory" / "pipeline.py").read_text(encoding="utf-8")
        self.assertIn('cands.append((rank, i, st, q, b.get("series", ""), b.get("ep", "")))', src)      # series at index 4, ep at index 5
        self.assertIn("series_memory.in_order(cands)", src)
        self.assertIn("cands.sort(key=lambda t: (-t[0], t[1]))", src)                                  # the old ranking still decides inside the allowed set


class Variety(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        (self.root / "autonomy").mkdir()
        m = {"recent": {"openings": ["ये मेरी सीटी है आज"], "hooks": ["सीटी किसकी"], "endings": ["आंटी की सीटी"]}}
        (self.root / "autonomy" / "memory.json").write_text(json.dumps(m, ensure_ascii=False), encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_repeats_cost_points(self):
        self.assertEqual(sm.penalty("ये मेरी सीटी है आज", "", "", self.root), 6)
        self.assertEqual(sm.penalty("ये मेरी सीटी है आज", "सीटी किसकी", "आंटी की सीटी", self.root), 12)
        self.assertLessEqual(sm.penalty("ये मेरी सीटी है आज", "सीटी किसकी", "आंटी की सीटी", self.root), sm.PENALTY_MAX)

    def test_new_things_cost_nothing(self):
        self.assertEqual(sm.penalty("गेंद गायब हो गई", "तीन बल्ले", "कुत्ता जीता", self.root), 0)

    def test_no_memory_no_penalty(self):
        self.assertEqual(sm.penalty("ये मेरी सीटी है आज", "", "", Path(tempfile.mkdtemp())), 0)

    def test_penalty_is_soft(self):
        src = (REPO / "reelfactory" / "factory" / "pipeline.py").read_text(encoding="utf-8")
        i = src.index("series_memory.penalty(")
        self.assertIn("rank -=", src[i - 120:i])                      # only lowers the rank
        self.assertNotIn("continue", src[i - 120:i + 200])            # never skips a story


class Files(unittest.TestCase):
    def test_write_touches_only_memory_json(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "poster").mkdir(); (root / "reelfactory" / "stories").mkdir(parents=True)
            (root / "reelfactory" / "stories" / "dialogue_bank.md").write_text(BANK, encoding="utf-8")
            (root / "poster" / "queue.json").write_text(queue([("bruno-files-one", -30)]), encoding="utf-8")
            qb = (root / "poster" / "queue.json").read_bytes()
            m = sm.write(root, NOW)
            self.assertEqual(sorted(p.name for p in (root / "autonomy").iterdir()), ["memory.json"])
            self.assertEqual((root / "poster" / "queue.json").read_bytes(), qb)
            self.assertEqual(m["series"]["Bruno Files"]["last_ep"], 1)
            (root / "STOP_AUTONOMY").write_text("", encoding="utf-8")
            (root / "autonomy" / "memory.json").unlink()
            self.assertEqual(sm.write(root, NOW), {})
            self.assertFalse((root / "autonomy" / "memory.json").exists())

    def test_memory_json_is_a_notes_file_and_the_code_is_protected(self):
        rules = g.load_rules()
        self.assertEqual(g.classify("autonomy/memory.json", rules)[0], "state")
        self.assertEqual(g.classify("autonomy/series_memory.py", rules)[0], "deny")

    def test_no_model_call_anywhere_in_the_memory(self):
        src = (REPO / "autonomy" / "series_memory.py").read_text(encoding="utf-8")
        for w in ("urllib", "requests", "generativelanguage", "chat/completions", "GEMINI", "subprocess"):
            self.assertNotIn(w, src, w)


class RefillHook(unittest.TestCase):
    SEED = {"situation": "x", "formula": {"name": "n", "pattern": "p", "example": "e"}}

    def test_prompt_changes_only_by_the_memory_text(self):
        import refill_bank as rb
        real = sm.prompt_text
        try:
            sm.prompt_text = lambda *a, **k: ""
            random.seed(3); base = rb.prompt_for(self.SEED, ["t"], ["e"], "series", 2)[1]["content"]
            sm.prompt_text = lambda *a, **k: "SERIES MEMORY (X): promise.\n\n"
            random.seed(3); with_m = rb.prompt_for(self.SEED, ["t"], ["e"], "series", 2)[1]["content"]
            sm.prompt_text = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
            random.seed(3); broken = rb.prompt_for(self.SEED, ["t"], ["e"], "series", 2)[1]["content"]
        finally:
            sm.prompt_text = real
        self.assertEqual(with_m.replace("SERIES MEMORY (X): promise.\n\n", ""), base)
        self.assertLess(with_m.index("SERIES MEMORY (X)"), with_m.index("Titles already used"))
        self.assertEqual(broken, base)


if __name__ == "__main__":
    unittest.main()
