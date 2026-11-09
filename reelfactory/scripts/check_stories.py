"""Check saved reels/<name>/script.json files against the DASHX rules (story_rules.py) and the template
checker the render script uses (src/reel/templateInfo.ts, compiled to dist/).

    .venv\\Scripts\\python.exe scripts\\check_stories.py chai-wala-catch my-turn-first ...
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from story_rules import hindi_problems, rule_problems  # noqa: E402

BRAND_EN = "DASHX Cricket Tennis Ball. DASHX by Nav Durga Sports, Meerut."


def template_check(script: dict) -> list[str]:
    js = (
        "const {checkScene}=require('./dist/reel/templateInfo');"
        "const s=JSON.parse(process.argv[1]);"
        "const out=[];s.scenes.forEach((sc,i)=>{const r=checkScene(sc,i);out.push(...r.errors,...r.warnings.map(w=>'warning: '+w));});"
        "console.log(JSON.stringify(out));"
    )
    r = subprocess.run(["node", "-e", js, json.dumps(script)], cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    return json.loads(r.stdout) if r.returncode == 0 and r.stdout.strip() else [f"template checker failed: {r.stderr[:200]}"]


def check(name: str) -> list[str]:
    path = ROOT / "reels" / name / "script.json"
    script = json.loads(path.read_text(encoding="utf-8"))
    problems = [f"title {p}" for p in hindi_problems(script["title"], 1, 10)]
    scenes = script["scenes"]
    for sc in scenes:
        last = sc["template"] == "hero-end"
        spoken = sc["voice"]
        if last:
            if not spoken.endswith(BRAND_EN):
                problems.append(f"scene {sc['id']}: DASHX brand line missing or changed")
            spoken = spoken[: -len(BRAND_EN)].strip()
        if sc["subtitle"] != sc["voice"]:
            problems.append(f"scene {sc['id']}: subtitle differs from voice")
        problems += [f"scene {sc['id']} {p}" for p in hindi_problems(spoken, 2, 8)]
        if "tts_text" in sc:
            problems += [f"scene {sc['id']} tts_text {p}" for p in rule_problems(sc["tts_text"])]
    if scenes[-1]["template"] != "hero-end":
        problems.append("last scene must be hero-end")
    if len({s["template"] for s in scenes[:-1]}) < 3:
        problems.append("fewer than 3 different visuals")
    total = sum(s["duration"] for s in scenes)
    if not 20 <= total <= 29:
        problems.append(f"estimated length {total:.1f}s is outside 20-29s")
    problems += template_check(script)
    return problems


if __name__ == "__main__":
    names = sys.argv[1:]
    failed = 0
    for n in names:
        p = check(n)
        print(f"{'PASS' if not p else 'FAIL'}  {n}")
        for line in p:
            print(f"      - {line}")
        failed += bool(p)
    sys.exit(1 if failed else 0)
