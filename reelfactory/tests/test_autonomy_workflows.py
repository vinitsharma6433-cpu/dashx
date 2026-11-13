"""The new autonomy workflow files stay DISABLED until the owner sets the repository variable DASHX_AUTONOMY_ENABLED to 'true'."""
import re
import subprocess
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
WF = REPO / ".github" / "workflows"
NEW = ("dashx-autonomy.yml", "dashx-autonomy-improve.yml")
GATE = "if: ${{ vars.DASHX_AUTONOMY_ENABLED == 'true' }}"


def text(name):
    return (WF / name).read_text(encoding="utf-8").replace("\r\n", "\n")


class Disabled(unittest.TestCase):
    def test_every_job_has_the_off_by_default_gate(self):
        for name in NEW:
            t = text(name)
            jobs = re.search(r"(?m)^jobs:\n((?:  .*\n|\n)+)", t).group(1)
            job_names = re.findall(r"(?m)^  (\w+):\n", jobs)
            self.assertTrue(job_names, name)
            for j in job_names:
                block = jobs.split(f"  {j}:\n", 1)[1]
                head = block.split("    runs-on:", 1)[0]
                self.assertIn(GATE, head, f"{name} job {j} has no enable gate")

    def test_the_gate_is_a_variable_only_the_owner_can_set(self):
        for name in NEW:
            self.assertIn("DASHX_AUTONOMY_ENABLED", text(name))
            self.assertNotIn("DASHX_AUTONOMY_ENABLED=", text(name))              # nothing in the file turns it on
        # no autonomy code sets a repository variable
        for f in (REPO / "autonomy").glob("*.py"):
            s = f.read_text(encoding="utf-8")
            self.assertNotIn("/actions/variables", s, f.name)
            self.assertNotIn("gh variable", s, f.name)

    def test_only_manual_and_schedule_triggers(self):
        for name in NEW:
            on = re.search(r"(?m)^on:\n((?:  .*\n)+)", text(name)).group(1)
            triggers = set(re.findall(r"(?m)^  (\w+):", on))
            self.assertTrue(triggers <= {"workflow_dispatch", "schedule"}, (name, triggers))     # never push, pull_request or issues triggers

    def test_stop_switches_are_still_honoured_inside_the_job(self):
        self.assertIn("STOP_AUTONOMY", text("dashx-autonomy.yml"))
        t = text("dashx-autonomy-improve.yml")
        self.assertIn("STOP_AUTONOMY", t)
        self.assertIn("STOP_QUEUE", t)

    def test_no_existing_workflow_was_changed_by_the_autonomy_branch(self):
        base = subprocess.run(["git", "merge-base", "HEAD", "origin/main"], cwd=REPO, capture_output=True, text=True, encoding="utf-8").stdout.strip()
        if not base:
            self.skipTest("no git history here")
        out = subprocess.run(["git", "diff", "--name-status", base, "HEAD", "--", ".github", "poster"], cwd=REPO, capture_output=True, text=True, encoding="utf-8").stdout.split("\n")
        changed = sorted(x for x in out if x.strip())
        # before the merge: exactly the two new files; after the merge into main the diff is empty. Either way no poster file and no old workflow is in it.
        self.assertTrue(set(changed) <= {"A\t.github/workflows/dashx-autonomy-improve.yml", "A\t.github/workflows/dashx-autonomy.yml"}, changed)


if __name__ == "__main__":
    unittest.main()
