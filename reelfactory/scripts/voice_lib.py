"""Per-character voices on top of Kokoro (offline). Reads voices.json; splits a scene line into speaker segments.

A line like "सूर्या बोला, आज छक्का मारकर दिखा!" becomes
    narrator: "सूर्या बोला,"   +   surya: "आज छक्का मारकर दिखा!"
so the audio still says exactly what the subtitle shows. Lines without a speaker verb are read by the narrator.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "voices.json"
RATE = 24000

NAMES = {"सचिन": "sachin", "सूर्या": "surya", "दादाजी": "dadaji", "आंटी": "aunty", "पिंटू": "pintu", "गोलू": "golu", "मीना": "meena", "कोच": "coach", "ब्रूनो": "bruno", "पप्पू": "pappu", "छोटू": "chhotu", "मिंटू": "mintu"}
SPEECH_VERBS = {"बोला", "बोली", "बोले", "बोलीं", "कहा", "चिल्लाया", "चिल्लाई", "चिल्लाए", "पूछा", "फुसफुसाया", "पुकारा", "हँसा"}
BARK_WORDS = ("भौंका", "भौंकता", "भौंकने", "भौंकती")


def load_config(path: Path = CONFIG) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def speaker_in(text: str) -> str | None:
    for tok in text.replace(",", " ").split():
        tok = tok.strip("!?।.")
        if tok in NAMES:
            return NAMES[tok]
    return None


def split_line(text: str) -> list[tuple[str, str]]:
    """[(speaker, text)] with speaker 'narrator' or a character id. At most two parts."""
    text = " ".join(text.split())
    if "," in text:
        tag, rest = text.split(",", 1)
        words = tag.split()
        if words and words[-1] in SPEECH_VERBS and rest.strip():
            who = speaker_in(tag)
            if who:
                return [("narrator", tag.strip() + ","), (who, rest.strip())]
    return [("narrator", text)]


def cast_of_script(script: dict) -> set[str]:
    out: set[str] = set()
    for sc in script["scenes"]:
        for v in sc.get("params", {}).values():
            out |= {x for x in (v if isinstance(v, list) else [v]) if x in NAMES.values()}
    return out


def _trim(x: np.ndarray, keep_head: float = 0.015, tail: float = 0.12) -> np.ndarray:
    idx = np.flatnonzero(np.abs(x) > 0.02)
    if idx.size == 0:
        return x
    a = max(0, int(idx[0] - keep_head * RATE))
    b = min(x.size, int(idx[-1] + tail * RATE))
    return x[a:b]


def _pitch(x: np.ndarray, semitones: float) -> np.ndarray:
    """Resample so pitch and tempo both move by 2**(st/12); the caller compensates the tempo through Kokoro's speed."""
    f = 2 ** (semitones / 12)
    if abs(f - 1) < 1e-3:
        return x
    pos = np.arange(0, x.size - 1, f)
    return np.interp(pos, np.arange(x.size), x).astype(np.float32)


def say(kokoro, text: str, spec: dict, global_speed: float = 1.0) -> np.ndarray:
    """One utterance in one character's voice. Net tempo = spec.speed * global_speed, net pitch shift = spec.pitch semitones."""
    f = 2 ** (spec.get("pitch", 0.0) / 12)
    tempo = spec.get("speed", 1.0) * global_speed
    synth_speed = min(2.0, max(0.5, tempo / f))
    samples, rate = kokoro.create(text, voice=spec["voice"], speed=synth_speed, lang="hi")
    assert rate == RATE
    x = _pitch(np.asarray(samples, dtype=np.float32), spec.get("pitch", 0.0))
    x = _trim(x)
    g = 10 ** (spec.get("gain_db", 0.0) / 20)
    if g > 1:
        x = np.tanh(x * g * 0.9) / np.tanh(0.9)  # soft limiter when boosting
    elif g < 1:
        x = x * g
    return np.clip(x, -0.98, 0.98).astype(np.float32)


def bark(cfg: dict) -> np.ndarray:
    spec = cfg["characters"]["bruno"]
    x, _rate = sf.read(str(ROOT / spec["bark"]), dtype="float32")
    return (x * 10 ** (spec.get("gain_db", 0.0) / 20)).astype(np.float32)


def render_line(kokoro, text: str, cfg: dict, global_speed: float = 1.0, narrator_override: str | None = None) -> tuple[np.ndarray, list[dict]]:
    """Audio for one scene line + a list of the segments that make it (for QC and reports)."""
    narr = dict(cfg["narrator"])
    if narrator_override:
        narr["voice"] = narrator_override
    gap = np.zeros(int(cfg.get("gap_s", 0.1) * RATE), dtype=np.float32)
    parts, segs = [], []
    pieces = split_line(text) if cfg.get("speak_tag", True) else [("narrator", text)]
    for who, t in pieces:
        if who == "bruno":
            audio, label = bark(cfg), "bark"
        else:
            spec = narr if who == "narrator" else cfg["characters"].get(who)
            if spec is None or "voice" not in spec:
                spec, who = narr, "narrator"  # a character without a voice is read by the narrator (QC flags the missing entry)
            audio, label = say(kokoro, t, spec, global_speed), spec["voice"]
        if parts:
            parts.append(gap)
        parts.append(audio)
        segs.append({"speaker": who, "text": t, "voice": label, "seconds": round(audio.size / RATE, 2)})
    if any(w in text for w in BARK_WORDS) and "bruno" in cfg["characters"]:
        b = bark(cfg)
        parts += [gap, b]
        segs.append({"speaker": "bruno", "text": "(bark)", "voice": "bark", "seconds": round(b.size / RATE, 2)})
    return np.concatenate(parts), segs


def render_dialogue(kokoro, entries: list[dict], cfg: dict, global_speed: float = 1.0) -> tuple[np.ndarray, list[dict]]:
    """Audio for one dialogue scene: each entry is said by its own speaker's voice (Bruno barks). Returns the audio and, per entry,
    its start/end in seconds from the start of the audio (the mixer adds the 0.25 s lead)."""
    gap = np.zeros(int(cfg.get("gap_s", 0.1) * RATE), dtype=np.float32)
    parts, segs, t = [], [], 0.0
    for e in entries:
        who = e["speaker"]
        spec = cfg["narrator"] if who == "narrator" else cfg["characters"].get(who)
        if who == "bruno":
            audio, label = bark(cfg), "bark"
        else:
            if spec is None or "voice" not in spec:
                raise KeyError(f"no voice for speaker {who!r} in voices.json")
            audio, label = say(kokoro, e["line"], spec, global_speed), spec["voice"]
        if parts:
            parts.append(gap)
            t += gap.size / RATE
        start = t
        parts.append(audio)
        t += audio.size / RATE
        segs.append({"speaker": who, "text": e["line"], "voice": label, "seconds": round(audio.size / RATE, 2), "start": round(start, 2), "end": round(t, 2)})
    return np.concatenate(parts), segs


def table(cfg: dict) -> str:
    rows = [("narrator", cfg["narrator"])] + list(cfg["characters"].items())
    out = [f"{'character':<10} {'voice id':<10} {'speed':>5} {'pitch (st)':>10} {'gain dB':>8}", "-" * 48]
    for name, s in rows:
        if "voice" in s:
            out.append(f"{name:<10} {s['voice']:<10} {s.get('speed', 1.0):>5} {s.get('pitch', 0):>+10} {s.get('gain_db', 0):>+8}")
        else:
            out.append(f"{name:<10} {'(bark wav)':<10} {'-':>5} {'-':>10} {s.get('gain_db', 0):>+8}")
    return "\n".join(out)
