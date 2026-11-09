"""Automatic PASS / FAIL check of one finished reel (output/reels/<name>.mp4 + its script.json).

    .venv\\Scripts\\python.exe scripts\\check_reel.py <reel-name>

Checks:
  1. the mp4 exists, has video and audio, the audio is not silent; frame 0 and the frame at 0.5 s are not dark
  2. length: 20 to 25.2 s, and equal to the timeline of script.json (+-0.4 s)
  3. subtitles: no single word alone on a line (re-measured in a real browser with the width used in the render)
  4. end card: the last scene is an end-card, at most 6.0 s, its spoken line fits inside it, and the
     DASHX name appears nowhere in the subtitles or spoken lines (the end card shows it once, as the logo)
  5. spoken lines are Devanagari only (no English letters, no digits)
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from fit_reel import LEAD, END_CARD_MAX, measure_subtitles  # noqa: E402

MIN_BRIGHTNESS = 40  # a frame darker than this (of 255) counts as black
FFPROBE = ROOT / "node_modules" / "@ffprobe-installer" / "win32-x64" / "ffprobe.exe"
FFMPEG = ROOT / "node_modules" / "@ffmpeg-installer" / "win32-x64" / "ffmpeg.exe"
if not FFMPEG.exists():  # Linux / GitHub Actions: ffmpeg and ffprobe from PATH
    import shutil as _sh
    FFMPEG, FFPROBE = Path(_sh.which("ffmpeg") or FFMPEG), Path(_sh.which("ffprobe") or FFPROBE)


def probe(mp4: Path) -> dict:
    r = subprocess.run([str(FFPROBE), "-v", "error", "-show_entries", "format=duration:stream=codec_type", "-of", "json", str(mp4)],
                       capture_output=True, text=True)
    return json.loads(r.stdout)


def mean_volume(mp4: Path) -> float | None:
    r = subprocess.run([str(FFMPEG), "-hide_banner", "-i", str(mp4), "-af", "volumedetect", "-vn", "-f", "null", "-"],
                       capture_output=True, text=True)
    m = re.search(r"mean_volume:\s*(-?[\d.]+) dB", r.stderr)
    return float(m.group(1)) if m else None


def frame_brightness(mp4: Path, t: float) -> float | None:
    """Mean brightness (0-255) of the frame at time t, from a tiny grayscale copy of the frame."""
    r = subprocess.run([str(FFMPEG), "-v", "error", "-ss", f"{t}", "-i", str(mp4), "-frames:v", "1", "-vf", "scale=72:128",
                        "-pix_fmt", "gray", "-f", "rawvideo", "-"], capture_output=True)
    return sum(r.stdout) / len(r.stdout) if r.stdout else None


def make_cover(mp4: Path, out: Path) -> float | None:
    """Save a 1080x1920 JPEG cover from a good frame (about 1.5 s; another one if that frame is dark)."""
    for t in (1.5, 2.0, 1.0, 2.5, 3.0):
        b = frame_brightness(mp4, t)
        if b is not None and b >= 60:
            subprocess.run([str(FFMPEG), "-v", "error", "-y", "-ss", f"{t}", "-i", str(mp4), "-frames:v", "1",
                            "-vf", "scale=1080:1920", "-q:v", "2", str(out)], capture_output=True)
            return t
    return None


def wav_seconds(path: Path) -> float:
    with wave.open(str(path), "rb") as w:
        return w.getnframes() / w.getframerate()


def check(name: str) -> tuple[bool, list[str], float | None]:
    """Returns (passed, reasons, mp4 duration)."""
    reasons: list[str] = []
    mp4 = ROOT / "output" / "reels" / f"{name}.mp4"
    script = json.loads((ROOT / "reels" / name / "script.json").read_text(encoding="utf-8"))
    scenes = script["scenes"]
    if not mp4.exists():
        return False, ["mp4 not found"], None

    info = probe(mp4)
    kinds = {s.get("codec_type") for s in info.get("streams", [])}
    dur = float(info["format"]["duration"])
    if not {"video", "audio"} <= kinds:
        reasons.append(f"streams missing (has {sorted(kinds)})")
    vol = mean_volume(mp4)
    if vol is None or vol < -50:
        reasons.append(f"audio is silent (mean volume {vol})")
    if not 20.0 <= dur <= 25.2:
        reasons.append(f"length {dur:.2f}s is outside 20-25.2s")
    timeline = sum(s["duration"] for s in scenes)
    if abs(dur - timeline) > 0.4:
        reasons.append(f"length {dur:.2f}s does not match the timeline {timeline:.2f}s")

    # the first frames must show a clear scene, never black (no fade from black on frame 0)
    for t in (0.0, 0.5):
        b = frame_brightness(mp4, t)
        if b is None or b < MIN_BRIGHTNESS:
            reasons.append(f"frame at {t}s is too dark (mean brightness {None if b is None else round(b)} of 255)")

    # subtitles: no single word alone on a line, measured with the width the render used
    measured = measure_subtitles([s["subtitle"] for s in scenes], [s.get("subtitleWidth", 900) for s in scenes])
    for s, m in zip(scenes, measured):
        if not m["ok"]:
            lines = " / ".join(f"{l['text']} ({l['words']})" for l in m["lines"])
            reasons.append(f"scene {s['id']}: single word alone on a subtitle line: {lines}")

    # end card
    last = scenes[-1]
    if last["template"] != "end-card":
        reasons.append("last scene is not an end-card")
    else:
        if last["duration"] > END_CARD_MAX + 0.001:
            reasons.append(f"end card lasts {last['duration']}s (max {END_CARD_MAX}s)")
        wav = ROOT / "reels" / name / "audio" / f"scene-{last['id']}.wav"
        if wav.exists() and wav_seconds(wav) + LEAD > last["duration"]:
            reasons.append(f"end-card line ({wav_seconds(wav):.2f}s) does not fit inside the {last['duration']}s card")
    for s in scenes:
        if re.search(r"dash\s*x", s["subtitle"] + " " + s["voice"], re.I):
            reasons.append(f"scene {s['id']}: DASHX is written in the subtitle (the end card should show it once, as the logo)")
        if re.search(r"[A-Za-z0-9०-९]", s["voice"]):
            reasons.append(f"scene {s['id']}: spoken line has English letters or digits")
    return (not reasons), reasons, dur


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: check_reel.py <reel-name>")
        sys.exit(2)
    passed, why, seconds = check(sys.argv[1])
    print(("PASS" if passed else "FAIL"), sys.argv[1], f"({seconds:.2f}s)" if seconds else "")
    for r in why:
        print("  -", r)
    sys.exit(0 if passed else 1)
