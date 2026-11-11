"""Phase 1 tests: the Autonomy rule file and guard (autonomy/RULES.json, autonomy/guard.py)."""
import json
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "autonomy"))
import guard as g  # noqa: E402

RULES = json.loads((REPO / "autonomy" / "RULES.json").read_text(encoding="utf-8"))


def ist(h, m=0, day=11):
    return datetime(2026, 11, day, h, m, tzinfo=g.IST)


class Sealed(unittest.TestCase):
    def test_real_rules_match_the_seal(self):
        self.assertEqual(g.load_rules()["version"], 1)

    def test_any_edit_is_detected(self):
        with tempfile.TemporaryDirectory() as d:
            r, s = Path(d, "RULES.json"), Path(d, "RULES.sha256")
            shutil.copy(g.RULES_PATH, r); shutil.copy(g.SEAL_PATH, s)
            self.assertTrue(g.load_rules(r, s))
            r.write_text(r.read_text(encoding="utf-8").replace('"max_self_changes_per_day": 1', '"max_self_changes_per_day": 99'), encoding="utf-8")
            with self.assertRaises(g.RulesTampered):
                g.load_rules(r, s)

    def test_missing_seal_or_rules_stop_the_machine(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(g.RulesTampered):
                g.load_rules(Path(d, "nope.json"), Path(d, "nope.sha256"))

    def test_tampered_rules_refuse_every_change(self):
        # check_change loads the real rules itself; simulate tamper by pointing the loader at a changed copy
        with tempfile.TemporaryDirectory() as d:
            r, s = Path(d, "RULES.json"), Path(d, "RULES.sha256")
            shutil.copy(g.RULES_PATH, r); shutil.copy(g.SEAL_PATH, s)
            r.write_text(r.read_text(encoding="utf-8") + " ", encoding="utf-8")
            old = (g.RULES_PATH, g.SEAL_PATH)
            try:
                g.RULES_PATH, g.SEAL_PATH = r, s
                dec = g.check_change(["reelfactory/stories/situations.json"], now=ist(15), root=Path(d))
            finally:
                g.RULES_PATH, g.SEAL_PATH = old
            self.assertFalse(dec.ok)
            self.assertTrue(dec.needs_human)
            self.assertIn("TAMPERED", dec.reasons[0])

    def test_crlf_does_not_break_the_seal(self):
        with tempfile.TemporaryDirectory() as d:
            r, s = Path(d, "RULES.json"), Path(d, "RULES.sha256")
            r.write_bytes(g.RULES_PATH.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
            shutil.copy(g.SEAL_PATH, s)
            self.assertTrue(g.load_rules(r, s))


class Paths(unittest.TestCase):
    def kind(self, p):
        return g.classify(p, RULES)[0]

    def test_allowed_files(self):
        for p in ("reelfactory/stories/dialogue_bank.md", "reelfactory/stories/situations.json",
                  "reelfactory/stories/characters.json", "reelfactory/factory/seo.py"):
            self.assertEqual(self.kind(p), "allow", p)

    def test_machine_notes(self):
        for p in ("autonomy/log.md", "autonomy/trends.json", "autonomy/learning.json", "status/daily.md", "autonomy/changes.jsonl"):
            self.assertEqual(self.kind(p), "state", p)

    def test_the_machine_can_never_edit_its_own_rules(self):
        for p in ("autonomy/RULES.json", "autonomy/RULES.sha256", "autonomy/guard.py", "AUTONOMY/rules.json",
                  "autonomy\\RULES.json", "./autonomy/RULES.json", "autonomy//RULES.json", "autonomy/RULES.json.",
                  "autonomy/RULES.json ", "autonomy/x/../RULES.json", "autonomy/RULES.json:stream"):
            self.assertEqual(self.kind(p), "deny", p)

    def test_deny_list(self):
        for p in (".github/workflows/dashx-poster.yml", ".github/workflows/x.yml", "poster/poster.py", "poster/queue.json",
                  "poster/loop.sh", "STOP_POSTER", "STOP_QUEUE", "STOP_AUTONOMY", "reelfactory/STOP_REFILL", "STOP_X",
                  ".env", "reelfactory/factory.env", "reelfactory/.env.local", "a/b/my_secret.txt", "poster/ytcomment.json",
                  "reelfactory/factory/youtube.py", "reelfactory/queue_config.json", "x/token.json", "k.pem"):
            self.assertEqual(self.kind(p), "deny", p)

    def test_default_deny_for_unlisted_paths(self):
        for p in ("index.html", "reelfactory/src/reel/reelScene.tsx", "reelfactory/factory/pipeline.py", "README.md", "status/index.html"):
            self.assertEqual(self.kind(p), "deny", p)

    def test_unsafe_paths_denied(self):
        for p in ("../x", "/etc/passwd", "C:/Windows/x", "", "   ", "a/../../b"):
            self.assertEqual(self.kind(p), "deny", p)

    def test_code_files_with_safety_checks_wait_for_owner_extraction(self):
        for p in ("reelfactory/scripts/refill_bank.py", "reelfactory/scripts/story_rules.py"):
            self.assertEqual(self.kind(p), "extract", p)
            d = g.check_change([p], now=ist(15), root=Path(tempfile.mkdtemp()))
            self.assertFalse(d.ok)
            self.assertTrue(d.needs_human)

    def test_no_path_is_both_allowed_and_denied(self):
        for p in g._allow_paths(RULES) + RULES["state_files"]["paths"]:
            self.assertNotEqual(self.kind(p), "deny", p)


class Limits(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_normal_change_allowed(self):
        d = g.check_change(["reelfactory/stories/situations.json"], now=ist(15), root=self.root)
        self.assertTrue(d.ok, d.reasons)

    def test_deny_file_is_refused_and_goes_to_the_owner(self):
        d = g.check_change(["reelfactory/stories/situations.json", ".github/workflows/dashx-poster.yml"], now=ist(15), root=self.root)
        self.assertFalse(d.ok)
        self.assertTrue(d.needs_human)

    def test_more_than_three_files(self):
        d = g.check_change(["reelfactory/stories/dialogue_bank.md", "reelfactory/stories/situations.json",
                            "reelfactory/stories/characters.json", "reelfactory/factory/seo.py"], now=ist(15), root=self.root)
        self.assertFalse(d.ok)
        self.assertFalse(d.needs_human)
        self.assertIn("4 files", d.reasons[0])
        self.assertTrue(g.check_change(["reelfactory/stories/dialogue_bank.md", "reelfactory/stories/situations.json",
                                        "reelfactory/stories/characters.json"], now=ist(15), root=self.root).ok)

    def test_one_self_change_a_day(self):
        g.record_change(["reelfactory/stories/situations.json"], now=ist(9), root=self.root)
        d = g.check_change(["reelfactory/stories/characters.json"], now=ist(15), root=self.root)
        self.assertFalse(d.ok)
        self.assertIn("already 1 self-change", d.reasons[0])
        # next IST day is fine again
        self.assertTrue(g.check_change(["reelfactory/stories/characters.json"], now=ist(15, day=12), root=self.root).ok)

    def test_machine_notes_do_not_count(self):
        g.record_change(["reelfactory/stories/situations.json"], now=ist(9), root=self.root)
        d = g.check_change(["autonomy/trends.json", "autonomy/log.md"], now=ist(15), root=self.root)
        self.assertTrue(d.ok)
        self.assertTrue(d.state_only)

    def test_blocked_windows(self):
        f = ["reelfactory/stories/situations.json"]
        for h, m in ((11, 0), (11, 45), (12, 30), (19, 0), (20, 30)):
            d = g.check_change(f, now=ist(h, m), root=self.root)
            self.assertFalse(d.ok, (h, m))
            self.assertIsNotNone(d.wait_until)
            self.assertGreater(d.wait_until, ist(h, m))
        for h, m in ((10, 59), (12, 31), (18, 59), (20, 31), (2, 0), (23, 59)):
            self.assertTrue(g.check_change(f, now=ist(h, m), root=self.root).ok, (h, m))

    def test_wait_until_is_the_end_of_the_window(self):
        d = g.check_change(["reelfactory/stories/situations.json"], now=ist(11, 30), root=self.root)
        self.assertEqual(d.wait_until, ist(12, 31))

    def test_blocked_window_is_read_in_ist_whatever_the_clock_zone(self):
        utc_now = datetime(2026, 11, 11, 6, 0, tzinfo=g.timezone.utc)     # 11:30 IST
        self.assertFalse(g.check_change(["reelfactory/stories/situations.json"], now=utc_now, root=self.root).ok)

    def test_kill_switches_always_win(self):
        f = ["reelfactory/stories/situations.json"]
        for name in ("STOP_AUTONOMY", "STOP_QUEUE"):
            (self.root / name).write_text("", encoding="utf-8")
            d = g.check_change(f, now=ist(15), root=self.root)
            self.assertFalse(d.ok, name)
            self.assertIn(name, d.reasons[0])
            (self.root / name).unlink()
        (self.root / "reelfactory").mkdir()
        (self.root / "reelfactory" / "STOP_AUTONOMY").write_text("", encoding="utf-8")
        self.assertEqual(g.halted("all", self.root), "STOP_AUTONOMY")

    def test_kill_switch_scopes(self):
        (self.root / "STOP_POSTER").write_text("", encoding="utf-8")
        self.assertEqual(g.halted("poster", self.root), "STOP_POSTER")
        self.assertIsNone(g.halted("self_change", self.root))     # STOP_POSTER does not stop story changes
        self.assertIsNone(g.halted("trends", self.root))
        (self.root / "STOP_REFILL").write_text("", encoding="utf-8")
        self.assertEqual(g.halted("refill", self.root), "STOP_REFILL")

    def test_the_guard_never_writes_the_rules_or_a_kill_switch(self):
        src = (REPO / "autonomy" / "guard.py").read_text(encoding="utf-8")
        # the only writes: the seal (owner command) and the changes ledger (a state file)
        writes = [ln.strip() for ln in src.splitlines() if "write_text(" in ln or "open(p, " in ln or ".unlink(" in ln]
        self.assertEqual(len(writes), 2, writes)
        self.assertTrue(any("seal_path.write_text" in w for w in writes))
        self.assertNotIn("STOP_", "".join(w for w in writes))

    def test_real_repo_has_no_kill_switch_file_created_by_these_files(self):
        for name in ("STOP_AUTONOMY", "STOP_QUEUE", "STOP_POSTER", "STOP_REFILL"):
            self.assertFalse((REPO / name).exists() or (REPO / "reelfactory" / name).exists(), name)


class RuleFileShape(unittest.TestCase):
    def test_required_limits(self):
        L = RULES["limits"]
        self.assertEqual((L["max_self_changes_per_day"], L["max_files_per_change"]), (1, 3))
        self.assertEqual([(w["from"], w["to"]) for w in L["blocked_windows_ist"]], [("11:00", "12:30"), ("19:00", "20:30")])

    def test_never_list_has_the_dangerous_things(self):
        text = " ".join(RULES["never"]).lower()
        for word in ("auto-like", "auto-follow", "auto-dm", "scraping", "logged-in chrome", "token", "outside binary", "editing its own rules"):
            self.assertIn(word, text)


if __name__ == "__main__":
    unittest.main()
