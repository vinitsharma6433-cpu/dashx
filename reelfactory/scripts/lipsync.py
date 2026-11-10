"""OPTIONAL lip sync (Rhubarb Lip Sync, MIT, https://github.com/DanielSWolf/rhubarb-lip-sync).

    python scripts/lipsync.py <reel-name>        # writes mouth cues into reels/<name>/script.json

It runs the `rhubarb` program on every scene voice file (reels/<name>/audio/scene-N.wav), turns its mouth shapes (A-H, X) into per-line cues
and stores them as dialogue[k]["mouth"] = [[seconds since the line started, "B"], ...]. src/reel/reelScene.tsx uses the cues to shape the
speaker's mouth. WITHOUT cues (the default) the reel keeps the old fixed open-close beat, so nothing changes unless this script was run.

The program is NOT part of the repo. Point RHUBARB_EXE at rhubarb(.exe), or put it at tools/rhubarb/rhubarb(.exe). If it is missing this script
prints a note and exits 0. Hindi uses the `phonetic` recogniser (Rhubarb's English recogniser does not know Hindi).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEAD = 0.25  # the voice starts this long after each scene start (scripts/fit_reel.py)


def find_rhubarb() -> str | None:
    for cand in (os.environ.get("RHUBARB_EXE"), str(ROOT / "tools" / "rhubarb" / "rhubarb.exe"), str(ROOT / "tools" / "rhubarb" / "rhubarb")):
        if cand and Path(cand).exists():
            return cand
    return shutil.which("rhubarb")


def cues_for(exe: str, wav: Path) -> list[tuple[float, str]]:
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "cues.json"
        r = subprocess.run([exe, "-r", "phonetic", "-f", "json", "-o", str(out), str(wav)], capture_output=True, timeout=300)
        if r.returncode != 0 or not out.exists():
            raise RuntimeError(f"rhubarb failed on {wav.name}: {r.stderr.decode('utf-8', 'replace')[-200:]}")
        return [(float(c["start"]), c["value"]) for c in json.loads(out.read_text(encoding="utf-8"))["mouthCues"]]


def main(name: str) -> int:
    exe = find_rhubarb()
    if not exe:
        print("lipsync: rhubarb not found (set RHUBARB_EXE); the reel keeps the default mouth animation")
        return 0
    f = ROOT / "reels" / name / "script.json"
    script = json.loads(f.read_text(encoding="utf-8"))
    n_lines = n_cues = 0
    for sc in script["scenes"]:
        ds = sc.get("dialogue") or []
        wav = ROOT / "reels" / name / "audio" / f"scene-{sc['id']}.wav"
        if not ds or not wav.exists():
            continue
        cues = [(t + LEAD, v) for t, v in cues_for(exe, wav)]   # seconds since the scene start
        for d in ds:
            start, end = d.get("start"), d.get("end")
            if start is None or end is None:
                continue
            rel = [[round(max(0.0, t - start), 3), v] for t, v in cues if start - 0.05 <= t < end]
            if rel:
                d["mouth"] = rel
                n_lines += 1
                n_cues += len(rel)
    f.write_text(json.dumps(script, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"lipsync: {n_cues} mouth cues for {n_lines} lines in {name}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
