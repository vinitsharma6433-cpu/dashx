"""Make the per-character voice test material in output/voice_test/ (does NOT touch any ready reel).

  clip1-echo-wall.mp4      first ~10 s, voices: narrator, Surya, Golu, Dadaji
  clip2-run-out-fight.mp4  first ~10 s, voices: narrator, Pintu, Meena
  clip3-bruno-keeper.mp4   first ~10 s, voices: narrator, Pintu, Surya, Coach, Bruno's bark
  ab-echo-wall.mp4         the same reel twice: A = old single voice, B = new character voices (1 s black between)
  voices-measured.txt      measured pitch of each character's voice
    python scripts/voice_test.py            (about 6 minutes: 4 renders)
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))
import daily  # noqa: E402
import fit_reel  # noqa: E402
import make_stories as ms  # noqa: E402
from factory import qc  # noqa: E402

PY = ROOT / ".venv" / "Scripts" / "python.exe"
OUT = ROOT / "output" / "voice_test"
OUT.mkdir(parents=True, exist_ok=True)
FF = qc.FFMPEG


def build(title_en: str, name: str) -> None:
    """Script for a bank story under a test name `name` (a new folder reels/<name>; nothing existing is touched)."""
    b = next(x for x in daily.parse_bank() if x["title_en"] == title_en)
    story, problems = daily.from_llm_data({"title_hi": b["title_hi"], "title_en": b["title_en"], "plot_en": b["plot_en"], "scenes": b["rows"], "closing_hi": b["closing"]}, 0, {})
    assert story and not problems, problems
    story["writer"] = "voice test"
    story["idea"] = title_en
    made, script = daily.write_script(story, ms.template_minimums())
    target = ROOT / "reels" / name
    assert not target.exists(), f"{target} already exists"
    shutil.move(str(ROOT / "reels" / made), str(target))
    script["id"] = name
    (target / "script.json").write_text(json.dumps(script, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run(cmd):
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode:
        raise SystemExit(f"{cmd}\n{r.stdout[-800:]}{r.stderr[-800:]}")
    return r.stdout


def make(name: str, legacy: bool = False) -> Path:
    run([str(PY), "scripts/make_voice.py", name, "hm_omega", "1.0"] + (["--legacy"] if legacy else []))
    ok, notes = fit_reel.fit(name, 0.35)
    assert ok, notes
    run(["node", "dist/reel.js", name])
    return ROOT / "output" / "reels" / f"{name}.mp4"


def clip(src: Path, dst: Path, seconds: float = 10.0) -> None:
    run([FF, "-v", "error", "-y", "-i", str(src), "-t", str(seconds), "-af", f"afade=t=out:st={seconds - 0.4}:d=0.4", "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", str(dst)])


def main():
    jobs = {"vt-echo-wall": "Echo Wall", "vt-run-out-fight": "Run-out Fight", "vt-bruno-keeper": "Bruno The Keeper"}
    for name, title in jobs.items():
        if not (ROOT / "reels" / name).exists():
            build(title, name)
    # the same story with the old single voice, for the A/B file
    if not (ROOT / "reels" / "vt-echo-wall-old").exists():
        shutil.copytree(ROOT / "reels" / "vt-echo-wall", ROOT / "reels" / "vt-echo-wall-old", ignore=shutil.ignore_patterns("audio"))
        sc = json.loads((ROOT / "reels" / "vt-echo-wall-old" / "script.json").read_text(encoding="utf-8"))
        sc["id"] = "vt-echo-wall-old"
        (ROOT / "reels" / "vt-echo-wall-old" / "script.json").write_text(json.dumps(sc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    new = {n: make(n) for n in jobs}
    old = make("vt-echo-wall-old", legacy=True)
    clip(new["vt-echo-wall"], OUT / "clip1-echo-wall.mp4")
    clip(new["vt-run-out-fight"], OUT / "clip2-run-out-fight.mp4")
    clip(new["vt-bruno-keeper"], OUT / "clip3-bruno-keeper.mp4")
    shutil.copy2(old, OUT / "ab-A-old-single-voice.mp4")
    shutil.copy2(new["vt-echo-wall"], OUT / "ab-B-new-character-voices.mp4")
    # A then 1 s black then B in one file
    run([FF, "-v", "error", "-y", "-i", str(old), "-f", "lavfi", "-t", "1", "-i", "color=c=black:s=1080x1920:r=30", "-f", "lavfi", "-t", "1", "-i", "anullsrc=r=44100:cl=mono",
         "-i", str(new["vt-echo-wall"]), "-filter_complex",
         "[0:v]setsar=1,fps=30[v0];[0:a]aresample=44100[a0];[1:v]setsar=1[v1];[2:a]anull[a1];[3:v]setsar=1,fps=30[v2];[3:a]aresample=44100[a2];[v0][a0][v1][a1][v2][a2]concat=n=3:v=1:a=1[v][a]",
         "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", str(OUT / "ab-echo-wall.mp4")])
    print("done", OUT)


if __name__ == "__main__":
    main()
