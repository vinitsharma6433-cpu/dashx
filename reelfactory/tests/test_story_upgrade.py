"""Tests for the story-upgrade rules (scripts/story_rules.py). They apply only to stories in the new format (with a `card:` line)."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import story_rules as sr  # noqa: E402


class ColdOpen(unittest.TestCase):
    def test_polite_question_fails(self):
        self.assertTrue(sr.cold_open_problems("दादाजी, आपको ज़ुकाम है क्या?"))
        self.assertTrue(sr.cold_open_problems("भैया, गेंद डालूँ क्या?"))

    def test_conflict_passes(self):
        self.assertFalse(sr.cold_open_problems("नो बॉल! नहीं गिनी जाएगी!"))
        self.assertFalse(sr.cold_open_problems("मेरी गेंद कौन ले गया?"))

    def test_plain_question_fails(self):
        self.assertTrue(sr.cold_open_problems("तू फिर से आउट हो गया?"))


class PlotVsDialogue(unittest.TestCase):
    SCENES = [
        {"params": {"left": "surya", "right": "golu"}, "dialogue": [{"speaker": "surya", "line": "क"}, {"speaker": "golu", "line": "ख"}]},
        {"params": {"catcher": "aunty", "watchers": ["bruno", "golu"]}, "dialogue": [{"speaker": "golu", "line": "ग"}, {"speaker": "bruno", "line": "भौं"}]},
    ]

    def test_speaker_missing_from_plot(self):
        out = sr.plot_dialogue_problems("Surya teaches Bruno to field and Aunty catches", self.SCENES)
        self.assertTrue(any("golu" in x for x in out))

    def test_matching_plot_passes(self):
        self.assertEqual(sr.plot_dialogue_problems("Surya and Golu argue, Bruno barks and Aunty catches", self.SCENES), [])

    def test_plot_names_someone_who_never_appears(self):
        out = sr.plot_dialogue_problems("Surya, Golu and Pappu argue", self.SCENES)
        self.assertTrue(any("pappu" in x for x in out))


class Typos(unittest.TestCase):
    def test_known_wrong_spelling(self):
        self.assertTrue(sr.typo_problems("ये तो अब मेरा फ़ीलडर है"))

    def test_bark_repeat_is_allowed(self):
        self.assertEqual(sr.typo_problems("भौं भौं!"), [])

    def test_same_word_twice(self):
        self.assertTrue(sr.typo_problems("गेंद गेंद उड़ गई"))


class Card(unittest.TestCase):
    def test_good_card(self):
        self.assertEqual(sr.card_problems("मिंटू की चालबाज़ी!"), [])

    def test_bad_cards(self):
        self.assertTrue(sr.card_problems("आज गली की जंग है भाई यार"))  # 7 words
        self.assertTrue(sr.card_problems("Bruno Files"))
        self.assertTrue(sr.card_problems("गेंद गायब 🐶 है"))


class Series(unittest.TestCase):
    def test_both_fields_and_question(self):
        self.assertEqual(sr.series_problems("Bruno Files", "2", "अब गेंद कहाँ गई?"), [])

    def test_missing_ep_or_no_question(self):
        self.assertTrue(sr.series_problems("Bruno Files", "", "अब गेंद कहाँ गई?"))
        self.assertTrue(sr.series_problems("Bruno Files", "2", "खत्म!"))

    def test_not_a_series_is_fine(self):
        self.assertEqual(sr.series_problems("", "", "खत्म!"), [])


class NewCast(unittest.TestCase):
    def test_new_characters_are_known(self):
        for who in ("pappu", "chhotu", "mintu"):
            self.assertIn(who, sr.SPEAKERS)
            self.assertIn(who, sr.SPEAKER_HI)


class HookScore(unittest.TestCase):
    """The Hindi hook score is a logged number only: it must never raise and must never be a reason to reject a story."""

    def test_weak_vs_strong(self):
        weak = sr.hook_score("नमस्ते दोस्तो, आज हम गेंद के बारे में बात करेंगे")
        strong = sr.hook_score("छोटू, ऐसी गेंद दे जो न फटे!")
        self.assertLess(weak["score"], strong["score"])
        self.assertEqual(weak["verdict"], "WEAK")
        self.assertEqual(strong["verdict"], "STRONG")

    def test_range_and_keys(self):
        for line in ("", "!", "abc", "भौं भौं!", "नो बॉल! नहीं गिनी जाएगी!"):
            h = sr.hook_score(line)
            self.assertTrue(0 <= h["score"] <= 100)
            for k in ("score", "verdict", "checks", "weakest", "flags"):
                self.assertIn(k, h)

    def test_text_form_never_raises(self):
        self.assertIn("hook score", sr.hook_score_text("मेरी गेंद कौन ले गया?"))

    def test_score_is_not_a_story_check(self):
        # the score functions do not appear in any problem-returning rule
        self.assertEqual(sr.cold_open_problems("नो बॉल! नहीं गिनी जाएगी!"), [])


if __name__ == "__main__":
    unittest.main()
