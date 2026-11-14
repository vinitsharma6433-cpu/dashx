import json, os, sys, tempfile, unittest
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import trend_radar as tr

PAGES = {"red-tennis-ball-cricket-110g", "green-tennis-ball-cricket-90g", "yellow-tennis-ball-cricket-90g", "heavy-tennis-ball-cricket-90g-110g",
         "light-tennis-ball-cricket-90g", "cricket-tennis-ball-pack-of-10-munna", "tennis-ball-cricket-material-weight-size",
         "cricket-tennis-ball-weights-packs-variants", "cricket-with-tennis-ball-guide"}
TODAY = date(2026, 11, 16)


class Rule(unittest.TestCase):
    def test_off_topic_is_dropped(self):
        for kw in ["cricket bat and tennis ball", "tennis ball price", "buy tennis ball online", "tennis ball wholesale", "tennis ball shop near me",
                   "tennis ball cricket delhi", "tennis ball meerut", "kookaburra tennis ball", "ss tennis ball", "tennis ball flipkart",
                   "how to bowl tennis ball", "tennis ball batting tips", "tennis ball cricket tutorial", "cricket gloves with ball", "cheap tennis ball"]:
            self.assertFalse(tr.keyword_ok(kw), kw)

    def test_dashx_balls_are_kept(self):
        for kw in ["heavy tennis ball for cricket", "red tennis ball cricket", "tennis ball 110g", "tennis ball pack of 10", "how to choose tennis ball for cricket",
                   "tennis ball care", "tennis ball for gully cricket", "क्रिकेट टेनिस बॉल", "cricket tennis ball kaise chune"]:
            self.assertTrue(tr.keyword_ok(kw), kw)

    def test_language_and_intent(self):
        self.assertEqual(tr.language_of("क्रिकेट टेनिस बॉल"), "hi")
        self.assertEqual(tr.language_of("cricket tennis ball kaise chune"), "hinglish")
        self.assertEqual(tr.language_of("heavy tennis ball"), "en")
        self.assertEqual(tr.intent_of("how to choose tennis ball"), "informational")
        self.assertEqual(tr.intent_of("heavy tennis ball"), "commercial-investigation")


class Pages(unittest.TestCase):
    def test_existing_page_means_update(self):
        self.assertEqual(tr.cluster_of("red tennis ball cricket", PAGES), ("color-red", "/blog/red-tennis-ball-cricket-110g", "update"))
        self.assertEqual(tr.cluster_of("tennis ball pack of 10", PAGES)[2], "update")
        self.assertEqual(tr.cluster_of("how to choose tennis ball", PAGES)[0], "how-to-choose")

    def test_no_page_means_new_topic(self):
        self.assertEqual(tr.cluster_of("tennis ball care", PAGES), ("care", "", "new"))
        self.assertEqual(tr.cluster_of("tennis ball for school sports day", PAGES)[2], "new")

    def test_page_missing_from_sitemap_becomes_new(self):
        self.assertEqual(tr.cluster_of("red tennis ball", set())[2], "new")
        self.assertEqual(tr.cluster_of("red tennis ball", None)[2], "update")   # sitemap unreadable: assume the page exists


class Seasonal(unittest.TestCase):
    CAL = {"events": [{"id": "diwali", "months": [10, 11], "modifiers": ["tennis ball for diwali cricket match"]},
                      {"id": "summer", "months": [5, 6], "modifiers": ["tennis ball for summer holidays practice"]}]}

    def test_active_and_next_month(self):
        self.assertIn("tennis ball for diwali cricket match", tr.seasonal_ideas(self.CAL, date(2026, 11, 3)))
        self.assertEqual(tr.seasonal_ideas(self.CAL, date(2026, 11, 3))["tennis ball for diwali cricket match"][0], 2.0)
        self.assertIn("tennis ball for summer holidays practice", tr.seasonal_ideas(self.CAL, date(2026, 4, 20)))   # starts next month: smaller boost
        self.assertNotIn("tennis ball for summer holidays practice", tr.seasonal_ideas(self.CAL, date(2026, 8, 1)))

    def test_shipped_calendar_is_valid_and_clean(self):
        cal = json.load(open(os.path.join(os.path.dirname(__file__), "..", "data", "seasonal_calendar.json"), encoding="utf-8"))
        for ev in cal["events"]:
            self.assertTrue(all(1 <= m <= 12 for m in ev["months"]))
            for m in ev["modifiers"]:
                self.assertTrue(tr.keyword_ok(m), m)


class Merge(unittest.TestCase):
    def test_first_seen_is_kept_and_last_seen_moves(self):
        recs, n = tr.merge_keywords([], {"red tennis ball": 80, "tennis ball price": 90}, {}, TODAY, PAGES)
        self.assertEqual(n, 1)                                  # the price keyword never gets in
        self.assertEqual(recs[0]["first_seen"], "2026-11-16")
        later = date(2026, 11, 23)
        recs2, n2 = tr.merge_keywords(recs, {"red tennis ball": 60}, {}, later, PAGES)
        self.assertEqual((n2, recs2[0]["first_seen"], recs2[0]["last_seen"], recs2[0]["status"]), (0, "2026-11-16", "2026-11-23", "active"))

    def test_stale_after_60_days_and_back_to_active(self):
        recs, _ = tr.merge_keywords([], {"red tennis ball": 80}, {}, date(2026, 1, 1), PAGES)
        recs, _ = tr.merge_keywords(recs, {"green tennis ball": 50}, {}, date(2026, 4, 1), PAGES)
        self.assertEqual([r["status"] for r in recs if r["keyword"] == "red tennis ball"], ["stale"])
        recs, _ = tr.merge_keywords(recs, {"red tennis ball": 50}, {}, date(2026, 4, 8), PAGES)
        self.assertEqual([r["status"] for r in recs if r["keyword"] == "red tennis ball"], ["active"])

    def test_record_has_every_field(self):
        recs, _ = tr.merge_keywords([], {"heavy tennis ball": 70}, {"heavy tennis ball": "autosuggest"}, TODAY, PAGES)
        self.assertEqual(sorted(recs[0]), sorted(["keyword", "language", "source", "intent", "cluster", "target_page", "status", "first_seen", "last_seen", "trend_score"]))


class Queue(unittest.TestCase):
    def recs(self, n):
        kws = ["red tennis ball", "green tennis ball", "yellow tennis ball", "heavy tennis ball", "light tennis ball", "tennis ball care",
               "tennis ball for school sports day", "tennis ball for gully cricket", "tennis ball pack of 10", "tennis ball 110g"]
        r, _ = tr.merge_keywords([], {k: 100 - i for i, k in enumerate(kws[:n])}, {}, TODAY, PAGES)
        return r

    def test_at_most_five_per_week(self):
        q, added = tr.build_queue(self.recs(10), [], TODAY, PAGES)
        self.assertEqual(len(added), 5)
        self.assertEqual(len(q), 5)

    def test_one_intent_per_page_and_cluster(self):
        r, _ = tr.merge_keywords([], {"red tennis ball": 90, "red tennis ball cricket": 80, "tennis ball care": 70, "tennis ball maintain": 60}, {}, TODAY, PAGES)
        q, added = tr.build_queue(r, [], TODAY, PAGES)
        self.assertEqual(sorted(t["keyword"] for t in added), ["red tennis ball", "tennis ball care"])   # 2nd red and 2nd care idea wait

    def test_next_week_does_not_repeat_queued_work(self):
        r = self.recs(6)
        q1, a1 = tr.build_queue(r, [], TODAY, PAGES)
        q2, a2 = tr.build_queue(r, q1, date(2026, 11, 23), PAGES)
        self.assertTrue(set(t["id"] for t in a1).isdisjoint(t["id"] for t in a2))
        self.assertLessEqual(len(q2), 10)

    def test_low_score_is_ignored(self):
        r, _ = tr.merge_keywords([], {"red tennis ball": 10}, {}, TODAY, PAGES)
        self.assertEqual(tr.build_queue(r, [], TODAY, PAGES)[1], [])


class Run(unittest.TestCase):
    def fetch(self, url, timeout=20):
        if "sitemap.xml" in url:
            return ('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + "".join("<url><loc>https://x/blog/%s</loc></url>" % s for s in PAGES) + "</urlset>").encode()
        return json.dumps(["q", ["red tennis ball cricket", "tennis ball price", "heavy tennis ball for cricket", "tennis ball care tips", "kookaburra tennis ball"]]).encode()

    def test_full_run_writes_both_files(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(tr.run(TODAY, self.fetch, lambda s: None, d), 0)
            kws = json.load(open(os.path.join(d, "keywords.json"), encoding="utf-8"))
            q = json.load(open(os.path.join(d, "topic_queue.json"), encoding="utf-8"))
            names = [k["keyword"] for k in kws]
            self.assertIn("red tennis ball cricket", names)
            self.assertNotIn("tennis ball price", names)
            self.assertNotIn("kookaburra tennis ball", names)
            self.assertLessEqual(len(q), 5)
            self.assertTrue(all(t["status"] == "queued" for t in q))

    def test_pause_file_stops_everything(self):
        with tempfile.TemporaryDirectory() as d:
            open(os.path.join(d, "PAUSE_AUTOPILOT"), "w").close()
            self.assertEqual(tr.run(TODAY, self.fetch, lambda s: None, d), 0)
            self.assertEqual(sorted(os.listdir(d)), ["PAUSE_AUTOPILOT"])     # nothing was written

    def test_everything_failing_is_a_red_run(self):
        def dead(url, timeout=20):
            raise OSError("no network")
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(tr.run(TODAY, dead, lambda s: None, d), 1)       # no seasonal calendar in this folder either

    def test_seasonal_only_still_works_when_autosuggest_is_down(self):
        def dead(url, timeout=20):
            raise OSError("no network")
        with tempfile.TemporaryDirectory() as d:
            json.dump(Seasonal.CAL, open(os.path.join(d, "seasonal_calendar.json"), "w"))
            self.assertEqual(tr.run(date(2026, 11, 3), dead, lambda s: None, d), 0)
            self.assertIn("tennis ball for diwali cricket match", [k["keyword"] for k in json.load(open(os.path.join(d, "keywords.json")))])

    def test_gsc_rows_parser(self):
        self.assertEqual(tr.gsc_rows_to_keywords([{"keys": ["Red Tennis Ball"], "impressions": 12}, {"keys": []}]), {"red tennis ball": 12.0})


if __name__ == "__main__":
    unittest.main()
