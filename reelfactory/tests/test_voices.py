"""Per-character voices: speaker detection, config completeness, no speech for Bruno, QC voice checks."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

import voice_lib  # noqa: E402
import daily  # noqa: E402

HINDI_VOICES = {"hf_alpha", "hf_beta", "hm_omega", "hm_psi"}


class TestSplit(unittest.TestCase):
    def test_quote_goes_to_the_named_speaker_and_the_tag_to_the_narrator(self):
        self.assertEqual(voice_lib.split_line("सूर्या बोला, आज छक्का मारकर दिखा!"), [("narrator", "सूर्या बोला,"), ("surya", "आज छक्का मारकर दिखा!")])
        self.assertEqual(voice_lib.split_line("दादाजी ने गेंद रोककर कहा, पहले एक रन!")[1][0], "dadaji")
        self.assertEqual(voice_lib.split_line("कोच बोले, हटो, मैं पेड़ हिलाता हूँ!")[1][0], "coach")
        self.assertEqual(voice_lib.split_line("मीना बोली, दादाजी, मेरी गेंद कहाँ गई?")[1][0], "meena")  # first name in the tag speaks, not the one addressed

    def test_lines_without_a_speaker_use_the_narrator(self):
        for t in ("सचिन ने गेंद उठाई, सूर्या चादर में छुपा।", "आंटी ने कैच पकड़ा और नल दिखाया!", "दोनों बोले, आंटी, एक मौक़ा दे दो!", "सूर्या का शॉट आंटी की छत पर पहुँचा!"):
            self.assertEqual([w for w, _ in voice_lib.split_line(t)], ["narrator"], t)

    def test_text_is_never_lost(self):
        for b in daily.parse_bank():
            for r in b["rows"]:
                joined = " ".join(t for _, t in voice_lib.split_line(r["line_hi"]))
                self.assertEqual(joined.replace(" ", ""), r["line_hi"].replace(" ", ""), r["line_hi"])


class TestConfig(unittest.TestCase):
    cfg = voice_lib.load_config()

    def test_every_character_has_a_voice_and_hindi_voices_are_used(self):
        for who in voice_lib.NAMES.values():
            spec = self.cfg["characters"][who]
            self.assertTrue("voice" in spec or "bark" in spec, who)
            if "voice" in spec:
                self.assertIn(spec["voice"], HINDI_VOICES, who)
        self.assertEqual(self.cfg["narrator"]["voice"], "hm_omega")  # the narrator keeps the current voice

    def test_bruno_barks_and_the_bark_file_exists(self):
        self.assertNotIn("voice", self.cfg["characters"]["bruno"])
        self.assertTrue((ROOT / self.cfg["characters"]["bruno"]["bark"]).exists())

    def test_character_roles(self):
        c = self.cfg["characters"]
        kids = [c[k] for k in ("sachin", "surya", "golu", "meena")]
        self.assertTrue(all(k["speed"] > 1.0 and k["pitch"] > 0 for k in kids))  # lighter and faster
        self.assertTrue(c["dadaji"]["speed"] < 1.0 and c["dadaji"]["pitch"] < 0)  # slow and deep
        self.assertTrue(c["coach"]["pitch"] < 0 and c["coach"]["gain_db"] > 0)  # deep and loud
        self.assertTrue(c["aunty"]["pitch"] > 0)  # higher

    def test_every_bank_speaker_has_a_voice(self):
        for b in daily.parse_bank():
            for r in b["rows"]:
                for who, _ in voice_lib.split_line(r["line_hi"]):
                    self.assertTrue(who == "narrator" or who in self.cfg["characters"], r["line_hi"])


class TestQC(unittest.TestCase):
    def test_new_reels_pass_the_voice_checks(self):
        from factory import qc
        for name in ("vt-echo-wall", "vt-bruno-keeper"):
            if not (ROOT / "output" / "reels" / f"{name}.mp4").exists():
                self.skipTest("voice test reels not rendered")
            r = qc.inspect(name)
            ids = {c["id"]: c["ok"] for c in r["checks"]}
            self.assertTrue(ids["voice_map"] and ids["voice_start"], name)

    def test_legacy_voice_fails_the_voice_map_check_when_character_voices_are_enabled(self):
        from factory import qc
        if not (ROOT / "output" / "reels" / "vt-echo-wall-old.mp4").exists():
            self.skipTest("voice test reels not rendered")
        r = qc.inspect("vt-echo-wall-old")
        self.assertIn("voice_map", [c["id"] for c in r["failed"]])


if __name__ == "__main__":
    unittest.main()
