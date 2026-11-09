"""Unit tests for the factory logic that needs no video rendering. Run: npm test"""

import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from factory import config, db, ops, repair, seo, youtube, backup, log  # noqa: E402
from factory import story as story_mod  # noqa: E402
from factory.bridge import daily  # noqa: E402


class TempDB(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.p1 = mock.patch.object(db, "DB_FILE", Path(self.tmp.name) / "t.db")
        self.p2 = mock.patch.object(db, "DATA", Path(self.tmp.name))
        self.p1.start()
        self.p2.start()

    def tearDown(self):
        self.p1.stop()
        self.p2.stop()
        self.tmp.cleanup()


class TestConfig(unittest.TestCase):
    def test_defaults_and_upload_off(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            for k in list(os.environ):
                if k in config.Config.__dataclass_fields__:
                    del os.environ[k]
            c = config.load()
        self.assertEqual(c.DAILY_REEL_LIMIT, 5)
        self.assertFalse(c.AUTO_UPLOAD)  # must stay off until the owner enables it
        self.assertTrue(c.AUTO_QC and c.AUTO_REPAIR and c.AUTO_SEO and c.AUTO_THUMBNAIL and c.AUTO_GENERATE)

    def test_env_override_and_bad_values(self):
        with mock.patch.dict(os.environ, {"DAILY_REEL_LIMIT": "7", "AUTO_SEO": "false", "MAX_REPAIRS": "abc", "SOURCE": "nonsense"}):
            c = config.load()
        self.assertEqual(c.DAILY_REEL_LIMIT, 7)
        self.assertFalse(c.AUTO_SEO)
        self.assertEqual(c.MAX_REPAIRS, 3)  # bad value falls back to the default
        self.assertEqual(c.SOURCE, "auto")

    def test_public_config_has_no_secrets(self):
        keys = " ".join(config.Config().public()).lower()
        for bad in ("secret", "token", "password", "key"):
            self.assertNotIn(bad, keys)


class TestDB(TempDB):
    def test_run_job_stats_usage(self):
        r = db.start_run("2026-01-01", 5, "bank")
        j = db.create_job(r, "x", "2026-01-01", "bank")
        db.update_job(j, status="ready", qc_score=95, cast_json=json.dumps(["sachin", "golu"]), seconds=60)
        db.add_failure(j, "first_frame", "render", "dark")
        self.assertEqual(db.stats()["ready"], 1)
        self.assertEqual(db.character_usage()["golu"], 1)
        self.assertEqual(db.passed_today("2026-01-01"), 1)
        self.assertEqual(db.template_failure_rates(), {"render": 1.0})


def bank_story(title_en):
    b = next(b for b in daily.parse_bank() if b["title_en"] == title_en)
    data = {"title_hi": b["title_hi"], "title_en": b["title_en"], "plot_en": b["plot_en"], "scenes": b["rows"], "closing_hi": b["closing"]}
    st, probs = daily.from_llm_data(data, 0, {})
    assert st and not probs, probs
    return st


class TestStory(unittest.TestCase):
    def test_similarity(self):
        self.assertGreater(story_mod.similarity("सूर्या ने गेंद डाली", "सूर्या ने गेंद डाली!"), 0.9)
        self.assertLess(story_mod.similarity("सूर्या ने गेंद डाली", "आंटी की खिड़की"), 0.5)

    def test_orthography_catches_malformed_hindi(self):
        self.assertTrue(story_mod.orthography_problems("ाबाल"))
        self.assertTrue(story_mod.orthography_problems("बॉलx"))
        self.assertEqual(story_mod.orthography_problems("सूर्या ने गेंद डाली।"), [])

    def test_good_story_scores_high_and_duplicate_scores_low(self):
        st = bank_story("Hero Dadaji")
        empty = {"plots": [], "titles": [], "endings": [], "lines": []}
        good = story_mod.score_story(st, ref=empty)
        self.assertGreaterEqual(good["score"], 85)
        dup_ref = {"plots": [st["plot_en"]], "titles": [st["title_hi"]], "endings": [st["closing"]], "lines": [s["line"] for s in st["scenes"]]}
        dup = story_mod.score_story(st, ref=dup_ref)
        self.assertLess(dup["score"], 70)  # an exact repeat must be rejected by the default threshold
        self.assertTrue(dup["notes"])

    def test_weak_story_rejected(self):
        st = bank_story("Hero Dadaji")
        st["closing"] = "ठीक"
        st["scenes"][0]["line"] = "ठीक है"
        for s in st["scenes"]:
            s["template"] = "catch"
        self.assertLess(story_mod.score_story(st, ref={"plots": [], "titles": [], "endings": [], "lines": []})["score"], 70)


class TestSEO(unittest.TestCase):
    def test_generate_and_score(self):
        script = {"title": "चाय वाला कैच", "scenes": [{"voice": "सूर्या ने गेंद डाली।"}, {"voice": "सचिन ने शॉट मारा!"}, {"voice": "दादाजी ने कैच पकड़ा!"}, {"voice": "खेलो डैश एक्स के साथ!"}],
                  "story": {"closing": "गली क्रिकेट का मज़ा!"}}
        m = seo.generate(script, ["Gali Cricket", "Family Comedy"], ["sachin", "surya", "dadaji"])
        self.assertGreaterEqual(m["seo_score"], 90)
        self.assertLessEqual(len(m["title"]), 60)
        self.assertLessEqual(sum(len(t) + 1 for t in m["tags"]), 450)
        self.assertIn("#Shorts", m["hashtags"])
        self.assertTrue(m["made_with_ai"])
        for bad in ("best", "premium", "guaranteed", "₹"):
            self.assertNotIn(bad, (m["title"] + m["description"]).lower().replace("https://", ""))


class TestRepairPlan(unittest.TestCase):
    def test_stage_selection_and_escalation(self):
        f = [{"id": "duration", "stage": "fit", "detail": "x"}, {"id": "first_frame", "stage": "render", "detail": "y"}]
        p1 = repair.plan(f, 1)
        self.assertEqual(p1["start"], "fit")  # earliest responsible stage, never earlier
        self.assertFalse(p1["swap_story"])
        self.assertEqual(repair.plan(f, 2)["params"]["fit_safety"], 0.6)
        self.assertTrue(repair.plan(f, 3)["swap_story"])  # attempt 3 changes the story
        self.assertTrue(repair.plan([{"id": "hindi_spelling", "stage": "story", "detail": "z"}], 1)["swap_story"])
        self.assertEqual(repair.plan([{"id": "thumbnail_quality", "stage": "thumbnail", "detail": ""}], 1)["start"], "thumbnail")


class TestOps(unittest.TestCase):
    def test_lock_prevents_second_instance(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(ops, "LOCK", Path(d) / "run.lock"), mock.patch.object(ops, "DATA", Path(d)):
            self.assertTrue(ops.acquire_lock())
            with mock.patch.object(ops, "pid_alive", return_value=True), mock.patch("os.getpid", return_value=999999):
                self.assertFalse(ops.acquire_lock())  # a live owner blocks a second run
            with mock.patch.object(ops, "pid_alive", return_value=False), mock.patch("os.getpid", return_value=999999):
                self.assertTrue(ops.acquire_lock())  # a stale lock is taken over

    def test_finished_videos_are_protected(self):
        ready = ops.ROOT / "output" / "ready" / "x" / "a.mp4"
        self.assertTrue(ops.is_protected(ready))
        self.assertFalse(ops.safe_delete(ready))
        for p in ("reels", "stories", "assets", "src", "backups"):
            self.assertTrue(ops.is_protected(ops.ROOT / p / "anything"))
        with tempfile.TemporaryDirectory(dir=ops.DATA) if ops.DATA.exists() else tempfile.TemporaryDirectory() as d:
            pass


class TestYouTube(TempDB):
    def test_nothing_uploads_by_default(self):
        cfg = config.Config()
        r = youtube.publish_job(1, Path("x.mp4"), None, {}, cfg)
        self.assertEqual(r["status"], "skipped")
        cfg.AUTO_UPLOAD = True  # enabled but no credentials: still nothing happens
        with mock.patch.dict(os.environ, {"YOUTUBE_CLIENT_SECRET_FILE": ""}):
            self.assertEqual(youtube.publish_job(1, Path("x.mp4"), None, {}, cfg)["status"], "skipped")

    def test_upload_flow_with_retry_and_no_secret_in_logs(self):
        with tempfile.TemporaryDirectory() as d:
            cs, tok, vid = Path(d, "cs.json"), Path(d, "tok.json"), Path(d, "v.mp4")
            cs.write_text(json.dumps({"installed": {"client_id": "id", "client_secret": "SECRET-VALUE"}}))
            tok.write_text(json.dumps({"refresh_token": "REFRESH-VALUE"}))
            vid.write_bytes(b"0" * 100)
            calls = []

            def transport(method, url, headers=None, data=None, timeout=0):
                calls.append((method, url))
                if "oauth2" in url:
                    return 200, json.dumps({"access_token": "ACCESS"}).encode(), {}
                if "uploadType=resumable" in url:
                    n = sum(1 for c in calls if "uploadType=resumable" in c[1])
                    return (503, b"", {}) if n == 1 else (200, b"", {"Location": "https://upload/session"})
                if url == "https://upload/session":
                    return 200, json.dumps({"id": "VID123"}).encode(), {}
                return 200, b"{}", {}

            cfg = config.Config(AUTO_UPLOAD=True)
            with mock.patch.dict(os.environ, {"YOUTUBE_CLIENT_SECRET_FILE": str(cs), "YOUTUBE_TOKEN_FILE": str(tok)}):
                from datetime import datetime, timezone
                vid_id = youtube.upload(vid, None, {"title": "t", "description": "d", "tags": ["a"]}, cfg, datetime.now(timezone.utc), transport, sleep=lambda s: None)
            self.assertEqual(vid_id, "VID123")
            self.assertGreaterEqual(sum(1 for c in calls if "uploadType=resumable" in c[1]), 2)  # the 503 was retried
            md = youtube.build_metadata({"title": "t", "description": "d", "tags": []}, datetime.now(timezone.utc), "public")
            self.assertEqual(md["status"]["privacyStatus"], "private")  # scheduled videos start private
            self.assertTrue(md["status"]["containsSyntheticMedia"])
            self.assertFalse(md["status"]["selfDeclaredMadeForKids"])
            self.assertNotIn("SECRET-VALUE", log.redact("client_secret=SECRET-VALUE access_token=ACCESS"))
            self.assertNotIn("ACCESS", log.redact("access_token=ACCESS"))


class TestBackup(unittest.TestCase):
    def test_backup_roundtrip_never_touches_live_files(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(backup, "BACKUPS", Path(d)):
            z = backup.create("unit")
            self.assertTrue(z.exists())
            import zipfile
            names = zipfile.ZipFile(z).namelist()
            self.assertIn("package.json", names)
            self.assertFalse([n for n in names if n.endswith(".mp4") and not n.startswith("evidence/")])  # rendered videos are never zipped; evidence videos ARE
            target = backup.restore(z)
            try:
                self.assertTrue((target / "package.json").exists())
                self.assertNotEqual(target, backup.ROOT)
            finally:
                import shutil
                shutil.rmtree(target)


class TestDashboard(TempDB):
    def test_api_and_post_protection(self):
        from http.server import ThreadingHTTPServer
        from factory import dashboard
        srv = ThreadingHTTPServer(("127.0.0.1", 0), dashboard.Handler)
        port = srv.server_address[1]
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            s = json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/api/status", timeout=30))
            self.assertIn("bank_left", s)
            self.assertFalse(s["config"]["AUTO_UPLOAD"])
            self.assertNotIn("client_secret", json.dumps(s).lower().replace("client_secret_configured", ""))
            req = urllib.request.Request(f"http://127.0.0.1:{port}/api/stop", data=b"{}", method="POST")
            with self.assertRaises(urllib.error.HTTPError) as cm:
                urllib.request.urlopen(req, timeout=10)
            self.assertEqual(cm.exception.code, 403)  # no X-Factory header -> refused
            html = urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=10).read().decode()
            self.assertIn("DASHX Control Center", html)
        finally:
            srv.shutdown()


if __name__ == "__main__":
    unittest.main()
