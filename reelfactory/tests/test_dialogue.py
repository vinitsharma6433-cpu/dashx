"""Dialogue format: bank stories, line rules, and the QC check that fails a scene with no speaker or a narration tag."""
import copy
import json
import shutil
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

import daily  # noqa: E402
import story_rules as rules  # noqa: E402


class TestRules(unittest.TestCase):
    def test_good_line(self):
        self.assertEqual(rules.dialogue_problems("कोच जी, मेरे पैर में मोच है!", "sachin"), [])

    def test_narration_tags_and_missing_speaker_are_rejected(self):
        for line in ("सूर्या बोला, चल!", "मीना बोली, ठीक है!", "दादाजी ने कहा, ठीक है!", "कोच ने पूछा, कहाँ?", "सचिन चिल्लाया, रुको!"):
            self.assertTrue(any("narration tag" in p for p in rules.dialogue_problems(line, "surya")), line)
        self.assertIn("has no valid speaker", rules.dialogue_problems("ठीक है भाई!", None))
        self.assertIn("has no valid speaker", rules.dialogue_problems("ठीक है भाई!", "narrator"))

    def test_third_person_about_itself_and_length(self):
        self.assertTrue(rules.dialogue_problems("सचिन ने गेंद उठाई।", "sachin"))
        self.assertTrue(rules.dialogue_problems(" ".join(["आज"] * 15) + " खेलो", "sachin"))  # more than 14 words


class TestBank(unittest.TestCase):
    def test_every_dialogue_story_builds_and_is_clean(self):
        stories = daily.parse_dialogue_bank()
        self.assertGreaterEqual(len(stories), 5)
        for b in stories:
            st, problems = daily.from_dialogue_data({"title_hi": b["title_hi"], "title_en": b["title_en"], "plot_en": b["plot_en"], "scenes": b["rows"], "closing_hi": b["closing"]})
            self.assertEqual(problems, [], b["title_en"])
            for sc in st["scenes"]:
                self.assertTrue(1 <= len(sc["dialogue"]) <= 2)
                cast = daily.scene_cast(sc["params"])
                self.assertTrue(all(d["speaker"] in cast for d in sc["dialogue"]), b["title_en"])

    def test_speaker_outside_the_scene_and_same_speaker_twice_are_rejected(self):
        b = daily.parse_dialogue_bank()[0]
        rows = copy.deepcopy(b["rows"])
        rows[0]["dialogue"][0]["speaker"] = "aunty"  # not on stage in the first scene
        _, problems = daily.from_dialogue_data({"title_hi": "x", "title_en": "x", "plot_en": "x", "scenes": rows, "closing_hi": b["closing"]})
        self.assertTrue(any("not in the scene" in p for p in problems))
        rows = copy.deepcopy(b["rows"])
        rows[0]["dialogue"][1]["speaker"] = rows[0]["dialogue"][0]["speaker"]
        _, problems = daily.from_dialogue_data({"title_hi": "x", "title_en": "x", "plot_en": "x", "scenes": rows, "closing_hi": b["closing"]})
        self.assertTrue(any("two different characters" in p for p in problems))


class TestQC(unittest.TestCase):
    SRC = "fake-cramp-talk"
    NAME = "_dlgtest"

    def setUp(self):
        if not (ROOT / "output" / "reels" / f"{self.SRC}.mp4").exists():
            self.skipTest("dialogue test reel not rendered")
        shutil.rmtree(ROOT / "reels" / self.NAME, ignore_errors=True)
        shutil.copytree(ROOT / "reels" / self.SRC, ROOT / "reels" / self.NAME)
        shutil.copy2(ROOT / "output" / "reels" / f"{self.SRC}.mp4", ROOT / "output" / "reels" / f"{self.NAME}.mp4")

    def tearDown(self):
        shutil.rmtree(ROOT / "reels" / self.NAME, ignore_errors=True)
        (ROOT / "output" / "reels" / f"{self.NAME}.mp4").unlink(missing_ok=True)

    def run_qc(self, edit=None):
        from factory import qc
        p = ROOT / "reels" / self.NAME / "script.json"
        sc = json.loads(p.read_text(encoding="utf-8"))
        if edit:
            edit(sc)
            p.write_text(json.dumps(sc, ensure_ascii=False), encoding="utf-8")
        r = qc.inspect(self.NAME)
        return r, {c["id"]: c for c in r["checks"]}

    @staticmethod
    def hindi_board(sc):
        for s in sc["scenes"]:
            if "boardText" in s.get("params", {}):
                s["params"]["boardText"] = "आउच"

    def test_the_real_dialogue_reel_passes(self):
        r, c = self.run_qc(self.hindi_board)
        self.assertTrue(r["passed"], r["failed"])
        self.assertTrue(c["dialogue_format"]["ok"] and c["dialogue_timing"]["ok"])

    def test_english_pop_up_word_fails(self):
        r, c = self.run_qc()  # this reel was rendered before the rule, with the word OUCH
        self.assertFalse(c["dialogue_format"]["ok"])
        self.assertIn("pop-up word must be Hindi", c["dialogue_format"]["detail"])

    def test_scene_without_speaker_fails(self):
        def e(s):
            self.hindi_board(s)
            del s["scenes"][1]["speaker"]
            del s["scenes"][1]["dialogue"]
        r, c = self.run_qc(e)
        self.assertFalse(c["dialogue_format"]["ok"])
        self.assertIn("no speaker", c["dialogue_format"]["detail"])
        self.assertFalse(r["passed"])

    def test_line_with_a_narration_tag_fails(self):
        def e(s):
            self.hindi_board(s)
            s["scenes"][0]["dialogue"][0]["line"] = "सचिन बोला, कोच जी, मेरे पैर में मोच है!"
        r, c = self.run_qc(e)
        self.assertFalse(c["dialogue_format"]["ok"])
        self.assertIn("narration tag", c["dialogue_format"]["detail"])

    def test_speaker_not_on_screen_and_end_card_speaker(self):
        def e(s):
            s["scenes"][0]["dialogue"][0]["speaker"] = "aunty"
        self.assertIn("not on screen", self.run_qc(e)[1]["dialogue_format"]["detail"])

        def e2(s):
            s["scenes"][-1]["speaker"] = "coach"
        self.assertFalse(self.run_qc(e2)[1]["dialogue_format"]["ok"])

    def test_older_narration_reels_are_not_judged_by_the_dialogue_rule(self):
        from factory import qc
        c = {x["id"]: x for x in qc.inspect("two-whistles")["checks"]}
        self.assertTrue(c["dialogue_format"]["ok"])
        self.assertIn("older", c["dialogue_format"]["detail"])


if __name__ == "__main__":
    unittest.main()
