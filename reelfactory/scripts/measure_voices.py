"""Measure what each character's voice really sounds like (median pitch in Hz, speaking rate) on the same sentence.
Software cannot judge how pleasant a voice is, but it can prove the voices are different from each other.
    python scripts/measure_voices.py [out.txt]
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import voice_lib  # noqa: E402
from kokoro_onnx import Kokoro  # noqa: E402

ROOT = voice_lib.ROOT
SENTENCE = "आज हम सब मिलकर गली में क्रिकेट खेलेंगे।"


def f0_median(x: np.ndarray, rate: int = 24000) -> float:
    frame, hop = int(0.04 * rate), int(0.01 * rate)
    lo, hi = int(rate / 400), int(rate / 70)
    vals = []
    for i in range(0, x.size - frame, hop):
        w = x[i:i + frame] - x[i:i + frame].mean()
        if np.sqrt((w ** 2).mean()) < 0.02:
            continue
        ac = np.correlate(w, w, "full")[frame - 1:]
        k = lo + int(np.argmax(ac[lo:hi]))
        if ac[k] > 0.45 * ac[0]:
            vals.append(rate / k)
    return float(np.median(vals)) if vals else float("nan")


def main():
    cfg = voice_lib.load_config()
    kokoro = Kokoro(str(ROOT / "models" / "kokoro-v1.0.onnx"), str(ROOT / "models" / "voices-v1.0.bin"))
    rows = [("narrator", cfg["narrator"])] + [(k, v) for k, v in cfg["characters"].items() if "voice" in v]
    lines = [f"{'character':<10} {'voice':<9} {'speed':>5} {'pitch st':>8} {'median F0 Hz':>13} {'seconds':>8} {'syll/s*':>8}", "-" * 68]
    for name, spec in rows:
        x = voice_lib.say(kokoro, SENTENCE, spec)
        secs = x.size / voice_lib.RATE
        lines.append(f"{name:<10} {spec['voice']:<9} {spec.get('speed', 1.0):>5} {spec.get('pitch', 0):>+8} {f0_median(x):>13.0f} {secs:>8.2f} {len(SENTENCE.split()) / secs:>8.2f}")
    lines.append("* words per second on the same sentence")
    lines.append("bruno: bark wav " + f"{len(voice_lib.bark(cfg)) / voice_lib.RATE:.2f}s")
    text = "\n".join(lines)
    print(text)
    if len(sys.argv) > 1:
        Path(sys.argv[1]).write_text(text + "\n", encoding="utf-8")


main()
