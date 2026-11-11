"""Phase 4 tests: learning loop (autonomy/learning.py), steering (autonomy/steer.py) and the additive hooks in refill_bank.py."""
import json
import random
import shutil
import sys
import tempfile
import unittest
import urllib.error
from datetime import datetime, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "autonomy"))
sys.path.insert(0, str(REPO / "reelfactory" / "scripts"))
sys.path.insert(0, str(REPO / "reelfactory"))
import guard as g  # noqa: E402
import learning as L  # noqa: E402
import steer as S  # noqa: E402

RULES = g.load_rules()
NOW = datetime(2026, 11, 11, 22, 0, tzinfo=g.IST)

BANK = """# header
## Two Whistles Talk | दो सीटी
plot: p
hook: सीटी किसकी? 🤔
card: क
- face-off | pintu | coach | सीटी | pintu: ये मेरी सीटी है! // coach: नहीं, मेरी!
- catch | aunty | pintu | coach | aunty: अब सीटी मेरी!

## Pappu Shop Plan | पप्पू
plot: p
hook: तीन गेंद, एक प्लान!
card: क
- face-off | pappu | chhotu | बल्ला | pappu: भाई लोग, मेरा प्लान! // chhotu: भैया, वज़न देखो!

## Mintu Trick | मिंटू
plot: p
hook: मिंटू ने क्या किया
- face-off | mintu | pappu | नो बॉल | mintu: नो बॉल! // pappu: ये क्या?

## Bruno Files One | ब्रूनो
plot: p
hook: गेंद कहाँ गई
series: Bruno Files
ep: 1
- face-off | golu | surya | गेंद | golu: मैंने देखा! // surya: क्या?

## Other A | ए
plot: p
hook: एक बात
- face-off | golu | surya | गेंद | golu: सुनो! // surya: क्या?

## Other B | बी
plot: p
hook: दो बात?
- face-off | golu | surya | गेंद | golu: सुनो! // surya: क्या?
"""


def post(i, slug_title, hours_ago=30, nets=("youtube", "instagram", "facebook")):
    due = NOW - timedelta(hours=hours_ago)
    res = {n: {"ok": True} for n in nets}
    notes = {"yt_video_id": f"yt{i}", "ig_media_id": f"ig{i}", "fb_video_id": f"fb{i}"}
    return {"title": f"{slug_title} DASHX", "when": due.isoformat(), "networks": list(nets), "results": res, "notes": notes, "status": "done"}


class FakeLive:
    def __init__(self, yt=None, ig=None, fb=None, ytok="T", mtok="M"):
        self._yt, self._ig, self._fb, self._ytok, self._mtok = yt, ig, fb, ytok, mtok
        self.calls = []

    def yt_token(self):
        return self._ytok

    def meta_token(self):
        return self._mtok

    def yt(self, ids, tok):
        self.calls.append(("yt", len(ids)))
        if isinstance(self._yt, Exception):
            raise self._yt
        return {i: {"views": 100 + n * 100, "likes": 5 + n, "comments": 1} for n, i in enumerate(ids)} if self._yt is None else self._yt

    def ig(self, mid, tok):
        self.calls.append(("ig", mid))
        if isinstance(self._ig, Exception):
            raise self._ig
        return {"likes": 3, "comments": 1}

    def fb(self, vid, tok):
        self.calls.append(("fb", vid))
        if isinstance(self._fb, Exception):
            raise self._fb
        return {"likes": 2, "comments": 0}


TITLES = ["two-whistles-talk", "pappu-shop-plan", "mintu-trick", "bruno-files-one", "other-a", "other-b"]


class Features(unittest.TestCase):
    def test_bank_features(self):
        b = L.parse_bank(BANK)
        self.assertEqual(b["bruno-files-one"]["format"], "series")
        self.assertEqual(b["pappu-shop-plan"]["format"], "shop")
        self.assertEqual(b["mintu-trick"]["format"], "rivalry")
        self.assertEqual(b["two-whistles-talk"]["format"], "normal")
        self.assertIn("pintu", b["two-whistles-talk"]["cast"])
        self.assertTrue(b["two-whistles-talk"]["first_line"].startswith("ये मेरी सीटी"))

    def test_hook_types(self):
        self.assertEqual(L.hook_type("सीटी किसकी? 🤔"), "question")
        self.assertEqual(L.hook_type("तीन गेंद, एक प्लान!"), "exclaim")
        self.assertEqual(L.hook_type("3 गेंद"), "number")
        self.assertEqual(L.hook_type("गेंद कहाँ गई"), "statement")
        self.assertEqual(L.hook_type(""), "statement")

    def test_garbage_never_raises(self):
        self.assertEqual(L.parse_bank(None), {})
        self.assertIsInstance(L.parse_bank("## \n## x |"), dict)


class Collect(unittest.TestCase):
    def posts(self):
        return [post(i, t) for i, t in enumerate(TITLES)]

    def test_all_sources_ok(self):
        live = FakeLive()
        m, av = L.collect(self.posts(), NOW, RULES, live)
        self.assertEqual(av, {"youtube_statistics": "ok", "instagram_counts": "ok", "facebook_counts": "ok"})
        self.assertEqual(len(m), 6)
        self.assertEqual(sum(1 for c in live.calls if c[0] == "yt"), 1)          # one batched YouTube call

    def test_denied_source_is_recorded_and_not_called_again(self):
        live = FakeLive(ig=L.Denied("HTTP 400: permission (#10)"))
        m, av = L.collect(self.posts(), NOW, RULES, live)
        self.assertTrue(av["instagram_counts"].startswith("DENIED"))
        self.assertIn("owner", av["instagram_counts"])
        self.assertEqual(sum(1 for c in live.calls if c[0] == "ig"), 1)           # stopped after the first denial
        self.assertEqual(av["youtube_statistics"], "ok")                         # the rest carries on
        self.assertEqual(av["facebook_counts"], "ok")

    def test_youtube_denied(self):
        _, av = L.collect(self.posts(), NOW, RULES, FakeLive(yt=L.Denied("HTTP 403: insufficient scope")))
        self.assertTrue(av["youtube_statistics"].startswith("DENIED"))

    def test_no_token_in_the_job(self):
        _, av = L.collect(self.posts(), NOW, RULES, FakeLive(ytok=None, mtok=None))
        self.assertEqual(set(av.values()), {"no token in this job"})

    def test_other_errors_do_not_break_the_loop(self):
        _, av = L.collect(self.posts(), NOW, RULES, FakeLive(fb=RuntimeError("HTTP 500")))
        self.assertTrue(av["facebook_counts"].startswith("error"))
        self.assertEqual(av["youtube_statistics"], "ok")

    def test_only_recent_real_reels_are_read(self):
        ps = [post(1, "a", hours_ago=2), post(2, "b", hours_ago=24 * 20), post(3, "c"), dict(post(4, "d"), title="META TEST golu DASHX"), dict(post(5, "e"), title="no brand tag")]
        m, _ = L.collect(ps, NOW, RULES, FakeLive())
        self.assertEqual(list(m), ["c DASHX"])

    def test_unposted_network_is_not_read(self):
        p = post(1, "a")
        p["results"]["instagram"] = {"ok": False}
        live = FakeLive()
        L.collect([p], NOW, RULES, live)
        self.assertFalse(any(c[0] == "ig" for c in live.calls))

    def test_error_text_never_carries_a_token(self):
        real = urllib.request.urlopen
        import io
        def boom(req, timeout=0):
            raise urllib.error.HTTPError("u", 400, "bad", {}, io.BytesIO(json.dumps({"error": {"message": "Invalid access_token=SECRET123 here"}}).encode()))
        try:
            urllib.request.urlopen = boom
            with self.assertRaises(L.Denied) as cm:
                L._get("https://graph.facebook.com/x?access_token=SECRET123")
        finally:
            urllib.request.urlopen = real
        self.assertNotIn("SECRET123", str(cm.exception))


import urllib.request  # noqa: E402


class Ids(unittest.TestCase):
    def test_ids_from_notes_or_the_saved_link(self):
        old = {"results": {"youtube": {"ok": True, "link": "https://www.youtube.com/shorts/AbCdEf12345"}, "facebook": {"ok": True, "link": "https://www.facebook.com/reel/777"},
                           "instagram": {"ok": True, "link": "instagram:999"}}, "notes": {}}
        self.assertEqual(L.video_ids(old), {"youtube": "AbCdEf12345", "facebook": "777", "instagram": "999"})
        self.assertEqual(L.video_ids({"results": {"instagram": {"ok": True, "link": "https://www.instagram.com/reel/XYZ/"}}, "notes": {}}), {})   # a permalink has no media id
        self.assertEqual(L.video_ids({"results": {"youtube": {"ok": False}}, "notes": {"yt_video_id": "x"}}), {})                             # not posted: not read

    def test_only_story_bank_reels_are_scored(self):
        ps = [post(i, t) for i, t in enumerate(TITLES)] + [dict(post(9, "ad-reel"), title="DASHX Ground Ad AI")]
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "poster").mkdir(); (root / "reelfactory" / "stories").mkdir(parents=True)
            (root / "reelfactory" / "stories" / "dialogue_bank.md").write_text(BANK, encoding="utf-8")
            (root / "poster" / "queue.json").write_text(json.dumps({"posts": ps}), encoding="utf-8")
            live = FakeLive()
            out = L.run(root, NOW, live=live)
            self.assertNotIn("DASHX Ground Ad AI", [r["title"] for r in out["reels"]])
            self.assertEqual(sum(1 for c in live.calls if c[0] == "yt"), 1)
            self.assertEqual(live.calls[0], ("yt", 6))                  # the ad was not even asked for


class Scoring(unittest.TestCase):
    def rows(self, n=6, views=lambda i: 100 * (i + 1)):
        ps = [post(i, TITLES[i % 6]) for i in range(n)]
        metrics = {p["title"]: {"youtube": {"views": views(i), "likes": i, "comments": 0}, "instagram": {"likes": i, "comments": 0}} for i, p in enumerate(ps)}
        return L.score_reels(ps, metrics, L.parse_bank(BANK), NOW, RULES)

    def test_not_enough_data_means_no_score(self):
        self.assertTrue(all("score" not in r for r in self.rows(4)))

    def test_scores_are_0_to_100_and_ordered(self):
        rows = self.rows(6)
        self.assertTrue(all("score" in r and 0 <= r["score"] <= 100 for r in rows))
        s = [r["score"] for r in rows]
        self.assertEqual(s, sorted(s))                          # more views and likes = higher score
        self.assertLess(s[0], s[-1])

    def test_zero_median_is_safe(self):
        rows = self.rows(6, views=lambda i: 0)
        self.assertTrue(all(0 <= r["score"] <= 100 for r in rows))

    def test_features_are_attached(self):
        r = self.rows(6)[0]
        self.assertEqual(r["format"], "normal")
        self.assertEqual(r["slot"], datetime.fromisoformat(post(0, "x")["when"]).strftime("%H:%M"))
        self.assertIn(r["hook_type"], ("question", "number", "exclaim", "statement"))

    def test_groups_need_min_size(self):
        rows = [{"score": 80, "format": "shop", "hook_type": "question", "cast": ["pappu"], "slot": "12:30"},
                {"score": 60, "format": "shop", "hook_type": "exclaim", "cast": ["pappu", "bruno"], "slot": "20:30"},
                {"score": 30, "format": "normal", "hook_type": "question", "cast": ["bruno"], "slot": "20:30"}]
        gr = L.groups(rows, RULES)
        self.assertEqual(gr["format"]["shop"], {"avg": 70.0, "n": 2})
        self.assertIsNone(gr["format"]["normal"]["avg"])         # one reel: not enough
        self.assertEqual(gr["character"]["pappu"]["n"], 2)

    def test_slot_hint_is_only_a_suggestion(self):
        h = L.slot_hint({"slot": {"12:30": {"avg": 40, "n": 3}, "20:30": {"avg": 70, "n": 3}}}, RULES)
        self.assertEqual(h["best_slot"], "20:30")
        self.assertIn("never changes", h["note"])
        self.assertIsNone(L.slot_hint({"slot": {"12:30": {"avg": 40, "n": 3}}}, RULES)["best_slot"])


class Run(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        (self.root / "poster").mkdir()
        (self.root / "reelfactory" / "stories").mkdir(parents=True)
        (self.root / "reelfactory" / "stories" / "dialogue_bank.md").write_text(BANK, encoding="utf-8")
        (self.root / "poster" / "queue.json").write_text(json.dumps({"posts": [post(i, t) for i, t in enumerate(TITLES)]}), encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_writes_only_its_own_notes(self):
        queue_before = (self.root / "poster" / "queue.json").read_bytes()
        d = L.run(self.root, NOW, live=FakeLive())
        self.assertTrue(d["enough_data"])
        self.assertTrue(d["steer"]["active"])
        self.assertEqual(sorted(p.name for p in (self.root / "autonomy").iterdir()), ["learning.json", "log.md", "metrics.json", "slot_hints.json"])
        self.assertEqual((self.root / "poster" / "queue.json").read_bytes(), queue_before)      # read-only for the queue
        self.assertIn("| info | learning |", (self.root / "autonomy" / "log.md").read_text(encoding="utf-8"))

    def test_once_a_day_and_kill_switch(self):
        L.run(self.root, NOW, live=FakeLive())
        calls = FakeLive()
        self.assertIsNone(L.run(self.root, NOW + timedelta(hours=3), live=calls))
        self.assertEqual(calls.calls, [])
        (self.root / "STOP_AUTONOMY").write_text("", encoding="utf-8")
        self.assertIsNone(L.run(self.root, NOW + timedelta(days=2), live=calls))
        self.assertEqual(calls.calls, [])

    def test_denied_data_is_reported_for_the_owner(self):
        d = L.run(self.root, NOW, live=FakeLive(ig=L.Denied("HTTP 400: (#10) permission")))
        self.assertTrue(d["availability"]["instagram_counts"].startswith("DENIED"))
        self.assertTrue(any("instagram_manage_insights" in x for x in d["needs_owner_for_more"]))
        self.assertIn("NEEDS OWNER", (self.root / "autonomy" / "log.md").read_text(encoding="utf-8"))

    def test_too_few_reels_means_steering_off(self):
        (self.root / "poster" / "queue.json").write_text(json.dumps({"posts": [post(i, t) for i, t in enumerate(TITLES[:3])]}), encoding="utf-8")
        d = L.run(self.root, NOW, live=FakeLive())
        self.assertFalse(d["enough_data"])
        self.assertFalse((self.root / "autonomy" / "slot_hints.json").exists())

    def test_the_loop_never_asks_for_a_new_permission(self):
        src = (REPO / "autonomy" / "learning.py").read_text(encoding="utf-8")
        for w in ('method="POST"', "youtubeanalytics", "insights?", "metric=", "scope=", "oauth2.googleapis.com", "grant_type", "refresh_token="):
            self.assertNotIn(w, src, w)
        self.assertTrue(RULES["learning"]["read_only"])
        self.assertEqual(g.classify("autonomy/learning.json", RULES)[0], "state")
        self.assertEqual(g.classify("autonomy/learning.py", RULES)[0], "deny")


class Steering(unittest.TestCase):
    DATA = {"steer": {"active": True, "dimensions": ["format", "hook_type"], "explore_share": 0.2},
            "groups": {"format": {"shop": {"avg": 80, "n": 4}, "normal": {"avg": 20, "n": 4}, "series": {"avg": None, "n": 1}, "rivalry": {"avg": 50, "n": 3}}}}
    OPTS = ["rivalry", "shop", "normal", "series", "normal"]

    def test_no_data_or_off_means_the_default(self):
        self.assertEqual(S.pick("format", self.OPTS, "DEF", data={}), "DEF")
        self.assertEqual(S.pick("format", self.OPTS, "DEF", data={"steer": {"active": False}}), "DEF")
        self.assertEqual(S.pick("format", self.OPTS, "DEF", Path(tempfile.mkdtemp())), "DEF")          # no learning.json at all

    def test_dimension_must_be_on_the_list(self):
        self.assertEqual(S.pick("character", ["a", "b"], "DEF", data=self.DATA), "DEF")

    def test_experiment_picks_the_least_tried(self):
        class R(random.Random):
            def random(self): return 0.05
        self.assertEqual(S.pick("format", self.OPTS, "DEF", data=self.DATA, rng=R()), "series")      # n=1 is the least tried

    def test_share_of_experiments_is_about_twenty_percent_and_winners_win_more(self):
        rng = random.Random(7)
        picks = [S.pick("format", self.OPTS, "DEF", data=self.DATA, rng=rng) for _ in range(4000)]
        series = picks.count("series") / len(picks)
        self.assertGreater(series, 0.17)                                   # series is only reached through experiments (+ its neutral weight)
        self.assertGreater(picks.count("shop"), picks.count("rivalry"))
        self.assertGreater(picks.count("rivalry"), 0)
        self.assertGreater(picks.count("normal"), 0)                       # a weak option keeps a chance (floor 0.25)
        self.assertTrue(set(picks) <= set(self.OPTS))

    def test_weights(self):
        self.assertEqual(S.weight("format", "shop", self.DATA), 1.6)
        self.assertEqual(S.weight("format", "normal", self.DATA), 0.4)
        self.assertEqual(S.weight("format", "series", self.DATA), 1.0)     # not enough reels: neutral
        self.assertEqual(S.weight("format", "unknown", self.DATA), 1.0)
        self.assertEqual(S.weight("format", "x", {"groups": {"format": {"x": {"avg": 1, "n": 5}}}}), 0.25)

    def test_pick_never_raises(self):
        self.assertEqual(S.pick("format", None, "DEF", data=self.DATA), "DEF")
        self.assertEqual(S.pick("format", self.OPTS, "DEF", data={"steer": "bad"}), "DEF")

    def test_pick_formula_falls_back_to_random_and_stays_in_the_list(self):
        cfg = json.loads((REPO / "reelfactory" / "stories" / "viral_formats.json").read_text(encoding="utf-8"))["formulas"]
        for _ in range(20):
            self.assertIn(S.pick_formula(cfg, Path(tempfile.mkdtemp())), cfg)


class RefillHooks(unittest.TestCase):
    def test_default_behaviour_without_learning_data(self):
        import refill_bank as rb
        self.assertEqual(rb.steer_format("shop"), "shop")
        cfg = [{"name": "a", "pattern": "p", "example": "x?"}, {"name": "b", "pattern": "p", "example": "y"}]
        self.assertIn(rb.steer_formula(cfg), cfg)

    def test_any_error_means_the_old_choice(self):
        import refill_bank as rb
        real = S.pick
        try:
            S.pick = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
            self.assertEqual(rb.steer_format("rivalry"), "rivalry")
        finally:
            S.pick = real

    def test_steering_makes_no_model_call(self):
        src = (REPO / "autonomy" / "steer.py").read_text(encoding="utf-8")
        for w in ("urllib", "requests", "generativelanguage", "chat/completions", "write_text"):
            self.assertNotIn(w, src, w)


if __name__ == "__main__":
    unittest.main()
