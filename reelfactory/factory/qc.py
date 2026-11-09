"""Quality Inspector: multi-stage quality control with a 0-100 score.

Each check returns (ok, detail) and knows which production STAGE is responsible, so the repair agent can rerun
only that stage. A check that cannot run counts as FAILED (never silently passed). Hard checks (marked H) cap the
score at 59 and block publishing. Target for publishing: MIN_QC_SCORE (default 90).

Stages: story, voice, fit, render, thumbnail.
"""

from __future__ import annotations

import json
import re
import subprocess
import wave
from dataclasses import dataclass, asdict
from pathlib import Path

import numpy as np

from . import ROOT, find_tool, spell
from .story import orthography_problems

FFMPEG = find_tool("ffmpeg")
FFPROBE = find_tool("ffprobe")
LEAD = 0.25
W, H = 1080, 1920
SAFE_TOP, SAFE_BOTTOM_UI, SAFE_SIDE = 150, 380, 40  # px kept clear of Reels/Shorts interface


@dataclass
class Check:
    id: str
    ok: bool
    weight: int
    detail: str
    stage: str
    hard: bool = False


# ---- ffmpeg helpers ------------------------------------------------------------------------------------
def _run(args: list[str], timeout: int = 180) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, timeout=timeout)


def probe(mp4: Path) -> dict:
    r = _run([FFPROBE, "-v", "error", "-show_entries", "format=duration:stream=codec_type,width,height,r_frame_rate", "-of", "json", str(mp4)])
    return json.loads(r.stdout or b"{}")


def stderr_of(mp4: Path, vf: str | None = None, af: str | None = None) -> str:
    args = [FFMPEG, "-hide_banner", "-nostats", "-i", str(mp4)]
    if vf:
        args += ["-vf", vf, "-an"]
    if af:
        args += ["-af", af, "-vn"]
    return _run(args + ["-f", "null", "-"], 300).stderr.decode("utf-8", "replace")


def gray_frame(mp4: Path, t: float, size=(72, 128)) -> np.ndarray | None:
    r = _run([FFMPEG, "-v", "error", "-ss", f"{t}", "-i", str(mp4), "-frames:v", "1", "-vf", f"scale={size[0]}:{size[1]}", "-pix_fmt", "gray", "-f", "rawvideo", "-"])
    return np.frombuffer(r.stdout, np.uint8).reshape(size[1], size[0]) if len(r.stdout) == size[0] * size[1] else None


def rgb_frame(mp4: Path, t: float, size=(270, 480)) -> np.ndarray | None:
    r = _run([FFMPEG, "-v", "error", "-ss", f"{t}", "-i", str(mp4), "-frames:v", "1", "-vf", f"scale={size[0]}:{size[1]}", "-pix_fmt", "rgb24", "-f", "rawvideo", "-"])
    return np.frombuffer(r.stdout, np.uint8).reshape(size[1], size[0], 3) if len(r.stdout) == size[0] * size[1] * 3 else None


def motion_series(mp4: Path, fps: int = 4) -> np.ndarray:
    r = _run([FFMPEG, "-v", "error", "-i", str(mp4), "-vf", f"fps={fps},scale=90:160", "-pix_fmt", "gray", "-f", "rawvideo", "-"], 300)
    a = np.frombuffer(r.stdout, np.uint8)
    n = a.size // (90 * 160)
    return a[: n * 90 * 160].reshape(n, 160, 90).astype(np.float32)


def sharpness(img: np.ndarray) -> float:
    f = img.astype(np.float32)
    lap = 4 * f[1:-1, 1:-1] - f[:-2, 1:-1] - f[2:, 1:-1] - f[1:-1, :-2] - f[1:-1, 2:]
    return float(lap.var())


def jpg_gray(path: Path, size=(270, 480)) -> np.ndarray | None:
    r = _run([FFMPEG, "-v", "error", "-i", str(path), "-vf", f"scale={size[0]}:{size[1]}", "-pix_fmt", "gray", "-f", "rawvideo", "-"])
    return np.frombuffer(r.stdout, np.uint8).reshape(size[1], size[0]) if len(r.stdout) == size[0] * size[1] else None


# ---- the checks -------------------------------------------------------------------------------------------
def inspect(name: str, thumbnail: Path | None = None, measure=None) -> dict:
    """Run every check for reel `name`. `measure` is the subtitle measuring function (injected for tests)."""
    script = json.loads((ROOT / "reels" / name / "script.json").read_text(encoding="utf-8"))
    mp4 = ROOT / "output" / "reels" / f"{name}.mp4"
    scenes = script["scenes"]
    checks: list[Check] = []

    def add(cid, weight, stage, fn, hard=False):
        try:
            ok, detail = fn()
        except Exception as e:  # a check that cannot run is a failure, never a silent pass
            ok, detail = False, f"check could not run: {type(e).__name__}: {e}"
        checks.append(Check(cid, bool(ok), weight, detail, stage, hard))

    if not mp4.exists():
        c = Check("video_exists", False, 100, "mp4 not found", "render", True)
        return {"score": 0, "passed": False, "hard_fail": True, "checks": [asdict(c)], "failed": [asdict(c)]}
    try:
        info = probe(mp4)
    except Exception:  # unreadable output from ffprobe
        info = {}
    if not any(st.get("codec_type") == "video" for st in info.get("streams", [])) or not info.get("format", {}).get("duration"):
        return {"score": 0, "passed": False, "hard_fail": True, "checks": [], "failed": [asdict(Check("file_readable", False, 100, "ffprobe cannot read a video stream (corrupted or truncated file)", "render", True))]}
    streams = info.get("streams", [])
    vid = next((s for s in streams if s.get("codec_type") == "video"), {})
    dur = float(info.get("format", {}).get("duration", 0))
    timeline = sum(s["duration"] for s in scenes)
    starts, t = [], 0.0
    for s in scenes:
        starts.append(t)
        t += s["duration"]

    add("duration", 10, "fit", lambda: (20.0 <= dur <= 25.2, f"{dur:.2f}s (must be 20-25.2s)"), True)
    add("resolution", 5, "render", lambda: ((vid.get("width"), vid.get("height")) == (W, H), f"{vid.get('width')}x{vid.get('height')}"), True)
    add("frame_rate", 3, "render", lambda: (vid.get("r_frame_rate") == "30/1", f"{vid.get('r_frame_rate')} (want 30/1)"))

    vol = stderr_of(mp4, af="volumedetect")
    mean = re.search(r"mean_volume:\s*(-?[\d.]+)", vol)
    peak = re.search(r"max_volume:\s*(-?[\d.]+)", vol)
    has_audio = any(s.get("codec_type") == "audio" for s in streams)
    add("audio_present", 8, "voice", lambda: (has_audio and mean is not None and float(mean.group(1)) > -50, f"audio={has_audio}, mean {mean.group(1) if mean else '?'} dB"), True)
    add("no_clipping", 5, "voice", lambda: (peak is not None and float(peak.group(1)) < -0.3, f"peak {peak.group(1) if peak else '?'} dB (must stay below -0.3)"))

    def first_frames():
        vals = [(tt, gray_frame(mp4, tt)) for tt in (0.0, 0.5)]
        bad = [f"{tt}s" for tt, g in vals if g is None or g.mean() < 40]
        return not bad, "frame 0 and 0.5s brightness " + ", ".join("?" if g is None else str(round(float(g.mean()))) for _, g in vals) + (f" (too dark at {bad})" if bad else "")
    add("first_frame", 8, "render", first_frames, True)

    def black_frozen():
        err = stderr_of(mp4, vf="blackdetect=d=0.25:pix_th=0.10,freezedetect=n=-55dB:d=1.5")
        blacks = re.findall(r"black_duration:([\d.]+)", err)
        frozen = [(float(a), float(b)) for a, b in zip(re.findall(r"freeze_start: ([\d.]+)", err), re.findall(r"freeze_duration: ([\d.]+)", err))]
        end_start = starts[-1] if scenes[-1]["template"] == "end-card" else 1e9
        bad_freeze = [f for f in frozen if f[0] < end_start + 1.0]  # the end card may hold still at its end
        return not blacks and not bad_freeze, f"black segments={blacks}, frozen segments={[f for f in frozen]} (end card hold allowed)"
    add("black_or_frozen", 7, "render", black_frozen)

    wavs = {s["id"]: ROOT / "reels" / name / "audio" / f"scene-{s['id']}.wav" for s in scenes}

    def voice_fits():
        bad = []
        for s in scenes:
            p = wavs[s["id"]]
            if not p.exists():
                bad.append(f"scene {s['id']}: no voice file")
                continue
            with wave.open(str(p)) as w:
                length = w.getnframes() / w.getframerate()
            if length + LEAD > s["duration"] + 0.02:
                bad.append(f"scene {s['id']}: voice {length:.2f}s + lead does not fit in {s['duration']}s")
        return not bad, "; ".join(bad) or "every voice line fits inside its scene"
    add("voice_not_clipped", 6, "fit", voice_fits, True)

    add("subtitle_timing", 6, "fit", lambda: (abs(dur - timeline) <= 0.4 and all(s["duration"] > 0 for s in scenes) and len(starts) == len(scenes),
                                              f"video {dur:.2f}s vs timeline {timeline:.2f}s; scenes run one after another, so subtitles cannot overlap"))

    measured = None
    if measure is None:
        from .bridge import measure_subtitles as measure  # noqa: PLC0415
    # one subtitle box per dialogue line (dialogue format) or one per scene (older reels and the end card)
    items = []
    for s in scenes:
        if s.get("dialogue"):
            items += [(s, d["line"], d.get("width", s.get("subtitleWidth", 900))) for d in s["dialogue"]]
        else:
            items.append((s, s["subtitle"], s.get("subtitleWidth", 900)))
    measured = measure([t for _, t, _ in items], [w for _, _, w in items])

    def lone_word():
        bad = sorted({f"scene {s['id']}" for (s, _t, _w), m in zip(items, measured) if not m["ok"]})
        return not bad, "no single word alone on a line" if not bad else f"single word alone on a line in {bad}"
    add("subtitle_no_lone_word", 5, "fit", lone_word)

    def safe_area():
        bad = []
        for (s, _t, w), m in zip(items, measured):
            width = w + 80
            height = len(m["lines"]) * 88 + 44
            top, bottom = 960 + 470 - height / 2, 960 + 470 + height / 2
            left = (W - width) / 2
            if left < SAFE_SIDE or top < SAFE_TOP or bottom > H - SAFE_BOTTOM_UI:
                bad.append(f"scene {s['id']}: box x={left:.0f} y={top:.0f}-{bottom:.0f}")
        return not bad, "subtitle boxes inside the safe area" if not bad else "; ".join(bad)
    add("safe_area", 4, "fit", safe_area)

    def spelling():
        text = " ".join(s["voice"] for s in scenes)
        bad = sorted({p for s in scenes for p in orthography_problems(s["voice"])})
        unk = spell.unknown_words(text)
        ratio = None if unk is None else len(unk) / max(1, len(re.findall(r"[\u0900-\u097F]+", text)))
        ok = not bad and (ratio is None or ratio <= 0.35)
        return ok, ("orthography: " + ("; ".join(bad) if bad else "ok")) + (f"; dictionary: {round(ratio * 100)}% unknown {unk[:6]}" if ratio is not None else "; dictionary not installed")
    add("hindi_spelling", 5, "story", spelling)

    def animation():
        series = motion_series(mp4)
        diffs = np.abs(np.diff(series, axis=0)).mean(axis=(1, 2)) / 255.0
        bounds = [x for x in starts] + [timeline]
        jumps = [round(i / 4, 2) for i, d in enumerate(diffs) if d > 0.25 and all(abs(i / 4 - b) > 0.6 for b in bounds)]
        return not jumps, f"{len(diffs)} frame steps, largest {float(diffs.max()):.3f}; sudden jumps at {jumps}"
    add("animation_sane", 4, "render", animation)

    def end_card():
        last = scenes[-1]
        text = " ".join(s["subtitle"] + s["voice"] for s in scenes)
        probs = []
        if last["template"] != "end-card":
            probs.append("last scene is not an end-card")
        if last["duration"] > 6.001:
            probs.append(f"end card lasts {last['duration']}s (max 6s)")
        if re.search(r"dash\s*x", text, re.I):
            probs.append("DASHX written in a subtitle (the card shows it once, as the logo)")
        return not probs, "; ".join(probs) or "one end card, <=6s, one spoken line"
    add("end_card", 6, "fit", end_card, True)

    def logo():
        fr = rgb_frame(mp4, max(0.0, dur - 1.0))
        r, g, b = (fr[..., i].astype(int) for i in range(3))
        yellow = float(((r > 200) & (g > 180) & (b < 90))[: fr.shape[0] // 2].mean())
        red = float(((r > 170) & (g < 90) & (b < 90))[fr.shape[0] // 4: 3 * fr.shape[0] // 4].mean())
        return yellow >= 0.01 and red >= 0.01, f"logo (yellow) {yellow * 100:.1f}%, ball (red) {red * 100:.1f}% of the end-card frame"
    add("logo_visible", 5, "render", logo)

    def sync():
        err = stderr_of(mp4, af="silencedetect=n=-38dB:d=0.12")
        ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", err)]
        missing = [s["id"] for s, st in zip(scenes, starts) if not any(st + LEAD - 0.2 <= e <= st + LEAD + 0.4 for e in ends)]
        return not missing, "voice starts 0.25s after each scene start" if not missing else f"voice onset not at the scene start in scenes {missing}"
    add("av_sync", 6, "render", sync)

    def dialogue_format():
        if not script.get("dialogue_format"):
            return True, "older narration format (made before the dialogue format)"
        from .bridge import story_rules  # noqa: PLC0415
        problems = []
        for sc in scenes:
            at = f"scene {sc['id']}"
            if sc["template"] == "end-card":
                if sc.get("speaker") != "narrator":
                    problems.append(f"{at}: the end card must be read by the narrator")
                continue
            ds = sc.get("dialogue") or []
            if not sc.get("speaker") or not ds:
                problems.append(f"{at} has no speaker")
                continue
            if not 1 <= len(ds) <= 2:
                problems.append(f"{at}: needs 1 or 2 lines, has {len(ds)}")
            cast = set()
            for v in sc.get("params", {}).values():
                cast |= {x for x in (v if isinstance(v, list) else [v]) if x in story_rules.SPEAKERS}
            for d in ds:
                who = d.get("speaker")
                if not who:
                    problems.append(f"{at} has a line with no speaker")
                    continue
                if who not in cast:
                    problems.append(f"{at}: {who} speaks but is not on screen")
                problems += [f"{at} ({who}) {p}" for p in story_rules.dialogue_problems(d.get("line", ""), who)]
            if len(ds) == 2 and ds[0].get("speaker") == ds[1].get("speaker"):
                problems.append(f"{at}: both lines have the same speaker")
            import re as _re  # noqa: PLC0415
            if _re.search(r"[A-Za-z]", str(sc.get("params", {}).get("boardText", ""))):
                problems.append(f"{at}: the pop-up word must be Hindi")
        return not problems, "every scene has a speaker; lines are first person with no narration tags" if not problems else "; ".join(problems[:4])
    add("dialogue_format", 8, "story", dialogue_format, True)

    def speaking_visible():
        # dialogue lines must be timed inside their scene, in order, without overlapping
        if not script.get("dialogue_format"):
            return True, "older narration format"
        bad = []
        for sc in scenes:
            ds = sc.get("dialogue") or []
            t = 0.0
            for d in ds:
                if "start" not in d or "end" not in d or d["start"] < t - 0.01 or d["end"] > sc["duration"] + 0.01:
                    bad.append(f"scene {sc['id']}")
                    break
                t = d["end"]
        return not bad, "every line is timed inside its scene" if not bad else f"line timing problem in {bad}"
    add("dialogue_timing", 4, "fit", speaking_visible)

    def voice_map():
        cfgf = ROOT / "voices.json"
        if not cfgf.exists():
            return True, "voices.json not present: single narrator voice"
        cfg = json.loads(cfgf.read_text(encoding="utf-8"))
        if not cfg.get("enabled", False):
            return True, "per-character voices are switched off in voices.json"
        names = {"sachin", "surya", "dadaji", "aunty", "pintu", "golu", "meena", "coach", "bruno"}
        cast = set()
        for sc in scenes:
            for v in sc.get("params", {}).values():
                cast |= {x for x in (v if isinstance(v, list) else [v]) if x in names}
        missing = sorted(c for c in cast if not ({"voice", "bark"} & set(cfg.get("characters", {}).get(c, {}))))
        seg = ROOT / "reels" / name / "audio" / "segments.json"
        if not seg.exists():
            return not missing, "legacy reel made before per-character voices (no segments.json); voice map itself is complete" if not missing else f"no voice for {missing}"
        mode = json.loads(seg.read_text(encoding="utf-8")).get("mode")
        if mode != "characters":
            return False, f"voice was made in '{mode}' mode, character voices are enabled"
        return not missing, f"every character on screen has a voice ({', '.join(sorted(cast))})" if not missing else f"no voice for {missing}"
    add("voice_map", 4, "voice", voice_map)

    def voice_start():
        err = stderr_of(mp4, af="silencedetect=n=-38dB:d=0.08")
        ivs, cur = [], None
        for m in re.finditer(r"silence_(start|end): (-?[\d.]+)", err):
            if m.group(1) == "start":
                cur = float(m.group(2))
            elif cur is not None:
                ivs.append((cur, float(m.group(2))))
                cur = None
        late = []
        for sc, st in zip(scenes, starts):
            lead = max((e - st for a, e in ivs if a <= st + 0.03 < e), default=0.0)
            if lead > 0.3:
                late.append(f"scene {sc['id']} {lead:.2f}s")
        return not late, "every scene starts speaking within 0.3s" if not late else "silence at the start of " + ", ".join(late)
    add("voice_start", 4, "voice", voice_start)

    def loud():
        err = stderr_of(mp4, af="ebur128=peak=true")
        m = re.findall(r"I:\s+(-?[\d.]+) LUFS", err)
        v = float(m[-1]) if m else None
        return v is not None and -19 <= v <= -13, f"integrated loudness {v} LUFS (target -16 +-3)"
    add("loudness", 4, "render", loud)

    if thumbnail is not None:
        def thumb():
            if not thumbnail.exists():
                return False, "thumbnail file missing"
            g = jpg_gray(thumbnail)
            dims = probe(thumbnail).get("streams", [{}])[0]
            ok = g is not None and (dims.get("width"), dims.get("height")) == (W, H) and thumbnail.stat().st_size >= 40_000 and 60 <= g.mean() <= 215 and sharpness(g) >= 30
            return ok, f"{dims.get('width')}x{dims.get('height')}, {thumbnail.stat().st_size // 1024} KB, brightness {None if g is None else round(float(g.mean()))}, sharpness {None if g is None else round(sharpness(g))}"
        add("thumbnail_quality", 4, "thumbnail", thumb)

    total = sum(c.weight for c in checks)
    score = round(100 * sum(c.weight for c in checks if c.ok) / total, 1)
    hard_fail = any(c.hard and not c.ok for c in checks)
    if hard_fail:
        score = min(score, 59.0)
    # strict: ANY failed check blocks the reel (found by negative controls: soft-check failures used to pass)
    return {"score": score, "passed": not any(not c.ok for c in checks), "hard_fail": hard_fail,
            "checks": [asdict(c) for c in checks], "failed": [asdict(c) for c in checks if not c.ok]}
