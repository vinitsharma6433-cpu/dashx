"""Make new DASHX reel stories with a LOCAL LLM (Ollama) and save them as reels/<name>/script.json.

    npm run stories -- 5

Uses the script-writing part of purffle-shorts (tools/purffle-shorts, MIT): its idea planner and its
Script Doctor two-pass (grade, rewrite, grade again). Everything else of purffle-shorts (video, voice,
captions, uploads) is removed. Nothing is rendered, voiced or posted here: only script.json files,
stories/used.md and stories/last_run.md are written.
"""

from __future__ import annotations

import json
import math
import random
import re
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools" / "purffle-shorts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from purffle_shorts.config import Settings  # noqa: E402
from purffle_shorts.history import History  # noqa: E402
from purffle_shorts.llm import LLM, LLMConfigError, LLMError  # noqa: E402
from purffle_shorts.planner import plan_ideas  # noqa: E402
from purffle_shorts.script import Scene, Script, review_script  # noqa: E402
from purffle_shorts.utils import slugify  # noqa: E402
from story_rules import hindi_problems, rule_problems, similar  # noqa: E402

REELS = ROOT / "reels"
USED = ROOT / "stories" / "used.md"
KIDS = ["sachin", "surya"]
ALL_CHARS = ["sachin", "surya", "dadaji"]
BODY_TEMPLATES = ["face-off", "run-up", "shot", "catch"]
BRAND_EN = "DASHX Cricket Tennis Ball. DASHX by Nav Durga Sports, Meerut."
BRAND_TTS = "डैश एक्स क्रिकेट टेनिस बॉल. डैश एक्स बाय नव दुर्गा स्पोर्ट्स, मेरठ."
TARGET_TOTAL = (21.0, 29.0)  # seconds, "about 25 s"
RECENT_FOR_WRITER = 10  # last titles handed to the story writer

CAMERA = {
    "face-off": {"move": "zoom-in", "from": 1.0, "to": 1.12},
    "run-up": {"move": "pan-left", "zoom": 1.1},
    "shot": {"move": "tilt-up", "zoom": 1.1},
    "catch": {"move": "zoom-in", "from": 1.0, "to": 1.15},
    "hero-end": {"move": "zoom-out", "from": 1.15, "to": 1.0},
    "end-card": {"move": "zoom-in", "from": 1.0, "to": 1.05},
}


def template_minimums() -> dict[str, float]:
    """Shortest duration each template needs, read from src/reel/templateInfo.ts (single source)."""
    text = (ROOT / "src" / "reel" / "templateInfo.ts").read_text(encoding="utf-8")
    found = {m.group(1): float(m.group(2)) for m in re.finditer(r"'?([\w-]+)'?:\s*\{\s*min:\s*([\d.]+)", text)}
    return {**{"face-off": 3.5, "run-up": 4.05, "shot": 4.05, "catch": 3.2, "hero-end": 5.0}, **found}


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# --------------------------------------------------------------------------------------------------
# 1. Idea planner (purffle-shorts planner.py)
# --------------------------------------------------------------------------------------------------
PLANNER_RULES = (
    "These are made-up cartoon stories, so ideas are invented but must be kind, funny and everyday. "
    "Characters: Sachin and Surya (10-year-old boys) and Dadaji (their grandfather). Setting: a narrow Indian gali "
    "with a tennis ball and a bat. Each idea must be playable with ONLY these visual moves: two characters staring "
    "each other down while a scoreboard shows one short word; a bowler running in; a batter hitting the ball very "
    "high; the ball falling from the sky and someone catching it. No real people, real teams or real players, no "
    "news, no politics, no religion, no danger or injuries, no talk of money, prices, offers or 'the best', no "
    "other brands. The closing brand scene is added by us, so do not plan one. Every idea must be clearly "
    "different from the ones already made."
)


def plan(llm: LLM, history: History, count: int) -> list[dict]:
    settings = Settings(
        niches=["funny gali-cricket cartoon stories with Sachin, Surya and Dadaji"],
        planner_rules=PLANNER_RULES,
        audience="kids and families in India who play gali cricket",
    )
    return plan_ideas(llm, settings, history, count=count, niches=settings.niches)


# --------------------------------------------------------------------------------------------------
# 2. Story writer (our own prompt, purffle's LLM layer)
# --------------------------------------------------------------------------------------------------
STORY_SCHEMA = {
    "type": "object",
    "properties": {
        "title_hi": {"type": "string"},
        "title_en": {"type": "string"},
        "plot_en": {"type": "string"},
        "scenes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "template": {"type": "string", "enum": BODY_TEMPLATES},
                    "who_a": {"type": "string", "enum": ALL_CHARS},
                    "who_b": {"type": "string", "enum": ALL_CHARS},
                    "board": {"type": "string"},
                    "line_hi": {"type": "string"},
                },
                "required": ["template", "who_a", "who_b", "board", "line_hi"],
                "additionalProperties": False,
            },
        },
        "closing_hi": {"type": "string"},
    },
    "required": ["title_hi", "title_en", "plot_en", "scenes", "closing_hi"],
    "additionalProperties": False,
}


def story_prompt(idea: dict, avoid: list[str], problems: list[str]) -> tuple[str, str]:
    system = (
        "You write very short, funny, family-friendly cartoon stories in simple spoken Hindi (Devanagari) for kids "
        "who play gali cricket. You reply with a single JSON object and nothing else."
    )
    avoid_block = ("Do NOT repeat or imitate these earlier stories:\n" + "\n".join(f"- {a}" for a in avoid) + "\n\n") if avoid else ""
    fix = ("Your previous attempt was rejected for these reasons. Fix them:\n" + "\n".join(f"- {p}" for p in problems) + "\n\n") if problems else ""
    user = f"""Write one 25-second cartoon story.

Idea: {idea['subject']}
Twist: {idea.get('notes') or idea.get('angle') or ''}
Characters: sachin and surya (10-year-old boys), dadaji (their grandfather).

{avoid_block}{fix}Tell the story in exactly 4 scenes, then one closing line. For every scene choose the visual:
- "face-off": two characters stare at each other (who_a on the left, who_b on the right). "board" = ONE short English word in capitals shown on a scoreboard (for example TIE, OUT?, DARE, MINE!, READY?), max 7 characters.
- "run-up": who_a runs in to bowl, who_b waits with the bat. who_a and who_b must be sachin or surya.
- "shot": who_a smashes the ball high into the sky, who_b watches open-mouthed. who_a must be sachin or surya.
- "catch": the ball comes falling down and dadaji (who_a) catches it one-handed while the others freeze. who_a must be dadaji.
Use at least 3 different visuals. For visuals other than face-off, board is "".

line_hi = what the narrator says in that scene: 3 to 7 words, simple spoken Hindi in Devanagari, funny, ONE short sentence.
closing_hi = a warm closing line about the joy of gali cricket: 3 to 5 words, Devanagari. Do not mention any brand.
title_hi: a short Hindi title (max 6 words). title_en: the same in English. plot_en: the whole plot in ONE English sentence.

Hard rules for every Hindi line: Devanagari letters only (no English letters, no digits, no emoji); no prices, offers or money; no words like best, number one, premium or guaranteed; no brand names; no real people, teams or players; no news, politics, religion, danger or injuries. The story must follow the idea above and tell a small story from start to end.

Return JSON: {{"title_hi", "title_en", "plot_en", "scenes": [{{"template", "who_a", "who_b", "board", "line_hi"}}, ...4 items], "closing_hi"}}"""
    return system, user


def build_scenes(data: dict, seed: int, mins: dict[str, float]) -> tuple[list[dict], list[str]]:
    """Turn the LLM's answer into our scene format (template + params). Returns (scenes, problems)."""
    problems: list[str] = []
    raw = data.get("scenes") or []
    if len(raw) != 4:
        return [], [f"need exactly 4 scenes, got {len(raw)}"]
    if len({s.get("template") for s in raw}) < 3:
        problems.append("use at least 3 different visuals (templates)")
    scenes: list[dict] = []
    for i, s in enumerate(raw, 1):
        t = s.get("template")
        a, b = s.get("who_a"), s.get("who_b")
        if t not in BODY_TEMPLATES:
            problems.append(f"scene {i}: unknown template {t!r}")
            continue
        line = " ".join(str(s.get("line_hi", "")).split())
        for p in hindi_problems(line, 2, 8):
            problems.append(f"scene {i} line {p}")
        # --- characters per template (the LLM's choice is repaired, never trusted blindly) ---
        if a == b:
            b = next(c for c in ALL_CHARS if c != a)
        if t == "face-off":
            board = str(s.get("board", "")).strip().upper()
            if not re.fullmatch(r"[A-Z?!.' ]{1,7}", board):
                board = "?"
            params = {"left": a, "right": b, "boardText": board}
        elif t == "run-up":
            bowler = a if a in KIDS else KIDS[0]
            batter = b if (b in KIDS and b != bowler) else next(k for k in KIDS if k != bowler)
            params = {"batter": batter, "bowler": bowler}
        elif t == "shot":
            batter = a if a in KIDS else KIDS[0]
            watcher = b if b != batter else next(c for c in ALL_CHARS if c != batter)
            params = {"batter": batter, "watcher": watcher}
        else:  # catch: Dadaji sits on the chair and catches, the two kids watch
            first = b if b in KIDS else KIDS[0]
            params = {"catcher": "dadaji", "watchers": [first, next(k for k in KIDS if k != first)]}
        scenes.append({"template": t, "params": params, "line": line})
    closing = " ".join(str(data.get("closing_hi", "")).split())
    for p in hindi_problems(closing, 2, 6):
        problems.append(f"closing line {p}")
    perms = [
        ["sachin", "dadaji", "surya"], ["surya", "dadaji", "sachin"], ["dadaji", "sachin", "surya"],
        ["dadaji", "surya", "sachin"], ["sachin", "surya", "dadaji"], ["surya", "sachin", "dadaji"],
    ]
    scenes.append({"template": "hero-end", "params": {"cast": perms[seed % len(perms)]}, "line": closing})
    return scenes, problems


# --------------------------------------------------------------------------------------------------
# 3. Script Doctor two-pass (purffle-shorts script.py), applied to the Hindi lines
# --------------------------------------------------------------------------------------------------
def doctor(llm: LLM, idea: dict, title_hi: str, plot_en: str, scenes: list[dict]) -> tuple[list[str], str, int | None, list[str]]:
    """Grade the story, let the Script Doctor rewrite it, grade the rewrite again (kept only if not worse).
    Only the wording is taken back: templates and characters stay exactly as we chose them."""
    # ~2.6 spoken words per second; our stories speak about half of the 25 s (the rest is animation)
    settings = Settings(language="hi", target_seconds=13, style="story", script_review="rewrite",
                        audience="kids and families in India who play gali cricket")
    draft = Script(
        topic=idea["subject"], title=title_hi, hook_text=scenes[0]["line"],
        scenes=[Scene(narration=s["line"], search_query=s["template"], image_prompt=s["template"]) for s in scenes],
        description=plot_en, category="entertainment", style="story", language="hi",
    )
    try:
        out = review_script(llm, draft, settings)
    except Exception as e:  # the Doctor must never stop a story
        log(f"  Script Doctor skipped: {e}")
        return [s["line"] for s in scenes], title_hi, None, []
    lines = [s["line"] for s in scenes]
    title = title_hi
    if len(out.scenes) == len(scenes):
        cand = [" ".join(sc.narration.split()) for sc in out.scenes]
        limit = lambda i: (2, 6) if i == len(cand) - 1 else (2, 8)
        if all(not hindi_problems(c, *limit(i)) for i, c in enumerate(cand)):
            lines = cand
        else:
            log("  Doctor rewrite broke a DASHX rule; kept the draft wording")
        t = " ".join(out.title.split())
        if t and not hindi_problems(t, 1, 10):
            title = t
    else:
        log(f"  Doctor rewrite changed the scene count ({len(out.scenes)}); kept the draft wording")
    return lines, title, out.score, out.review


# --------------------------------------------------------------------------------------------------
# 4. Assemble script.json (our format)
# --------------------------------------------------------------------------------------------------
def estimate_durations(scenes: list[dict], lines: list[str], mins: dict[str, float]) -> list[float]:
    durs = []
    for i, (s, line) in enumerate(zip(scenes, lines)):
        last = s["template"] == "hero-end"
        words = len((line + " " + BRAND_TTS).split()) if last else len(line.split())
        voice = 0.46 * words + 0.3  # measured with kokoro hm_omega (about 2.3 words/s)
        need = voice + 0.25 + 0.45  # lead silence + safety
        floor = math.ceil(mins[s["template"]] * 10) / 10  # template minimum, rounded up to 0.1 s
        durs.append(max(floor, math.ceil(need * 2) / 2))
    total = sum(durs)
    if total < TARGET_TOTAL[0]:  # spread the missing time over the body scenes (more animation time)
        extra = min(1.5, (25.0 - total) / max(1, len(durs) - 1))
        durs = [d + (math.floor(extra * 2) / 2 if i < len(durs) - 1 else 0) for i, d in enumerate(durs)]
    return durs


def make_script(name: str, title_hi: str, plot_en: str, idea: dict, scenes: list[dict], lines: list[str],
                durations: list[float], score: int | None, review: list[str], model: str) -> dict:
    out_scenes = []
    for i, (s, line, dur) in enumerate(zip(scenes, lines, durations), 1):
        last = s["template"] == "hero-end"
        voice = f"{line} {BRAND_EN}" if last else line
        item = {
            "id": i,
            "template": s["template"],
            "params": s["params"],
            "duration": dur,
            "camera": CAMERA[s["template"]],
            "voice": voice,
            "subtitle": voice,
        }
        if last:
            item["tts_text"] = f"{line} {BRAND_TTS}"
        out_scenes.append(item)
    return {
        "id": name,
        "title": title_hi,
        "language": "hi",
        "format": {"width": 1080, "height": 1920, "fps": 30},
        "brand": {
            "spelling": "DASHX",
            "line": "DASHX by Nav Durga Sports, Meerut",
            "notes": "Generated story. No price, no 'best/no.1/premium/guaranteed' claim, no other brands, no sensitive news.",
        },
        "story": {
            "plot": plot_en,
            "idea": idea["subject"],
            "generated": date.today().isoformat(),
            "writer": f"purffle-shorts planner + Script Doctor, local model {model}",
            "doctor_score": score,
            "doctor_notes": review[:5],
            "durations_are_estimates": "Run scripts/make_voice.py, then set each duration to voice length + about 0.7 s.",
        },
        "scenes": out_scenes,
    }


def unique_name(base: str) -> str:
    base = slugify(base, 28) or "story"
    name, n = base, 2
    while (REELS / name).exists():
        name, n = f"{base}-{n}", n + 1
    return name


# --------------------------------------------------------------------------------------------------
def main() -> int:
    count = 5
    if len(sys.argv) > 1:
        try:
            count = max(1, min(20, int(sys.argv[1])))
        except ValueError:
            print("Usage: npm run stories -- <how many>   (default 5)")
            return 2

    import os

    from purffle_shorts.llm import ollama_models, ollama_url

    # Model: STORIES_MODEL if set, else gemma3:4b when installed (better Hindi), else Ollama's first model.
    model = os.environ.get("STORIES_MODEL", "")
    if not model and "gemma3:4b" in (ollama_models(ollama_url()) or []):
        model = "gemma3:4b"
    try:
        llm = LLM(Settings(llm_provider="ollama", llm_model=model))
    except (LLMConfigError, LLMError) as e:
        print(f"No free local LLM available: {e}")
        return 1
    log(f"Using local model: {llm.label}")

    mins = template_minimums()
    history = History(USED)
    log(f"Planning ideas (avoiding {len(history.recent_titles(60))} earlier titles)...")
    try:
        ideas = plan(llm, history, count + 3)
    except Exception as e:
        print(f"The local LLM could not plan ideas: {e}")
        return 1
    if not ideas:
        print("The planner returned no usable ideas.")
        return 1
    log(f"{len(ideas)} idea(s) planned")

    made: list[dict] = []
    batch_titles: list[str] = []
    for idea in ideas:
        if len(made) >= count:
            break
        log(f"Story {len(made) + 1}/{count}: {idea['subject']}")
        recent = history.recent_titles(RECENT_FOR_WRITER) + batch_titles
        recent = recent[-RECENT_FOR_WRITER:] if len(recent) > RECENT_FOR_WRITER else recent
        problems: list[str] = []
        built = None
        for attempt in range(1, 4):
            system, user = story_prompt(idea, recent, problems)
            try:
                data = llm.complete_json(system, user, STORY_SCHEMA, max_tokens=2500)
            except Exception as e:
                problems = [f"the reply was not usable JSON ({e})"]
                continue
            title_hi = " ".join(str(data.get("title_hi", "")).split())
            title_en = " ".join(str(data.get("title_en", "")).split())
            plot_en = " ".join(str(data.get("plot_en", "")).split())
            scenes, problems = build_scenes(data, seed=len(made) + int(time.time()) % 7, mins=mins)
            problems += [f"title {p}" for p in hindi_problems(title_hi, 1, 10)]
            problems += [f"title_en/plot_en {p}" for p in rule_problems(title_en + " " + plot_en)]
            if not scenes:
                continue
            # not a repeat of something already made (last titles, plots and this batch)?
            for old in history.recent_titles(60) + batch_titles:
                if similar(title_en, old) > 0.8 or similar(title_hi, old) > 0.8:
                    problems.append(f"too similar to an earlier story: {old}")
                    break
            if problems:
                log(f"  attempt {attempt} rejected: {'; '.join(problems[:3])}")
                continue
            lines = [s["line"] for s in scenes]
            durs = estimate_durations(scenes, lines, mins)
            if not (TARGET_TOTAL[0] <= sum(durs) <= TARGET_TOTAL[1]):
                problems = [f"total length would be {sum(durs):.1f}s; make the lines shorter or longer (target about 25s)"]
                log(f"  attempt {attempt}: {problems[0]}")
                continue
            built = (title_hi, title_en, plot_en, scenes)
            break
        if not built:
            log("  skipped (no valid story after 3 tries)")
            continue

        title_hi, title_en, plot_en, scenes = built
        log("  Script Doctor (grade, rewrite, grade again)...")
        lines, title_hi, score, review = doctor(llm, idea, title_hi, plot_en, scenes)
        durs = estimate_durations(scenes, lines, mins)
        name = unique_name(title_en)
        script = make_script(name, title_hi, plot_en, idea, scenes, lines, durs, score, review, llm.label)
        (REELS / name).mkdir(parents=True, exist_ok=True)
        (REELS / name / "script.json").write_text(json.dumps(script, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        history.add_used(date.today().isoformat(), name, f"{title_hi} ({title_en})", plot_en)
        batch_titles.append(f"{title_hi} ({title_en})")
        made.append({"name": name, "title": f"{title_hi} ({title_en})", "plot": plot_en, "seconds": sum(durs), "score": score})
        log(f"  saved reels/{name}/script.json  ({sum(durs):.1f}s, Doctor score {score})")

    if not made:
        print("No story passed the DASHX checks. Try again, or use a stronger local model (STORIES_MODEL).")
        return 1
    table = ["| name | title | plot | est. seconds | Doctor score |", "|---|---|---|---|---|"]
    for m in made:
        table.append(f"| {m['name']} | {m['title']} | {m['plot']} | {m['seconds']:.1f} | {m['score']} |")
    (ROOT / "stories").mkdir(exist_ok=True)
    (ROOT / "stories" / "last_run.md").write_text("\n".join(table) + "\n", encoding="utf-8")
    print("\n" + "\n".join(table))
    if len(made) < count:
        print(f"\nOnly {len(made)} of {count} stories passed the checks.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
