"""Tests that use real media (tiny synthetic videos made with the project's ffmpeg) and the repair loop.
They only create and remove their own temporary files (reels/_qctest*, output/reels/_qctest*.mp4)."""

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
import wave
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from factory import config, db, qc  # noqa: E402
from factory import pipeline  # noqa: E402

ROOT = qc.ROOT
OK_MEASURE = lambda texts, widths: [{"ok": True, "lines": [{"text": t, "words": 3}]} for t in texts]  # noqa: E731


def make_reel(name: str, vf_src: str, with_audio: bool):
    """A synthetic 21 s reel: script.json + voice wavs + an mp4 built from an ffmpeg lavfi source."""
    scenes = [{"id": i + 1, "template": t, "params": {}, "duration": d, "voice": "अ ब स", "subtitle": "अ ब स"}
              for i, (t, d) in enumerate([("face-off", 4.0), ("run-up", 4.5), ("shot", 4.5), ("catch", 4.0), ("end-card", 4.0)])]
    (ROOT / "reels" / name / "audio").mkdir(parents=True, exist_ok=True)
    (ROOT / "reels" / name / "script.json").write_text(json.dumps({"title": "टेस्ट", "scenes": scenes, "story": {"plot": "p", "closing": "c"}}, ensure_ascii=False), encoding="utf-8")
    for s in scenes:
        with wave.open(str(ROOT / "reels" / name / "audio" / f"scene-{s['id']}.wav"), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(24000)
            w.writeframes(b"\0\0" * 24000 * 2)
    out = ROOT / "output" / "reels" / f"{name}.mp4"
    cmd = [qc.FFMPEG, "-v", "error", "-y", "-f", "lavfi", "-i", f"{vf_src}:s=1080x1920:d=21:r=30"]
    if with_audio:
        cmd += ["-f", "lavfi", "-i", "sine=frequency=300:d=21", "-c:a", "aac"]
    subprocess.run(cmd + ["-pix_fmt", "yuv420p", "-c:v", "libx264", str(out)], check=True)


class TestQCOnSyntheticVideo(unittest.TestCase):
    names = ["_qctest_black", "_qctest_mute"]

    def tearDown(self):
        for n in self.names:
            shutil.rmtree(ROOT / "reels" / n, ignore_errors=True)
            (ROOT / "output" / "reels" / f"{n}.mp4").unlink(missing_ok=True)

    def test_black_video_fails_and_blames_render(self):
        make_reel("_qctest_black", "color=c=black", True)
        r = qc.inspect("_qctest_black", measure=OK_MEASURE)
        failed = {c["id"]: c for c in r["failed"]}
        self.assertIn("first_frame", failed)
        self.assertEqual(failed["first_frame"]["stage"], "render")
        self.assertTrue(r["hard_fail"])
        self.assertLessEqual(r["score"], 59)  # a failed video can never look like a pass
        self.assertFalse(r["passed"])

    def test_missing_audio_fails_and_blames_voice(self):
        make_reel("_qctest_mute", "color=c=gray", False)
        r = qc.inspect("_qctest_mute", measure=OK_MEASURE)
        failed = {c["id"]: c for c in r["failed"]}
        self.assertIn("audio_present", failed)
        self.assertEqual(failed["audio_present"]["stage"], "voice")
        self.assertFalse(r["passed"])

    def test_missing_video_is_a_failure_not_a_pass(self):
        (ROOT / "reels" / "_qctest_black").mkdir(parents=True, exist_ok=True)
        (ROOT / "reels" / "_qctest_black" / "script.json").write_text(json.dumps({"scenes": []}))
        r = qc.inspect("_qctest_black", measure=OK_MEASURE)
        self.assertFalse(r["passed"])
        self.assertEqual(r["score"], 0)


class TestRepairLoop(unittest.TestCase):
    """The orchestration logic with stubbed stages: repair, give-up after 3 attempts, never a silent PASS."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.patches = [mock.patch.object(db, "DB_FILE", Path(self.tmp.name) / "t.db"), mock.patch.object(db, "DATA", Path(self.tmp.name)),
                        mock.patch.object(pipeline.evidence, "EVIDENCE", Path(self.tmp.name) / "evidence")]
        for p in self.patches:
            p.start()
        self.pm = pipeline.ProductionManager(config.Config(MAX_REPAIRS=3))
        run = db.start_run("2026-01-01", 1, "bank")
        self.job_id = db.create_job(run, "stub", "2026-01-01", "bank")
        db.update_job(self.job_id, cast_json=json.dumps(["sachin"]))
        self.job = pipeline.Job(self.job_id, "stub", "2026-01-01", {"title_en": "t", "title_hi": "ट", "plot_en": "p", "closing": "c", "scenes": []},
                                {"title": "ट", "scenes": []}, {"score": 90, "categories": ["Gali Cricket"]})
        self.pm.seo.run = lambda *a, **k: {"seo_score": 100, "title": "t", "description": "d", "hashtags": [], "tags": [], "keyword_suggestions": [], "seo_notes": []}
        self.pm.editor.finalize = lambda *a, **k: Path("x.mp4")
        self.brief = {"usage": {}, "season_word": ""}

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()

    @staticmethod
    def bad(stage="fit", cid="duration"):
        return {"score": 70.0, "passed": False, "hard_fail": False, "checks": [], "failed": [{"id": cid, "stage": stage, "detail": "x", "weight": 10, "ok": False}]}

    @staticmethod
    def good():
        return {"score": 96.0, "passed": True, "hard_fail": False, "checks": [{"id": "duration", "detail": "21.0s ok"}], "failed": []}

    def test_failure_is_repaired_by_rerunning_only_the_responsible_stage(self):
        starts = []
        self.pm._build = lambda job, start: starts.append(start) or []
        self.pm.qa.inspect = mock.Mock(side_effect=[self.bad("fit"), self.good()])
        verified = {"verified": True, "status": "REPAIR VERIFIED", "reason": "stub"}
        with mock.patch.object(pipeline.evidence.Recorder, "finalize", return_value=verified):
            r = self.pm._finish(self.job, "voice", 0, self.brief, 1)
        self.assertEqual(r["status"], "ready")
        self.assertEqual(r["repairs"], 1)
        self.assertEqual(starts, ["voice", "fit"])  # first build from voice, the repair restarts at 'fit' (not earlier)
        self.assertEqual(len(db.q("SELECT * FROM repairs")), 3)  # started + rebuilt + evidence verdict are logged
        self.assertEqual(len(db.q("SELECT * FROM failures")), 1)

    def test_gives_up_after_three_attempts_and_never_passes(self):
        self.pm._build = lambda job, start: []
        self.pm._new_story = lambda *a, **k: None  # no replacement story available
        self.pm.qa.inspect = mock.Mock(return_value=self.bad("render", "first_frame"))
        r = self.pm._finish(self.job, "voice", 0, self.brief, 1)
        self.assertEqual(r["status"], "failed")
        self.assertEqual(r["repairs"], 3)
        self.assertEqual(db.q("SELECT status FROM jobs WHERE id=?", (self.job_id,))[0]["status"], "failed")
        self.assertGreaterEqual(len(db.q("SELECT * FROM failures")), 3)  # every failure is saved

    def test_low_score_without_failed_check_is_still_not_ready(self):
        self.pm._build = lambda job, start: []
        self.pm.cfg.MAX_REPAIRS = 0
        self.pm.qa.inspect = mock.Mock(return_value={"score": 85.0, "passed": True, "hard_fail": False, "checks": [], "failed": []})
        self.assertEqual(self.pm._finish(self.job, "voice", 0, self.brief, 1)["status"], "failed")  # 85 < 90

    def test_qc_off_is_never_marked_ready(self):
        self.pm._build = lambda job, start: []
        self.pm.cfg.AUTO_QC = False
        self.assertEqual(self.pm._finish(self.job, "voice", 0, self.brief, 1)["status"], "unchecked")

    def test_stage_error_becomes_a_failed_check(self):
        calls = []

        def build(job, start):
            calls.append(start)
            return [{"id": "voice_error", "stage": "voice", "detail": "boom", "weight": 10, "ok": False, "hard": True}] if len(calls) == 1 else []

        self.pm._build = build
        self.pm.qa.inspect = mock.Mock(return_value=self.good())
        verified = {"verified": True, "status": "REPAIR VERIFIED", "reason": "stub"}
        with mock.patch.object(pipeline.evidence.Recorder, "finalize", return_value=verified):
            r = self.pm._finish(self.job, "voice", 0, self.brief, 1)
        self.assertEqual(r["status"], "ready")
        self.assertEqual(r["repairs"], 1)

    def test_repair_without_independent_proof_is_not_success(self):
        """QC says PASS after a repair, but the media proof is missing -> the job must NOT be 'ready'."""
        self.pm._build = lambda job, start: []
        self.pm.qa.inspect = mock.Mock(side_effect=[self.bad("render", "first_frame"), self.good()])
        r = self.pm._finish(self.job, "voice", 0, self.brief, 1)  # no real mp4 exists -> nothing to verify
        self.assertEqual(r["status"], "failed")
        self.assertIn("not independently verified", r["error"])


if __name__ == "__main__":
    unittest.main()
