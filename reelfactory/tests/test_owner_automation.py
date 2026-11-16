"""Owner automation round: late daily report fix, post-mortem, grade mode for imported stories, read-only analytics (off by default), the hook card.
(The NotebookLM pack, trend study and propose-only improver moved into the ONE pattern pipeline: see test_pattern_engine.py.) All network and model calls are mocked."""
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "reelfactory" / "scripts"))
sys.path.insert(0, str(REPO / "reelfactory"))
sys.path.insert(0, str(REPO / "autonomy"))
import alerts  # noqa: E402
import analytics  # noqa: E402
import guard  # noqa: E402
import report  # noqa: E402

IST = guard.IST
REAL_RULES = guard.load_rules


def rules_with(*paths, improvers=None):
    def f():
        r = json.loads(json.dumps(REAL_RULES()))
        r["state_files"]["paths"] += list(paths)
        if improvers:
            r["improve"]["improvers_enabled"] = improvers
        return r
    return f


def tmp_root():
    d = Path(tempfile.mkdtemp())
    (d / "autonomy").mkdir()
    (d / "poster").mkdir()
    (d / "autonomy/TRUST_LADDER.md").write_bytes((REPO / "autonomy/TRUST_LADDER.md").read_bytes())
    return d


def post(title, when, ok=True, link=True, notes=None, results=None):
    res = results if results is not None else {n: ({"ok": ok, "link": f"https://x/{title}/{n}"} if link else {"ok": ok}) for n in ("youtube", "instagram", "facebook")}
    return {"title": f"{title} DASHX", "when": when.isoformat(), "networks": ["youtube", "instagram", "facebook"], "results": res, "notes": notes or {}, "status": "done"}


# ---------------------------------------------------------------- Fix A: the late daily report
class LateReport(unittest.TestCase):
    def test_a_morning_run_writes_yesterday(self):
        t = datetime(2026, 11, 16, 1, 59, tzinfo=IST)
        self.assertEqual(report.report_time(t).strftime("%Y-%m-%d %H:%M"), "2026-11-15 23:59")
        self.assertEqual(report.report_time(datetime(2026, 11, 15, 21, 5, tzinfo=IST)).date().isoformat(), "2026-11-15")

    def test_due_rules(self):
        root = tmp_root()
        self.assertFalse(report.due(root, datetime(2026, 11, 15, 15, 0, tzinfo=IST)))     # afternoon: never
        self.assertTrue(report.due(root, datetime(2026, 11, 15, 21, 30, tzinfo=IST)))
        self.assertTrue(report.due(root, datetime(2026, 11, 16, 2, 0, tzinfo=IST)))        # last night's was missed
        (root / "status").mkdir()
        (root / "status/daily.md").write_text("<!-- day: 2026-11-15 -->", encoding="utf-8")
        self.assertFalse(report.due(root, datetime(2026, 11, 16, 2, 0, tzinfo=IST)))
        self.assertFalse(report.due(root, datetime(2026, 11, 15, 22, 0, tzinfo=IST)))

    def test_alerts_run_writes_the_report_when_due_with_the_right_day(self):
        root = tmp_root()
        (root / "poster/queue.json").write_text(json.dumps({"posts": [post("late-one", datetime(2026, 11, 15, 20, 30, tzinfo=IST))]}), encoding="utf-8")
        out = alerts.run(root, datetime(2026, 11, 16, 1, 59, tzinfo=IST), api=None)
        self.assertEqual(out.get("report"), "2026-11-15")
        txt = (root / "status/daily.md").read_text(encoding="utf-8")
        self.assertIn("## 2026-11-15", txt)
        self.assertNotIn("## 2026-11-16", txt)
        self.assertIn("late-one", txt)                                                       # yesterday's reel is in yesterday's report
        self.assertNotIn("report", alerts.run(root, datetime(2026, 11, 16, 2, 29, tzinfo=IST), api=None))   # once only


class PostMortem(unittest.TestCase):
    def test_every_failure_gets_a_cause_and_a_next_step(self):
        now = datetime(2026, 11, 15, 22, 0, tzinfo=IST)
        bad = post("broken", now - timedelta(hours=2), results={"youtube": {"ok": True, "link": "l"}, "instagram": {"ok": False, "error": "token expired ERRDETAIL-77"}, "facebook": {"ok": True}})
        s = alerts.Signals(now, [bad], log_text=f"- {now.strftime('%Y-%m-%d')} 20:40 IST | ladder | drop | 2->1 | missed slot: x\n")
        txt = report.build(s)
        self.assertIn("### Post-mortem", txt)
        self.assertIn("broken / instagram", txt)
        self.assertIn("login token", txt)
        self.assertIn("Trust Ladder dropped one step", txt)
        self.assertNotIn("ERRDETAIL-77", txt)                                                # the error text itself is never copied

    def test_a_good_day(self):
        self.assertIn("Nothing went wrong today.", report.build(alerts.Signals(datetime(2026, 11, 15, 22, 0, tzinfo=IST), [])))


# ---------------------------------------------------------------- grade mode (Story Refill, inside the daily cap)
class GradeMode(unittest.TestCase):
    def setUp(self):
        import refill_bank as rb
        self.rb = rb
        d = Path(tempfile.mkdtemp())
        self.bank, self.usage, self.req, self.log = d / "bank.md", d / "usage.json", d / "req.json", d / "log.md"
        self.bank.write_text("# bank\n\n## Alpha | अ\nplot: p\nending: e!\n\n## Beta | ब\nplot: p\nending: e!\n\n## Gamma | ग\nplot: p\nending: e!\n", encoding="utf-8")
        self.usage.write_text(json.dumps({"day": "x", "calls": 0, "cap": 12}), encoding="utf-8")
        self.req.write_text(json.dumps({"titles": ["Alpha", "Beta", "Gamma", "Missing"]}), encoding="utf-8")
        self.p = [mock.patch.object(rb, "BANK", self.bank), mock.patch.object(rb, "USAGE", self.usage), mock.patch.object(rb, "GRADE_REQUEST", self.req),
                  mock.patch.object(rb, "LOG", self.log)]
        for x in self.p:
            x.start()
        rb.GRADES.clear()
        rb.CALLS.update(n=0, cap=12)
        rb.STATE.update(quota_hit=False)

    def tearDown(self):
        for x in self.p:
            x.stop()
        self.rb.GRADES.clear()

    def judge(self, scores):
        it = iter(scores)

        def j(block):
            self.rb.CALLS["n"] += 1
            return next(it)
        return j

    def test_grades_within_the_cap_and_keeps_the_results(self):
        rb = self.rb
        rb.CALLS.update(n=10, cap=12)                                                         # only 2 calls left today
        good = (True, {"meerut_feel": 8, "twist": 7, "funny": 8, "natural_hindi": 8, "kid_safe": True, "typos": [], "issue": "ok"})
        low = (False, {"meerut_feel": 3, "twist": 4, "funny": 5, "natural_hindi": 7, "kid_safe": True, "typos": ["x"], "issue": "weak twist"})
        with mock.patch.object(rb, "judge", self.judge([good, low, good])):
            done, failed, left = rb.grade_step()
        self.assertEqual((done, failed, left), (2, 1, 1))                                     # Missing is not in the bank: never asked
        self.assertLessEqual(rb.CALLS["n"], 12)
        saved = json.loads(self.usage.read_text(encoding="utf-8"))
        self.assertEqual(saved["grade"]["Alpha"]["ok"], True)
        self.assertEqual(saved["grade"]["Beta"]["meerut"], 3)
        self.assertEqual((saved["calls"], saved["cap"]), (12, 12))
        self.assertIn("grade FAIL | Beta", self.log.read_text(encoding="utf-8"))
        self.assertIn("## Beta", self.bank.read_text(encoding="utf-8"))                      # nothing is removed

    def test_an_unavailable_judge_stops_and_records_nothing(self):
        rb = self.rb
        with mock.patch.object(rb, "judge", self.judge([(False, {"issue": "judge unavailable (HTTP 0)"})])):
            self.assertEqual(rb.grade_step(), (0, 0, 3))
        self.assertNotIn("grade", json.loads(self.usage.read_text(encoding="utf-8")))

    def test_a_later_save_keeps_the_grades(self):
        rb = self.rb
        rb.GRADES["Alpha"] = {"ok": True}
        rb.save_usage()
        rb.GRADES.clear()
        self.assertEqual(rb.grade_state(), {"Alpha": {"ok": True}})
        self.assertEqual(rb.grade_pending(), ["Beta", "Gamma"])

    def test_the_real_request_lists_the_90_imported_stories(self):
        req = json.loads((REPO / "reelfactory/stories/grade_request.json").read_text(encoding="utf-8"))
        bank = (REPO / "reelfactory/stories/dialogue_bank.md").read_text(encoding="utf-8")
        self.assertEqual(len(req["titles"]), 90)
        self.assertTrue(all(f"## {t} |" in bank for t in req["titles"]))

    def test_the_report_shows_grade_progress(self):
        s = alerts.Signals(datetime(2026, 11, 15, 22, 0, tzinfo=IST), [], usage={"grade": {"A": {"ok": True}, "B": {"ok": False}}})
        txt = report.build(s)
        self.assertIn("2 graded so far, 1 below the bar (B)", txt)


# ---------------------------------------------------------------- read-only analytics: OFF until the owner adds the secret
class Analytics(unittest.TestCase):
    POSTS = [post("a", datetime(2026, 11, 15, 12, 30, tzinfo=IST), notes={"yt_video_id": "Y1", "ig_media_id": "I1", "fb_video_id": "F1"})]

    def test_off_by_default_nothing_is_called(self):
        calls = []
        self.assertIsNone(analytics.collect(self.POSTS, {"META_PAGE_TOKEN": "x", "YT_REFRESH_TOKEN": "y", "YT_CLIENT_ID": "c", "YT_CLIENT_SECRET": "s"},
                                            get=lambda *a, **k: calls.append(a)))
        self.assertEqual(calls, [])
        self.assertIsNone(analytics.run(tmp_root(), env={}))

    def test_each_source_needs_its_own_new_secret(self):
        on = analytics.enabled({"YT_ANALYTICS_REFRESH_TOKEN": "t", "YT_CLIENT_ID": "c", "YT_CLIENT_SECRET": "s"})
        self.assertEqual(on, {"yt_analytics": True, "ig_insights": False, "fb_insights": False})
        self.assertEqual(analytics.SOURCES["yt_analytics"]["scope"], "https://www.googleapis.com/auth/yt-analytics.readonly")

    def test_mocked_reads(self):
        env = {"YT_ANALYTICS_REFRESH_TOKEN": "t", "YT_CLIENT_ID": "c", "YT_CLIENT_SECRET": "s", "META_INSIGHTS_TOKEN": "m", "IG_USER_ID": "u", "FB_PAGE_ID": "p"}

        def get(url, headers=None, data=None):
            if "oauth2" in url:
                return {"access_token": "AT"}
            if "youtubeanalytics" in url:
                return {"columnHeaders": [{"name": n} for n in ("video", "views", "averageViewDuration", "averageViewPercentage", "subscribersGained")],
                        "rows": [["Y1", 500, 11.5, 62.0, 3]]}
            if "/I1/insights" in url:
                return {"data": [{"name": "reach", "values": [{"value": 900}]}, {"name": "saved", "values": [{"value": 4}]}]}
            if "/F1/video_insights" in url:
                import urllib.error
                raise urllib.error.HTTPError(url, 403, "no", {}, None)
            raise AssertionError(url)
        res = analytics.collect(self.POSTS, env, get, today=datetime(2026, 11, 16).date())
        self.assertEqual(res["yt_analytics"]["by_reel"]["a DASHX"]["avg_view_percent"], 62.0)
        self.assertEqual(res["ig_insights"]["by_reel"]["a DASHX"], {"reach": 900, "saved": 4})
        self.assertEqual(res["fb_insights"]["status"], "DENIED (HTTP 403)")

    def test_the_token_never_lands_in_the_output(self):
        env = {"META_INSIGHTS_TOKEN": "SECRET123", "IG_USER_ID": "u"}
        res = analytics.collect(self.POSTS, env, lambda url, **k: {"data": []})
        self.assertNotIn("SECRET123", json.dumps(res))


class HookTitle(unittest.TestCase):
    def test_bigger_card_inside_the_safe_area(self):
        src = (REPO / "reelfactory/src/reel/reelScene.tsx").read_text(encoding="utf-8")
        self.assertIn("const CARD_FONT = 112;", src)
        self.assertIn("const CARD_Y = -620;", src)
        lines, font = 2, 112
        top = 960 - 620 - (lines * font * 1.25 + 40) / 2
        self.assertGreaterEqual(top, 150)                                                      # two-line card still below the top safe area


if __name__ == "__main__":
    unittest.main()
