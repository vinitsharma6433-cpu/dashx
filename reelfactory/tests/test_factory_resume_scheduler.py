"""Resume of interrupted jobs, duplicate-production protection and the scheduler's due() logic (all stubbed)."""

import json
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from factory import config, db, pipeline, scheduler  # noqa: E402

ROOT = pipeline.ROOT


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.patches = [mock.patch.object(db, "DB_FILE", Path(self.tmp.name) / "t.db"), mock.patch.object(db, "DATA", Path(self.tmp.name))]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()


class TestResume(Base):
    def setUp(self):
        super().setUp()
        self.d = ROOT / "reels" / "_resumetest"
        (self.d / "audio").mkdir(parents=True, exist_ok=True)
        (self.d / "script.json").write_text(json.dumps({"title": "ट", "scenes": [], "story": {"plot": "p", "closing": "c"}}, ensure_ascii=False), encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)
        super().tearDown()

    def test_interrupted_job_resumes_from_the_right_stage(self):
        run = db.start_run("2026-01-01", 1, "bank")
        jid = db.create_job(run, "_resumetest", "2026-01-01", "bank")  # status 'running' = interrupted
        db.update_job(jid, cast_json=json.dumps(["sachin"]))
        pm = pipeline.ProductionManager(config.Config())
        seen = []
        pm._finish = lambda job, start, *a, **k: seen.append((job.name, start)) or {"name": job.name, "status": "ready"}
        pm.resume(run, "2026-01-01", {})
        self.assertEqual(seen, [("_resumetest", "voice")])  # no voice files yet -> start at the voice
        (self.d / "audio" / "durations.json").write_text("{}")
        pm.resume(run, "2026-01-01", {})
        self.assertEqual(seen[-1], ("_resumetest", "fit"))  # voice already exists -> do not make it again

    def test_job_with_no_script_is_closed_not_resumed(self):
        run = db.start_run("2026-01-01", 1, "bank")
        jid = db.create_job(run, "_no_such_reel", "2026-01-01", "bank")
        pm = pipeline.ProductionManager(config.Config())
        pm._finish = mock.Mock()
        pm.resume(run, "2026-01-01", {})
        pm._finish.assert_not_called()
        self.assertEqual(db.q("SELECT status FROM jobs WHERE id=?", (jid,))[0]["status"], "failed")


class TestNoDuplicateProduction(Base):
    def test_target_counts_reels_already_ready_today(self):
        day = time.strftime("%Y-%m-%d")
        run = db.start_run(day, 5, "bank")
        for i in range(3):
            j = db.create_job(run, f"r{i}", day, "bank")
            db.update_job(j, status="ready")
        self.assertEqual(db.passed_today(day), 3)
        # run_day computes target = count - passed_today unless --force; here 2 more are needed
        self.assertEqual(max(0, 5 - db.passed_today(day)), 2)

    def test_second_instance_is_refused_by_the_lock(self):
        from factory import ops
        with mock.patch.object(ops, "acquire_lock", return_value=False):
            pm = pipeline.ProductionManager(config.Config())
            self.assertEqual(pm.run_day(1)["status"], "locked")


class TestScheduler(Base):
    def at(self, hh, mm):
        return time.struct_time((2026, 10, 30, hh, mm, 0, 4, 303, -1))

    def test_due_only_after_run_time_and_only_once_per_day(self):
        cfg = config.Config(RUN_TIME="09:00")
        self.assertFalse(scheduler.due(cfg, self.at(8, 59)))
        self.assertTrue(scheduler.due(cfg, self.at(9, 0)))
        run = db.start_run("2026-10-30", 5, "bank")
        db.finish_run(run, "done")
        self.assertFalse(scheduler.due(cfg, self.at(10, 0)))  # already ran today

    def test_auto_generate_off_means_never_due(self):
        self.assertFalse(scheduler.due(config.Config(AUTO_GENERATE=False), self.at(12, 0)))

    def test_interrupted_job_makes_the_scheduler_resume(self):
        cfg = config.Config(RUN_TIME="23:59")
        run = db.start_run("2026-10-30", 5, "bank")
        db.create_job(run, "x", "2026-10-30", "bank")  # still 'running'
        self.assertTrue(scheduler.due(cfg, self.at(8, 0)))


if __name__ == "__main__":
    unittest.main()
