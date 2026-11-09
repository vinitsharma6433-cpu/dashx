"""Thumbnail Agent: a 9:16 cover with the Hindi title on top and the DASHX logo, built from the sharpest, brightest
early frame of the reel (candidates at several times). `variant` picks a different frame when a repair is needed."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from . import ROOT
from . import qc

TIMES = [1.5, 2.2, 3.0, 4.2, 5.0]


def _frame(mp4: Path, t: float, out: Path) -> bool:
    r = subprocess.run([qc.FFMPEG, "-v", "error", "-y", "-ss", f"{t}", "-i", str(mp4), "-frames:v", "1", "-vf", "scale=1080:1920", "-q:v", "2", str(out)], capture_output=True)
    return r.returncode == 0 and out.exists()


def best_frame(mp4: Path, tmp: Path, variant: int = 0) -> Path:
    scored = []
    for t in TIMES:
        f = tmp / f"cand-{t}.jpg"
        if _frame(mp4, t, f):
            g = qc.jpg_gray(f)
            if g is not None:
                scored.append((qc.sharpness(g) * min(1.0, float(g.mean()) / 120.0), t, f))
    if not scored:
        raise RuntimeError("no usable frame for the thumbnail")
    scored.sort(reverse=True)
    return scored[variant % len(scored)][2]


def make(name: str, title_hi: str, mp4: Path, out: Path, variant: int = 0) -> Path:
    tmp = ROOT / "factory" / "data" / "tmp" / name
    tmp.mkdir(parents=True, exist_ok=True)
    frame = best_frame(mp4, tmp, variant)
    logo = next((p for p in (ROOT / "assets" / "dashx-logo.png", ROOT / "assets" / "dashx-logo.jpg", ROOT / "assets" / "dashx-logo.placeholder.png") if p.exists()))
    payload = {"frame": str(frame), "logo": str(logo), "title": title_hi, "out": str(out)}
    r = subprocess.run(["node", str(ROOT / "factory" / "thumb.js")], input=json.dumps(payload), capture_output=True, text=True, encoding="utf-8", timeout=120, cwd=ROOT)
    if r.returncode != 0 or not out.exists():
        raise RuntimeError(f"thumbnail render failed: {r.stderr[-300:]}")
    return out
