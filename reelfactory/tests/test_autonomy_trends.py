"""Phase 3 tests: trend radar (autonomy/trends.py), the prompt feed (autonomy/trend_feed.py) and the additive hook in refill_bank.py."""
import json
import random
import shutil
import sys
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlparse

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "autonomy"))
sys.path.insert(0, str(REPO / "reelfactory" / "scripts"))
sys.path.insert(0, str(REPO / "reelfactory"))
import guard as g  # noqa: E402
import trend_feed as tf  # noqa: E402
import trends as t  # noqa: E402
import story_rules as sr  # noqa: E402

RULES = g.load_rules()
THEMES = t.load_json(REPO / "autonomy" / "trend_themes.json")
CAL = t.load_json(REPO / "autonomy" / "festivals.json")
TODAY = date(2026, 11, 11)

RSS = b"""<?xml version="1.0"?><rss><channel><title>Feed name</title>
<item><title>Gully cricket match in Meerut lane</title></item><item><title>Second item</title></item></channel></rss>"""


def build(fetched, today=TODAY, themes=THEMES, cal=CAL, failed=None):
    return t.build(today, fetched, RULES, themes, cal, failed)


class Safety(unittest.TestCase):
    def test_blocked_headlines_are_thrown_away(self):
        bad = ["Minister says election date soon", "BJP rally in the city", "Temple row grows", "Muslim leader speaks",
               "Fatal accident kills two", "Police arrest man after theft", "Flood hits town", "Court gives bail",
               "Best cricket ball price drop", "Dhoni returns for IPL", "Kohli scores again", "Amazon sale on bats", "Man dies in fire"]
        for h in bad:
            self.assertFalse(t.is_safe_headline(h, RULES), h)

    def test_normal_headlines_pass(self):
        for h in ("Gully cricket tournament in Meerut", "Board exam date sheet released", "Winter holiday for schools announced",
                  "Rain brings cool weather to the city", "Wedding season starts"):
            self.assertTrue(t.is_safe_headline(h, RULES), h)

    def test_word_boundaries_avoid_false_blocks(self):
        self.assertTrue(t.is_safe_headline("Ape park opens", RULES))            # not 'ap...' party words
        self.assertTrue(t.is_safe_headline("Godown cleaned before the match", RULES))   # 'god ' is a whole word only

    def test_unsafe_headlines_do_not_count_toward_a_theme(self):
        out = build({"s": ["Cricket stadium collapse kills fans", "Cricket match kills", "Police cricket arrest"]})
        self.assertNotIn("match_fever", [x["id"] for x in out["topics"]])
        self.assertEqual(out["stats"]["dropped_unsafe"], 3)

    def test_headlines_are_never_stored_or_copied(self):
        heads = ["Gully cricket tournament in Meerut lane", "Cricket match today in the city", "Wedding season rush in Meerut"]
        out = json.dumps(build({"news_cricket": heads}), ensure_ascii=False)
        for h in heads:
            self.assertNotIn(h, out)
            self.assertNotIn(h.lower(), out.lower())

    def test_a_topic_that_breaks_brand_rules_is_dropped(self):
        bad = {"themes": [dict(THEMES["themes"][0], id="bad", angle="Show the best bat at a low price offer", keywords=["cricket"]),
                          dict(THEMES["themes"][0], id="bad2", angle="A kid beats Dhoni", keywords=["cricket"]),
                          dict(THEMES["themes"][1], id="good")]}
        ids = [x["id"] for x in build({"s": ["cricket match"]}, themes=bad)["topics"]]
        self.assertNotIn("bad", ids)
        self.assertNotIn("bad2", ids)
        self.assertIn("good", ids)

    def test_all_our_own_texts_pass_the_existing_story_rules(self):
        texts = []
        for th in THEMES["themes"]:
            texts += [th["label"], th["why"], th["angle"]]
        for d in CAL["days"]:
            texts += [d["label"], d["why"], d["angle"]]
        for x in texts:
            self.assertFalse(sr._BAD_EN.search(x), x)
            self.assertFalse(sr._BAD_HI.search(x), x)
            self.assertTrue(t.brand_ok(x, RULES), x)
            self.assertFalse(t.blocked_re(RULES).search(x), x)     # no politics / religion / tragedy / crime words in our own angles either

    def test_themes_are_well_formed(self):
        ids = [x["id"] for x in THEMES["themes"]]
        self.assertEqual(len(ids), len(set(ids)))
        for th in THEMES["themes"]:
            for k in ("id", "label", "keywords", "why", "angle"):
                self.assertTrue(th.get(k), (th.get("id"), k))


class Build(unittest.TestCase):
    def test_counts_safe_headlines_per_theme(self):
        out = build({"a": ["Cricket match tonight", "Another cricket match", "Meerut news"], "b": ["Rain expected", "Gully cricket"]})
        top = {x["id"]: x for x in out["topics"]}
        self.assertEqual(top["match_fever"]["strength"], 3)
        self.assertEqual(top["match_fever"]["sources"], ["a", "b"] if "b" in top["match_fever"]["sources"] else ["a"])
        self.assertIn("weather_twist", top)
        self.assertEqual(out["stats"]["headlines_seen"], 5)

    def test_evergreen_themes_when_every_source_fails(self):
        out = build({}, failed=["a", "b"])
        ids = [x["id"] for x in out["topics"]]
        self.assertIn("gully_rules", ids)
        self.assertIn("meerut_touch", ids)
        self.assertEqual(out["stats"]["sources_failed"], ["a", "b"])

    def test_max_topics_and_ranking(self):
        out = build({"a": ["cricket gully meerut rain wedding school holiday exam"] * 6})
        self.assertLessEqual(len(out["topics"]), RULES["trends"]["max_topics"])
        s = [x["strength"] for x in out["topics"]]
        self.assertEqual(s, sorted(s, reverse=True))

    def test_every_topic_has_an_expiry_date(self):
        for x in build({"a": ["cricket match"]})["topics"]:
            self.assertGreaterEqual(x["expires"], TODAY.isoformat())
            self.assertTrue(x["story_angle"] and x["why_fits"] and x["topic"])

    def test_festival_window(self):
        ids = [x["id"] for x in t.festival_topics(TODAY, CAL)]
        self.assertIn("bhai_dooj_2026", ids)
        self.assertIn("childrens_day_2026", ids)             # 3 days ahead
        self.assertNotIn("diwali_2026", ids)                 # 3 days ago: over
        self.assertNotIn("holi_2027", ids)
        self.assertEqual(t.festival_topics(date(2026, 12, 1), CAL), [])
        self.assertIn("diwali_2026", [x["id"] for x in t.festival_topics(date(2026, 11, 4), CAL)])
        self.assertIn("diwali_2026", [x["id"] for x in t.festival_topics(date(2026, 11, 9), CAL)])   # 1 day after

    def test_lunar_dates_are_marked_for_the_owner(self):
        d = {x["id"]: x for x in t.festival_topics(date(2026, 11, 8), CAL)}
        self.assertTrue(any("approximate" in s for s in d["diwali_2026"]["sources"]))


class Fetch(unittest.TestCase):
    def test_headlines_skip_the_feed_title(self):
        self.assertEqual(t.headlines(RSS), ["Gully cricket match in Meerut lane", "Second item"])

    def test_only_https(self):
        with self.assertRaises(ValueError):
            t.fetch("http://news.google.com/rss", RULES)

    def test_sources_are_free_public_google_rss_only(self):
        self.assertFalse(RULES["trends"]["login_required"])
        for s in RULES["trends"]["sources"]:
            u = urlparse(s["url"])
            self.assertEqual(u.scheme, "https")
            self.assertIn(u.hostname, ("trends.google.com", "news.google.com"))
            self.assertNotIn("instagram", s["url"])
        self.assertTrue(RULES["trends"]["not_used"])

    def test_code_has_no_login_scraping_or_instagram(self):
        for f in ("trends.py", "trend_feed.py"):
            src = (REPO / "autonomy" / f).read_text(encoding="utf-8").lower()
            for w in ("instagram.com", "selenium", "playwright", "webbrowser", "subprocess", "import requests", "password", "authorization", "access_token", "os.system"):
                self.assertNotIn(w, src, (f, w))


class Run(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        (self.root / "autonomy").mkdir()
        for f in ("trend_themes.json", "festivals.json"):
            shutil.copy(REPO / "autonomy" / f, self.root / "autonomy" / f)
        self.now = datetime(2026, 11, 11, 14, 0, tzinfo=g.IST)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def ok_fetcher(self, url, rules):
        return RSS

    def test_writes_trends_and_log_only(self):
        d = t.run(self.root, self.now, fetcher=self.ok_fetcher)
        self.assertTrue(d["topics"])
        self.assertEqual(sorted(p.name for p in (self.root / "autonomy").iterdir()), ["festivals.json", "log.md", "trend_themes.json", "trends.json"])
        self.assertIn("| info | trend_radar |", (self.root / "autonomy" / "log.md").read_text(encoding="utf-8"))

    def test_once_a_day(self):
        t.run(self.root, self.now, fetcher=self.ok_fetcher)
        calls = []
        self.assertIsNone(t.run(self.root, self.now.replace(hour=20), fetcher=lambda *a: calls.append(1) or RSS))
        self.assertEqual(calls, [])
        self.assertIsNotNone(t.run(self.root, self.now.replace(hour=20), force=True, fetcher=self.ok_fetcher))

    def test_failed_sources_are_skipped(self):
        def boom(url, rules):
            raise OSError("down")
        d = t.run(self.root, self.now, fetcher=boom)
        self.assertEqual(len(d["stats"]["sources_failed"]), len(RULES["trends"]["sources"]))
        self.assertTrue(d["topics"])           # evergreen + festivals still give a safe result

    def test_kill_switch(self):
        (self.root / "STOP_AUTONOMY").write_text("", encoding="utf-8")
        self.assertIsNone(t.run(self.root, self.now, fetcher=self.ok_fetcher))
        self.assertFalse((self.root / "autonomy" / "trends.json").exists())

    def test_trends_file_is_a_machine_notes_file(self):
        self.assertEqual(g.classify("autonomy/trends.json", RULES)[0], "state")
        for p in ("autonomy/trend_themes.json", "autonomy/festivals.json", "autonomy/trends.py", "autonomy/trend_feed.py"):
            self.assertEqual(g.classify(p, RULES)[0], "deny", p)       # the machine cannot edit its own themes, calendar or code


class Feed(unittest.TestCase):
    TOP = [{"id": "a", "topic": "A", "why_fits": "w", "story_angle": "angle a", "strength": 3, "expires": "2026-11-13"},
           {"id": "b", "topic": "B", "why_fits": "w", "story_angle": "angle b", "strength": 2, "expires": "2026-11-13"},
           {"id": "c", "topic": "C", "why_fits": "w", "story_angle": "angle c", "strength": 1, "expires": "2026-11-13"},
           {"id": "old", "topic": "Old", "why_fits": "w", "story_angle": "x", "strength": 9, "expires": "2026-11-10"},
           {"id": "bad", "topic": "Bad", "why_fits": "w", "story_angle": "the best price", "strength": 9, "expires": "2026-11-13"}]

    def test_pick_skips_expired_and_unsafe_and_limits_to_two(self):
        ids = [x["id"] for x in tf.pick(self.TOP, TODAY, RULES)]
        self.assertEqual(ids, ["a", "b"])

    def test_same_day_same_choice(self):
        self.assertEqual(tf.pick(self.TOP, TODAY, RULES), tf.pick(self.TOP, TODAY, RULES))

    def test_prompt_text_empty_without_file_or_when_all_expired(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(tf.prompt_text(Path(d), TODAY), "")
            (Path(d) / "autonomy").mkdir()
            (Path(d) / "autonomy" / "trends.json").write_text(json.dumps({"topics": self.TOP[3:4]}), encoding="utf-8")
            self.assertEqual(tf.prompt_text(Path(d), TODAY), "")
            (Path(d) / "autonomy" / "trends.json").write_text("not json", encoding="utf-8")
            self.assertEqual(tf.prompt_text(Path(d), TODAY), "")

    def test_prompt_text_has_the_safe_topics(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "autonomy").mkdir()
            (Path(d) / "autonomy" / "trends.json").write_text(json.dumps({"topics": self.TOP}), encoding="utf-8")
            txt = tf.prompt_text(Path(d), TODAY)
            self.assertIn("TREND OF THE DAY", txt)
            self.assertIn("angle a", txt)
            self.assertNotIn("price", txt)
            self.assertNotIn("angle c", txt)


class RefillHook(unittest.TestCase):
    SEED = {"situation": "x", "formula": {"name": "n", "pattern": "p", "example": "e"}}

    def test_prompt_unchanged_without_trends_and_gets_the_text_with_them(self):
        import refill_bank as rb
        real = tf.prompt_text
        try:
            tf.prompt_text = lambda *a, **k: ""
            random.seed(5); base = rb.prompt_for(self.SEED, ["t"], ["e"], "normal", 1)[1]["content"]
            tf.prompt_text = lambda *a, **k: "TREND OF THE DAY (mood):\n- A: angle a\n\n"
            random.seed(5); with_t = rb.prompt_for(self.SEED, ["t"], ["e"], "normal", 1)[1]["content"]
            tf.prompt_text = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
            random.seed(5); broken = rb.prompt_for(self.SEED, ["t"], ["e"], "normal", 1)[1]["content"]
        finally:
            tf.prompt_text = real
        self.assertNotIn("TREND OF THE DAY", base)
        self.assertIn("angle a", with_t)
        self.assertLess(with_t.index("angle a"), with_t.index("Titles already used"))
        self.assertEqual(with_t.replace("TREND OF THE DAY (mood):\n- A: angle a\n\n", ""), base)    # only that text was added
        self.assertEqual(broken, base)                                                              # an error means the old prompt

    def test_no_extra_model_call_is_added(self):
        src = (REPO / "autonomy" / "trend_feed.py").read_text(encoding="utf-8")
        for w in ("urllib", "requests", "chat/completions", "generativelanguage", "GEMINI"):
            self.assertNotIn(w, src, w)


if __name__ == "__main__":
    unittest.main()
