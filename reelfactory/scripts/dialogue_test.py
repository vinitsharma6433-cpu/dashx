"""Build, voice, render and QC dialogue reels from stories/dialogue_bank.md into NEW folders (nothing existing is touched).

    python scripts/dialogue_test.py "Fake Cramp Talk" "Sneeze Talk"   -> output/reels/<slug>.mp4 and output/voice_test/<slug>.mp4
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
import daily  # noqa: E402
import fit_reel  # noqa: E402
import make_stories as ms  # noqa: E402
from factory import qc  # noqa: E402

PY = ROOT / ".venv" / "Scripts" / "python.exe"
OUT = ROOT / "output" / "voice_test"


def run(cmd):
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode:
        raise SystemExit(f"{cmd}\n{r.stdout[-1200:]}{r.stderr[-1200:]}")
    return r.stdout


def make(title_en: str) -> str:
    b = next(x for x in daily.parse_dialogue_bank() if x["title_en"] == title_en)
    story, problems = daily.from_dialogue_data({"title_hi": b["title_hi"], "title_en": b["title_en"], "plot_en": b["plot_en"], "scenes": b["rows"], "closing_hi": b["closing"], "hook": b.get("hook", ""), "card": b.get("card", ""), "series": b.get("series", ""), "ep": b.get("ep", "")})
    assert story and not problems, problems
    story["writer"] = "dialogue bank (stories/dialogue_bank.md)"
    story["idea"] = title_en
    name, _ = daily.write_script(story, ms.template_minimums())
    print(run([str(PY), "scripts/make_voice.py", name, "hm_omega", "1.0"]))
    ok, notes = fit_reel.fit(name, 0.35)
    print("fit:", ok, notes)
    assert ok, notes
    run(["node", "dist/reel.js", name])
    OUT.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "output" / "reels" / f"{name}.mp4", OUT / f"{name}.mp4")
    return name


if __name__ == "__main__":
    for t in sys.argv[1:]:
        n = make(t)
        r = qc.inspect(n)
        print(n, "QC", r["score"], "passed" if r["passed"] else "FAILED", [(c["id"], c["detail"][:100]) for c in r["failed"]])
