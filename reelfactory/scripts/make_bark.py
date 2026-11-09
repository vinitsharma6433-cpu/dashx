"""Generate assets/sfx/bark.wav: a short synthetic two-woof dog bark (numpy only, nothing downloaded, no licence issue).
    .venv\Scripts\python.exe scripts\make_bark.py
"""
from pathlib import Path

import numpy as np
import soundfile as sf

RATE = 24000
rng = np.random.default_rng(7)


def woof(length=0.20, f0=420.0):
    t = np.arange(int(RATE * length)) / RATE
    f = f0 * (1.0 - 0.45 * t / length)                  # pitch falls during the bark
    phase = 2 * np.pi * np.cumsum(f) / RATE
    tone = sum(np.sin(h * phase) / h for h in range(1, 9))  # harmonic-rich "voice"
    noise = rng.normal(0, 1, t.size)
    k = np.ones(40) / 40
    noise = np.convolve(noise, k, mode="same") * 3      # low-passed breath noise
    env = np.minimum(1.0, t / 0.012) * np.exp(-t / 0.075)
    out = (tone * 0.6 + noise * 0.5) * env
    return out / np.max(np.abs(out))


gap = np.zeros(int(RATE * 0.07))
bark = np.concatenate([woof(0.20, 430), gap, woof(0.22, 390)]) * 0.8
out = Path(__file__).resolve().parent.parent / "assets" / "sfx" / "bark.wav"
sf.write(str(out), bark.astype(np.float32), RATE)
print(out, f"{len(bark) / RATE:.2f}s")
