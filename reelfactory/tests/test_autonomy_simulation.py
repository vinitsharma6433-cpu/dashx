"""Phase 8: the hand-over simulation (autonomy/simulate.py) as unit tests. Every scenario runs on a temporary TEST COPY with its own local git origin."""
import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "autonomy"))
import simulate as sim  # noqa: E402


class Simulation(unittest.TestCase):
    pass


def _make(fn):
    def test(self):
        res = fn()
        failed = [what for ok, what in res.checks if not ok]
        self.assertTrue(res.checks, "scenario made no checks")
        self.assertEqual(failed, [], f"{res.code} {res.name}")
    return test


for _fn in sim.SCENARIOS:
    setattr(Simulation, f"test_{_fn.__name__}", _make(_fn))


class Hygiene(unittest.TestCase):
    def test_the_simulation_never_touches_the_real_repo(self):
        before = subprocess.run(["git", "status", "--porcelain"], cwd=REPO, capture_output=True, text=True, encoding="utf-8").stdout
        res = sim.s1_dead_loop()
        after = subprocess.run(["git", "status", "--porcelain"], cwd=REPO, capture_output=True, text=True, encoding="utf-8").stdout
        self.assertTrue(res.ok)
        self.assertEqual(before, after)

    def test_the_test_copy_is_deleted(self):
        import tempfile
        before = set(Path(tempfile.gettempdir()).glob("dashx-sim-*"))
        sim.s3_missing_comment()
        self.assertEqual(set(Path(tempfile.gettempdir()).glob("dashx-sim-*")), before)

    def test_the_simulation_code_is_protected_and_never_calls_a_service(self):
        import guard
        self.assertEqual(guard.classify("autonomy/simulate.py", guard.load_rules())[0], "deny")
        src = (REPO / "autonomy" / "simulate.py").read_text(encoding="utf-8")
        for w in ("urllib.request", "import requests", "generativelanguage", "gh\", \"", "graph.facebook", "googleapis"):
            self.assertNotIn(w, src, w)


if __name__ == "__main__":
    unittest.main()
