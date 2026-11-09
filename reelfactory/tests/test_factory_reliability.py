"""Reliability: database corruption recovery, evidence backup/restore round trip, cleanup never touches protected files."""

import hashlib
import shutil
import sqlite3
import sys
import tempfile
import time
import unittest
import zipfile
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from factory import backup, db, evidence, ops  # noqa: E402


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


class TestDatabaseRecovery(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = Path(self.tmp.name)
        self.patches = [mock.patch.object(db, "DB_FILE", t / "f.db"), mock.patch.object(db, "DATA", t), mock.patch.object(db, "SNAPSHOTS", t / "snap")]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()

    def corrupt(self):
        data = bytearray(db.DB_FILE.read_bytes())
        for i in range(100, min(len(data), 3000)):
            data[i] = 0xFF
        db.DB_FILE.write_bytes(bytes(data))
        for s in ("-wal", "-shm"):
            Path(str(db.DB_FILE) + s).unlink(missing_ok=True)

    def test_healthy_database_is_left_alone(self):
        db.start_run("2026-01-01", 1, "bank")
        self.assertEqual(db.ensure_healthy()["status"], "ok")

    def test_corrupt_database_is_restored_from_snapshot_and_damage_is_kept(self):
        run = db.start_run("2026-01-01", 1, "bank")
        db.create_job(run, "a", "2026-01-01", "bank")
        db.snapshot()
        # make sure everything is flushed into the main file before we damage it
        c = sqlite3.connect(db.DB_FILE)
        c.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        c.close()
        self.corrupt()
        self.assertFalse(db.integrity()[0])
        res = db.ensure_healthy()
        self.assertEqual(res["status"], "restored")
        self.assertTrue(list(Path(self.tmp.name).glob("f.db.corrupt-*")))  # the damaged file is kept, not deleted
        self.assertEqual(len(db.q("SELECT * FROM jobs")), 1)  # the data is back

    def test_corrupt_database_without_snapshot_starts_fresh_and_keeps_damage(self):
        db.start_run("2026-01-01", 1, "bank")
        c = sqlite3.connect(db.DB_FILE)
        c.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        c.close()
        self.corrupt()
        res = db.ensure_healthy()
        self.assertEqual(res["status"], "fresh")
        self.assertEqual(db.q("SELECT * FROM jobs"), [])
        self.assertTrue(list(Path(self.tmp.name).glob("f.db.corrupt-*")))

    def test_snapshots_rotate(self):
        db.start_run("2026-01-01", 1, "bank")
        for i in range(5):
            with mock.patch.object(time, "strftime", return_value=f"20260101-00000{i}"):
                db.snapshot(keep=3)
        self.assertEqual(len(list(db.SNAPSHOTS.glob("factory-*.db"))), 3)


class TestEvidenceBackup(unittest.TestCase):
    def test_evidence_videos_survive_backup_and_restore_with_identical_hashes(self):
        live = evidence.EVIDENCE
        files = [f for f in live.rglob("*") if f.is_file()] if live.exists() else []
        if not files:
            self.skipTest("no evidence on disk yet")
        with tempfile.TemporaryDirectory() as d, mock.patch.object(backup, "BACKUPS", Path(d)):
            z = backup.create("evtest")
            names = set(zipfile.ZipFile(z).namelist())
            target = backup.restore(z)
            try:
                for f in files:
                    rel = f.relative_to(backup.ROOT).as_posix()
                    self.assertIn(rel, names, rel)
                    self.assertEqual(sha(target / rel), sha(f), rel)  # byte-identical after restore
                self.assertTrue((target / "factory" / "data" / "factory.db").exists())
            finally:
                shutil.rmtree(target)

    def test_restore_never_overwrites_live_files(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(backup, "BACKUPS", Path(d)):
            z = backup.create("t2")
            before = sha(backup.ROOT / "package.json")
            target = backup.restore(z)
            try:
                self.assertNotEqual(target.resolve(), backup.ROOT.resolve())
                self.assertEqual(sha(backup.ROOT / "package.json"), before)
            finally:
                shutil.rmtree(target)


class TestCleanupSafety(unittest.TestCase):
    def test_protected_paths_can_not_be_deleted(self):
        for rel in ("evidence", "output/ready", "output/reels", "reels", "backups", "stories", "src", "factory/data/factory.db"):
            self.assertTrue(ops.is_protected(ops.ROOT / rel), rel)
        self.assertFalse(ops.safe_delete(ops.ROOT / "evidence"))
        self.assertFalse(ops.safe_delete(ops.ROOT.parent))  # outside the project

    def test_cleanup_leaves_evidence_and_ready_files_untouched(self):
        watched = [f for top in ("evidence", "output/ready") for f in (ops.ROOT / top).rglob("*") if f.is_file()]
        before = {f: (f.stat().st_size, f.stat().st_mtime) for f in watched}
        ops.cleanup(older_than_days=0)  # most aggressive setting: everything "old"
        self.assertEqual({f: (f.stat().st_size, f.stat().st_mtime) for f in watched if f.exists()}, before)


if __name__ == "__main__":
    unittest.main()
