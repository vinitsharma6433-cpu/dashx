"""Make one Hindi voice-over wav per scene with kokoro-onnx (offline).

Usage: .venv\\Scripts\\python.exe scripts\\make_voice.py <reel-name> [voice] [speed] [--legacy]
       .venv\\Scripts\\python.exe scripts\\make_voice.py --table
Reads reels/<reel>/script.json, writes reels/<reel>/audio/scene-N.wav, durations.json and segments.json.

With voices.json enabled every character speaks in their own voice (see scripts/voice_lib.py); the narrator and the
end card keep the original voice. --legacy (or "enabled": false) gives the old single-voice behaviour.
"""
import json
import sys
from pathlib import Path

import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parent))
import voice_lib  # noqa: E402

root = Path(__file__).resolve().parent.parent

if "--table" in sys.argv:
    print(voice_lib.table(voice_lib.load_config()))
    sys.exit(0)

from kokoro_onnx import Kokoro  # noqa: E402

args = [a for a in sys.argv[1:] if not a.startswith("--")]
reel = args[0] if args else "last-ball"
voice = args[1] if len(args) > 1 else "hm_omega"
speed = float(args[2]) if len(args) > 2 else 1.0
cfg = voice_lib.load_config() if voice_lib.CONFIG.exists() else {"enabled": False}
legacy = "--legacy" in sys.argv or not cfg.get("enabled", False)

script = json.loads((root / "reels" / reel / "script.json").read_text(encoding="utf-8"))
out_dir = root / "reels" / reel / "audio"
out_dir.mkdir(parents=True, exist_ok=True)

kokoro = Kokoro(str(root / "models" / "kokoro-v1.0.onnx"), str(root / "models" / "voices-v1.0.bin"))

durations, segments = {}, {}
for scene in script["scenes"]:
    # tts_text is a phonetic Devanagari version for lines that contain English words.
    text = scene.get("tts_text") or scene["voice"]
    path = out_dir / f"scene-{scene['id']}.wav"
    if scene.get("dialogue") and not legacy:
        samples, segs = voice_lib.render_dialogue(kokoro, scene["dialogue"], cfg, speed)
        rate = voice_lib.RATE
        segments[scene["id"]] = segs
    elif legacy:
        samples, rate = kokoro.create(text, voice=voice, speed=speed, lang="hi")
        segments[scene["id"]] = [{"speaker": "narrator", "text": text, "voice": voice}]
    else:
        samples, segs = voice_lib.render_line(kokoro, text, cfg, speed, voice)
        rate = voice_lib.RATE
        segments[scene["id"]] = segs
    sf.write(str(path), samples, rate)
    seconds = len(samples) / rate
    durations[scene["id"]] = round(seconds, 2)
    who = "+".join(s["speaker"] for s in segments[scene["id"]])
    print(f"scene {scene['id']}: voice {seconds:.2f}s / slot {scene['duration']}s ({who}) -> {path.name}")

(out_dir / "durations.json").write_text(json.dumps(durations, indent=2), encoding="utf-8")
(out_dir / "segments.json").write_text(json.dumps({"mode": "legacy" if legacy else "characters", "dialogue": bool(script.get("dialogue_format")), "scenes": segments}, ensure_ascii=False, indent=1), encoding="utf-8")
