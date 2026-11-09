"""Fit a reel's script.json to its real voice files, and make the subtitles wrap cleanly.

    .venv\\Scripts\\python.exe scripts\\fit_reel.py <reel-name>

1. durations: each scene lasts as long as its Hindi voice line (+0.25 s lead, +0.35 s safety), but at least
   what its template needs. The end card is at most 5.0 s. The whole reel must be at most 24.9 s.
2. subtitleWidth: for each subtitle the widest wrap width is chosen where no single word is left alone on a
   line (measured in a real browser by scripts/subtitle_lines.js).
Writes the new values back into reels/<name>/script.json. Returns (ok, notes) when imported.
"""

from __future__ import annotations

import json
import math
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEAD = 0.25  # must match LEAD in src/reel.ts
END_CARD_MAX = 5.0
TOTAL_MAX = 24.9
TOTAL_TARGET_MIN = 21.0  # shorter reels get extra animation time (checked: 20 s minimum)


def template_minimums() -> dict[str, float]:
    text = (ROOT / "src" / "reel" / "templateInfo.ts").read_text(encoding="utf-8")
    found = {m.group(1): float(m.group(2)) for m in re.finditer(r"'?([\w-]+)'?:\s*\{\s*min:\s*([\d.]+)", text)}
    return {"face-off": 3.5, "run-up": 4.05, "shot": 4.05, "catch": 3.2, "hero-end": 5.0, "end-card": 4.5, **found}


def measure_subtitles(texts: list[str], widths: list[int | None] | None = None) -> list[dict]:
    items = [{"text": t, **({"width": widths[i]} if widths and widths[i] else {})} for i, t in enumerate(texts)]
    r = subprocess.run(["node", "scripts/subtitle_lines.js"], cwd=ROOT, input=json.dumps({"fontSize": 56, "items": items}),
                       capture_output=True, text=True, encoding="utf-8", timeout=180)
    if r.returncode != 0:
        raise RuntimeError(f"subtitle measurement failed: {r.stderr[:300]}")
    return json.loads(r.stdout)["items"]


def fit(name: str, safety: float = 0.35) -> tuple[bool, list[str]]:
    notes: list[str] = []
    path = ROOT / "reels" / name / "script.json"
    script = json.loads(path.read_text(encoding="utf-8"))
    voice_file = ROOT / "reels" / name / "audio" / "durations.json"
    if not voice_file.exists():
        return False, ["no audio/durations.json: run make_voice.py first"]
    voice = {int(k): float(v) for k, v in json.loads(voice_file.read_text(encoding="utf-8")).items()}
    mins = template_minimums()
    scenes = script["scenes"]

    def durations(safety: float) -> list[float]:
        out = []
        for sc in scenes:
            need = voice[sc["id"]] + LEAD + safety
            floor = math.ceil(mins[sc["template"]] * 10) / 10
            d = max(floor, math.ceil(need * 10) / 10)
            if sc["template"] == "end-card":
                d = min(END_CARD_MAX, max(floor, d))
            out.append(round(d, 1))
        return out

    ok = True
    durs = durations(safety)
    if sum(durs) > TOTAL_MAX:
        durs = durations(0.15)
        notes.append(f"tight timing: 0.15 s safety instead of {safety} s")
    if sum(durs) < TOTAL_TARGET_MIN:
        body = [i for i, sc in enumerate(scenes) if sc["template"] != "end-card"]
        extra = min(1.5, (TOTAL_TARGET_MIN - sum(durs)) / max(1, len(body)))
        extra = math.ceil(extra * 10) / 10
        for i in body:
            durs[i] = round(durs[i] + extra, 1)
        notes.append(f"short reel: +{extra}s animation time on each of the {len(body)} story scenes")
    last = scenes[-1]
    if last["template"] == "end-card" and voice[last["id"]] + LEAD > END_CARD_MAX - 0.1:
        ok = False
        notes.append(f"end-card line is too long: voice {voice[last['id']]:.2f}s + lead must fit in {END_CARD_MAX}s")
    if sum(durs) > TOTAL_MAX:
        ok = False
        notes.append(f"total {sum(durs):.1f}s is more than {TOTAL_MAX}s")
    for sc, d in zip(scenes, durs):
        sc["duration"] = d

    # dialogue scenes: one subtitle per spoken line, shown while that character talks
    seg_file = ROOT / "reels" / name / "audio" / "segments.json"
    segs = json.loads(seg_file.read_text(encoding="utf-8")).get("scenes", {}) if seg_file.exists() else {}
    items: list[tuple[dict, dict | None]] = []  # (scene, dialogue entry or None for a plain subtitle)
    for sc in scenes:
        if sc.get("dialogue"):
            timing = segs.get(str(sc["id"]), [])
            if len(timing) != len(sc["dialogue"]):
                ok = False
                notes.append(f"scene {sc['id']}: segments.json does not match the dialogue (run make_voice.py again)")
                continue
            for e, t in zip(sc["dialogue"], timing):
                e["start"], e["end"] = round(LEAD + t["start"], 2), round(LEAD + t["end"], 2)
                items.append((sc, e))
        else:
            items.append((sc, None))
    fitted = measure_subtitles([e["line"] if e else sc["subtitle"] for sc, e in items])
    widest: dict[int, int] = {}
    for (sc, e), f in zip(items, fitted):
        if f["ok"]:
            if e is not None:
                e["width"], e["lines"] = f["width"], len(f["lines"])
            widest[sc["id"]] = max(widest.get(sc["id"], 0), f["width"])
        else:
            ok = False
            notes.append(f"scene {sc['id']}: subtitle always leaves a single word alone on a line: {(e or sc).get('line', sc['subtitle'])}")
    for sc in scenes:
        w = widest.get(sc["id"])
        if w is None:
            continue
        if w == 900:
            sc.pop("subtitleWidth", None)
        else:
            sc["subtitleWidth"] = w

    path.write_text(json.dumps(script, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    notes.append(f"total {sum(durs):.1f}s; durations {durs}")
    return ok, notes


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: fit_reel.py <reel-name>")
        sys.exit(2)
    good, info = fit(sys.argv[1])
    print(("OK  " if good else "FAIL"), *info, sep="\n  ")
    sys.exit(0 if good else 1)
