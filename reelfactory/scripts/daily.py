"""DASHX Reel Machine: make N finished reels, fully automatically.

    npm run daily -- 5                      (Gemma if it is ready, stories\\bank.md otherwise or as a fallback)
    npm run daily -- 5 --source bank        (only the hand-written bank)
    npm run daily -- 5 --source gemma       (only Gemma, no fallback)

For every reel:  story -> rule check -> Hindi voice -> fit timing + subtitles -> render -> auto-check (PASS/FAIL).
PASS reels are copied to output\\ready\\<date>\\ and listed in LIST.md. One reel failing never stops the others.
It never posts, uploads or deletes anything, and it writes no SEO text.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "tools" / "purffle-shorts"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import make_stories as ms  # noqa: E402
import fit_reel  # noqa: E402
import check_reel  # noqa: E402
from check_stories import template_check  # noqa: E402
from story_rules import dialogue_problems, hindi_problems, rule_problems, similar  # noqa: E402
from purffle_shorts.config import Settings  # noqa: E402
from purffle_shorts.history import History  # noqa: E402
from purffle_shorts.llm import LLM, ollama_models, ollama_url  # noqa: E402

PY = ROOT / ".venv" / "Scripts" / "python.exe"
if not PY.exists():  # Linux / GitHub Actions
    PY = Path(sys.executable)
BANK = ROOT / "stories" / "bank.md"
DIALOGUE_BANK = ROOT / "stories" / "dialogue_bank.md"
TODAY = date.today().isoformat()
READY = ROOT / "output" / "ready" / TODAY
TAIL_HI = "खेलो डैश एक्स के साथ!"  # OLD end-card tail (reels made before the call to action); kept to read old reels' endings
# The ONE end-card line, spoken and subtitled LAST (after the story and its joke). The same sentence is written in Roman
# letters by src/reel/templates/endCard.tsx. Kokoro needs Devanagari, and a subtitle must equal the voice.
CTA_HI = "अमेज़न, फ्लिपकार्ट या मीशो पर डैश एक्स क्रिकेट टेनिस बॉल सर्च करो।"
CTA_MAX_WORDS = 12
GEMMA = "gemma3:4b"
MIN_DOCTOR_SCORE = 80  # a Gemma story below this Doctor score is not used (the bank is used instead)
LOG_FILE: Path | None = None

# Cast. Main cast: sachin, surya, dadaji. The rest are original gali characters (no real people).
ROSTER = ["sachin", "surya", "dadaji", "aunty", "pintu", "golu", "meena", "coach", "bruno"]
BATTERS = ["sachin", "surya", "golu", "meena"]  # kids who bat
BOWLERS = BATTERS + ["coach"]
CATCHERS = ["dadaji", "aunty", "coach", "pintu"]  # grown-ups who sit on the chair and catch


def log(msg: str) -> None:
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    if LOG_FILE:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")


# --------------------------------------------------------------------------------------------------
# Gemma status
# --------------------------------------------------------------------------------------------------
def gemma_status() -> tuple[str, str]:
    models = ollama_models(ollama_url())
    if models is None:
        return "NOT STARTED", "Ollama is not running"
    if GEMMA in models:
        return "READY", f"{GEMMA} is installed"
    r = subprocess.run(["powershell", "-NoProfile", "-Command",
                        "Get-CimInstance Win32_Process -Filter \"Name='ollama.exe'\" | ForEach-Object { $_.CommandLine }"],
                       capture_output=True, text=True)
    if re.search(r"\bpull\b", r.stdout or ""):
        return "DOWNLOADING", "an `ollama pull` is running"
    return "NOT STARTED", f"{GEMMA} is not installed"


# --------------------------------------------------------------------------------------------------
# Story sources
# --------------------------------------------------------------------------------------------------
def parse_bank() -> list[dict]:
    if not BANK.exists():
        return []
    stories, cur = [], None
    for raw in BANK.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.startswith("## "):
            en, _, hi = line[3:].partition("|")
            cur = {"title_en": en.strip(), "title_hi": hi.strip(), "plot_en": "", "closing": "", "rows": []}
            stories.append(cur)
        elif cur is not None and line.startswith("plot:"):
            cur["plot_en"] = line[5:].strip()
        elif cur is not None and line.startswith("ending:"):
            cur["closing"] = line[7:].strip()
        elif cur is not None and line.startswith("- ") and line.count("|") == 4:
            t, a, b, board, text = [c.strip() for c in line[2:].split("|")]
            cur["rows"].append({"template": t, "who_a": a, "who_b": b, "board": board, "line_hi": text})
    return stories


def known_closings(history: History) -> list[str]:
    """Endings of every earlier story: used.md plus the last scenes of all reels already made."""
    out = list(history.closings())
    for f in (ROOT / "reels").glob("*/script.json"):
        try:
            sc = json.loads(f.read_text(encoding="utf-8"))["scenes"][-1]
        except Exception:
            continue
        voice = sc.get("voice", "")
        if sc.get("template") == "hero-end":
            out.append(voice.replace(ms.BRAND_EN, "").strip())
        elif sc.get("template") == "end-card" and voice != CTA_HI:  # a CTA-only end card has no story ending in it
            out.append(voice.replace(TAIL_HI, "").strip())
    return [c for c in out if c]


def story_problems(story: dict, history: History, batch: list[str], closings: list[str]) -> list[str]:
    """Rule check of a story BEFORE anything is voiced: DASHX rules, repetition, different ending."""
    problems = [f"title {p}" for p in hindi_problems(story["title_hi"], 1, 10)]
    problems += [f"title_en/plot_en {p}" for p in rule_problems(story["title_en"] + " " + story["plot_en"])]
    n = len(story["closing"].split())
    if not 2 <= n <= 5:
        problems.append(f"ending has {n} words (want 2-5)")
    for old in history.recent_titles(60) + batch:
        if similar(story["title_en"], old) > 0.8 or similar(story["title_hi"], old) > 0.8:
            problems.append(f"title too similar to an earlier story: {old}")
            break
    for c in closings:
        if story["closing"] == c or similar(story["closing"], c) > 0.6:
            problems.append(f"ending repeats an earlier ending: {c}")
            break
    return problems


def build_body(data: dict) -> tuple[list[dict], list[str]]:
    """The 4 story scenes (template + params + Hindi line) from story data. Characters are checked and repaired
    so every role makes sense: the bowler bowls, the batter bats, grown-ups sit and catch, Bruno only watches."""
    rows = data.get("scenes") or []
    if len(rows) != 4:
        return [], [f"need exactly 4 scenes, got {len(rows)}"]
    problems: list[str] = []
    if len({r.get("template") for r in rows}) < 3:
        problems.append("use at least 3 different visuals (templates)")
    other = lambda *used: next(c for c in BATTERS if c not in used)
    scenes = []
    for i, r in enumerate(rows, 1):
        t, a, b = r.get("template"), r.get("who_a"), r.get("who_b")
        board = str(r.get("board", "")).strip()
        line = " ".join(str(r.get("line_hi", "")).split())
        problems += [f"scene {i} line {p}" for p in hindi_problems(line, 2, 8)]
        a = a if a in ROSTER else "sachin"
        b = b if (b in ROSTER and b != a) else next(c for c in ROSTER if c != a and c != "bruno")
        if t == "face-off":
            text = board.upper()
            params = {"left": a, "right": b, "boardText": text if re.fullmatch(r"[A-Z?!.' ]{1,7}", text) else "?"}
        elif t == "run-up":
            bowler = a if a in BOWLERS else "surya"
            batter = b if (b in BATTERS and b != bowler) else other(bowler)
            params = {"batter": batter, "bowler": bowler}
        elif t == "shot":
            batter = a if a in BATTERS else "sachin"
            params = {"batter": batter, "watcher": b if b != batter else next(c for c in ROSTER if c != batter)}
        elif t == "catch":
            catcher = a if a in CATCHERS else "dadaji"
            w1 = b if (b in ROSTER and b != catcher) else other(catcher)
            w2 = board if (board in ROSTER and board not in (catcher, w1)) else next(c for c in ROSTER if c not in (catcher, w1))
            params = {"catcher": catcher, "watchers": [w1, w2]}
        else:
            problems.append(f"scene {i}: unknown template {t!r}")
            continue
        scenes.append({"template": t, "params": params, "line": line})
    closing = " ".join(str(data.get("closing_hi", "")).split())
    problems += [f"closing line {p}" for p in hindi_problems(closing, 2, 5)]
    return scenes, problems


def from_llm_data(data: dict, seed: int, mins: dict) -> tuple[dict | None, list[str]]:
    """Story data in make_stories' LLM format -> our story dict (4 body scenes + ending)."""
    scenes, problems = build_body(data)
    if not scenes:
        return None, problems
    story = {
        "title_hi": " ".join(str(data.get("title_hi", "")).split()),
        "title_en": " ".join(str(data.get("title_en", "")).split()),
        "plot_en": " ".join(str(data.get("plot_en", "")).split()),
        "scenes": scenes,
        "closing": " ".join(str(data.get("closing_hi", "")).split()),
    }
    return story, problems



# --------------------------------------------------------------------------------------------------
# Dialogue stories (stories/dialogue_bank.md): every spoken line is said by a character, in the first person.
#   - template | who_a | who_b | board | speaker: line // speaker: line
# --------------------------------------------------------------------------------------------------
def parse_dialogue_bank() -> list[dict]:
    if not DIALOGUE_BANK.exists():
        return []
    stories, cur = [], None
    for raw in DIALOGUE_BANK.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.startswith("## "):
            en, _, hi = line[3:].partition("|")
            cur = {"title_en": en.strip(), "title_hi": hi.strip(), "plot_en": "", "closing": "", "hook": "", "rows": []}
            stories.append(cur)
        elif cur is not None and line.startswith("plot:"):
            cur["plot_en"] = line[5:].strip()
        elif cur is not None and line.startswith("ending:"):
            cur["closing"] = line[7:].strip()
        elif cur is not None and line.startswith("hook:"):
            cur["hook"] = line[5:].strip()
        elif cur is not None and line.startswith("- ") and line.count("|") == 4:
            t, a, b, board, text = [c.strip() for c in line[2:].split("|")]
            entries = []
            for part in text.split("//"):
                who, _, said = part.partition(":")
                entries.append({"speaker": who.strip(), "line": " ".join(said.split())})
            cur["rows"].append({"template": t, "who_a": a, "who_b": b, "board": board, "dialogue": entries})
    return stories


def scene_params(r: dict) -> tuple[dict | None, str]:
    """Template parameters for one bank row (same rules as build_body) and the problem text, if any."""
    t, a, b, board = r.get("template"), r.get("who_a"), r.get("who_b"), str(r.get("board", "")).strip()
    a = a if a in ROSTER else "sachin"
    b = b if (b in ROSTER and b != a) else next(c for c in ROSTER if c != a and c != "bruno")
    if t == "face-off":
        text = board.upper()
        return {"left": a, "right": b, "boardText": text if re.fullmatch(r"[A-Z?!.' ऀ-ॿ]{1,8}", text) else "?"}, ""
    if t == "run-up":
        if a not in BOWLERS or b not in BATTERS or a == b:
            return None, f"run-up needs a bowler ({', '.join(BOWLERS)}) and a batter ({', '.join(BATTERS)})"
        return {"batter": b, "bowler": a}, ""
    if t == "shot":
        if a not in BATTERS:
            return None, "shot needs a batter as the first name"
        return {"batter": a, "watcher": b}, ""
    if t == "catch":
        if a not in CATCHERS:
            return None, f"catch needs a grown-up catcher ({', '.join(CATCHERS)})"
        w2 = board if (board in ROSTER and board not in (a, b)) else next(c for c in ROSTER if c not in (a, b))
        return {"catcher": a, "watchers": [b, w2]}, ""
    return None, f"unknown template {t!r}"


def scene_cast(params: dict) -> set[str]:
    out: set[str] = set()
    for v in params.values():
        out |= {x for x in (v if isinstance(v, list) else [v]) if x in ROSTER}
    return out


def build_dialogue_body(data: dict) -> tuple[list[dict], list[str]]:
    rows = data.get("scenes") or []
    if len(rows) != 4:
        return [], [f"need exactly 4 scenes, got {len(rows)}"]
    problems: list[str] = []
    if len({r.get("template") for r in rows}) < 3:
        problems.append("use at least 3 different visuals (templates)")
    scenes = []
    for i, r in enumerate(rows, 1):
        params, why = scene_params(r)
        if params is None:
            problems.append(f"scene {i}: {why}")
            continue
        cast = scene_cast(params)
        if r["template"] == "face-off" and (params["boardText"] == "?" and str(r.get("board", "")).strip() != "?" or re.search(r"[A-Za-z]", str(r.get("board", "")))):
            problems.append(f"scene {i}: the pop-up word must be Hindi (Devanagari, up to 8 characters), not {r.get('board')!r}")
        ds = r.get("dialogue") or []
        if not 1 <= len(ds) <= 2:
            problems.append(f"scene {i}: needs 1 or 2 dialogue lines, got {len(ds)}")
        if len(ds) == 2 and ds[0]["speaker"] == ds[1]["speaker"]:
            problems.append(f"scene {i}: the two lines must be said by two different characters")
        for d in ds:
            problems += [f"scene {i} line {p}" for p in dialogue_problems(d["line"], d["speaker"])]
            if d["speaker"] not in cast:
                problems.append(f"scene {i}: {d['speaker']} speaks but is not in the scene ({', '.join(sorted(cast))})")
        scenes.append({"template": r["template"], "params": params, "dialogue": ds, "line": " ".join(d["line"] for d in ds)})
    closing = " ".join(str(data.get("closing_hi", "")).split())
    problems += [f"closing line {p}" for p in hindi_problems(closing, 2, 5)]
    return scenes, problems


def from_dialogue_data(data: dict, seed: int = 0, mins: dict | None = None) -> tuple[dict | None, list[str]]:
    scenes, problems = build_dialogue_body(data)
    if not scenes:
        return None, problems
    return {
        "title_hi": " ".join(str(data.get("title_hi", "")).split()),
        "title_en": " ".join(str(data.get("title_en", "")).split()),
        "plot_en": " ".join(str(data.get("plot_en", "")).split()),
        "scenes": scenes,
        "closing": " ".join(str(data.get("closing_hi", "")).split()),
        "hook": " ".join(str(data.get("hook", "")).split()),
        "format": "dialogue",
    }, problems


def cast_of(story_or_script: dict) -> set[str]:
    out: set[str] = set()
    for sc in story_or_script["scenes"]:
        for v in sc.get("params", {}).values():
            out |= {x for x in (v if isinstance(v, list) else [v]) if x in ROSTER}
    return out


def recent_cast(history: History, batch_casts: list[set[str]]) -> set[str]:
    """Characters used in this batch and in the last 3 reels already made (to give the next reel new faces)."""
    seen: set[str] = set().union(*batch_casts) if batch_casts else set()
    for row in history._rows()[-3:]:
        f = ROOT / "reels" / row[1] / "script.json"
        if f.exists():
            seen |= cast_of(json.loads(f.read_text(encoding="utf-8")))
    return seen


def story_from_bank(history: History, batch: list[str], closings: list[str], mins: dict,
                    batch_casts: list[set[str]] | None = None) -> dict | None:
    done = " ".join(history.recent_titles(500) + batch)
    seen = recent_cast(history, batch_casts or [])
    best, best_score = None, (-1,)
    for i, b in enumerate(parse_bank()):
        if b["title_hi"] in done or b["title_en"] in done:
            continue
        data = {"title_hi": b["title_hi"], "title_en": b["title_en"], "plot_en": b["plot_en"],
                "scenes": b["rows"], "closing_hi": b["closing"]}
        story, problems = from_llm_data(data, seed=i, mins=mins)
        if story:
            problems += story_problems(story, history, batch, closings)
        if not story or problems:
            log(f"  bank story '{b['title_en']}' skipped: {'; '.join(problems[:3])}")
            continue
        cast = cast_of(story)
        last = (batch_casts or [set()])[-1]
        # new faces first; then the least overlap with the previous reel; then more of the new characters
        score = (len(cast - seen), -len(cast & last), len(cast - {"sachin", "surya", "dadaji"}))
        if score > best_score:
            story["writer"] = "hand-written story bank (stories/bank.md)"
            story["idea"] = b["title_en"]
            best, best_score = story, score
    return best


def story_from_gemma(llm: LLM, ideas: list[dict], history: History, batch: list[str], closings: list[str],
                     mins: dict) -> dict | None:
    while ideas:
        idea = ideas.pop(0)
        subject = re.split(r"[“”\"]", idea["subject"])[0].strip(" ,'’")  # drop JSON junk after the idea
        if len(subject) < 6:
            continue
        idea = {**idea, "subject": subject}
        log(f"  Gemma idea: {idea['subject']}")
        recent = (history.recent_titles(ms.RECENT_FOR_WRITER) + batch)[-ms.RECENT_FOR_WRITER:]
        problems: list[str] = []
        story = None
        for attempt in range(1, 4):
            system, user = ms.story_prompt(idea, recent, problems)
            try:
                data = llm.complete_json(system, user, ms.STORY_SCHEMA, max_tokens=2500)
            except Exception as e:
                problems = [f"the reply was not usable JSON ({e})"]
                continue
            story, problems = from_llm_data(data, seed=len(batch) + attempt, mins=mins)
            if story:
                problems += story_problems(story, history, batch, closings)
            if story and not problems:
                break
            story = None
            log(f"    attempt {attempt} rejected: {'; '.join(problems[:3])}")
        if not story:
            continue
        # Script Doctor two-pass (purffle-shorts): only the wording is taken back
        log("    Script Doctor (grade, rewrite, grade again)...")
        body = story["scenes"] + [{"template": "hero-end", "params": {"cast": ["sachin", "dadaji", "surya"]}, "line": story["closing"]}]
        lines, title_hi, score, _review = ms.doctor(llm, idea, story["title_hi"], story["plot_en"], body)
        story["title_hi"] = title_hi
        for sc, line in zip(story["scenes"], lines[:-1]):
            sc["line"] = line
        story["closing"] = lines[-1]
        late = story_problems(story, history, batch, closings)
        if late:
            log(f"    after the Doctor: {'; '.join(late[:3])} -> next idea")
            continue
        if score is None or score < MIN_DOCTOR_SCORE:
            log(f"    Script Doctor score {score} is below {MIN_DOCTOR_SCORE}: Gemma's Hindi is not good enough -> next idea")
            continue
        story["writer"] = f"Gemma {GEMMA} via purffle-shorts planner + Script Doctor (score {score})"
        story["idea"] = idea["subject"]
        return story
    return None


# --------------------------------------------------------------------------------------------------
# Build, voice, fit, render, check
# --------------------------------------------------------------------------------------------------
def write_script(story: dict, mins: dict) -> tuple[str, dict]:
    # the call to action comes LAST, after the story and the joke. story["closing"] stays in the history (used.md) but is no longer spoken:
    # the end card is only the CTA, so the story scenes keep their time and the CTA is never shortened.
    end = {"template": "end-card", "params": {}, "line": CTA_HI}
    scenes = story["scenes"] + [end]
    lines = [s["line"] for s in scenes]
    durs = ms.estimate_durations(scenes, lines, mins)
    durs[-1] = fit_reel.END_CARD_MAX
    name = ms.unique_name(story["title_en"])
    script = ms.make_script(name, story["title_hi"], story["plot_en"], {"subject": story["idea"]}, scenes, lines, durs,
                            None, [], "n/a")
    if story.get("format") == "dialogue":
        script["dialogue_format"] = 2
        script["story"]["hook"] = story.get("hook", "")  # the reel-specific hook line used for captions
        for sc, src in zip(script["scenes"], scenes):
            if src.get("dialogue"):
                sc["dialogue"] = [{"speaker": d["speaker"], "line": d["line"]} for d in src["dialogue"]]
                sc["speaker"], sc["line"] = sc["dialogue"][0]["speaker"], sc["dialogue"][0]["line"]
                if sc["template"] == "run-up":
                    sc["params"]["near"] = True  # the bowler starts on screen so a talking bowler is visible
            else:  # the end card: the narrator
                sc["speaker"], sc["line"] = "narrator", sc["voice"]
    script["story"]["writer"] = story["writer"]
    script["story"]["closing"] = story["closing"]
    script["story"].pop("doctor_score", None)
    script["story"].pop("doctor_notes", None)
    script["story"]["durations_are_estimates"] = "scripts/fit_reel.py sets the real durations after the voice is made."
    (ROOT / "reels" / name).mkdir(parents=True, exist_ok=True)
    (ROOT / "reels" / name / "script.json").write_text(json.dumps(script, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return name, script


def precheck(script: dict) -> list[str]:
    """Rules on the final script: spoken lines, end card, templates."""
    problems = []
    scenes = script["scenes"]
    for sc in scenes:
        last = sc["template"] == "end-card"
        problems += [f"scene {sc['id']} {p}" for p in hindi_problems(sc["voice"], 3 if last else 2, CTA_MAX_WORDS if last else 8)]
        if last and sc["voice"] != CTA_HI:
            problems.append(f"scene {sc['id']}: the end card must speak the call to action exactly")
        if sc["subtitle"] != sc["voice"]:
            problems.append(f"scene {sc['id']}: subtitle differs from voice")
    if scenes[-1]["template"] != "end-card" or sum(s["template"] == "end-card" for s in scenes) != 1:
        problems.append("the reel must end with exactly one end-card")
    if len({s["template"] for s in scenes[:-1]}) < 3:
        problems.append("fewer than 3 different visuals")
    problems += [p for p in template_check(script) if not p.startswith("warning")]
    return problems


def run(cmd: list[str], timeout: int) -> tuple[int, str]:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, env=env)
    return r.returncode, (r.stdout + r.stderr)[-1500:]


def produce(name: str, script: dict) -> dict:
    """voice -> fit -> render -> check for one reel. Never raises: failures come back as a record."""
    rec = {"name": name, "status": "FAIL", "reasons": [], "duration": None}
    try:
        bad = precheck(script)
        if bad:
            rec["reasons"] = bad
            return rec
        log("  voice (kokoro)...")
        code, out = run([str(PY), "scripts/make_voice.py", name, "hm_omega", "1.0"], 900)
        if code != 0:
            rec["reasons"] = [f"voice failed: {out[-300:]}"]
            return rec
        ok, notes = fit_reel.fit(name)
        log(f"  fit: {'; '.join(notes)}")
        if not ok:
            rec["reasons"] = notes
            return rec
        log("  render (revideo, about 1.5 minutes)...")
        started = time.time()
        code, out = run(["node", "dist/reel.js", name], 1800)
        mp4 = ROOT / "output" / "reels" / f"{name}.mp4"
        if code != 0 or not mp4.exists() or mp4.stat().st_mtime < started:
            rec["reasons"] = [f"render failed: {out[-400:]}"]
            return rec
        passed, why, seconds = check_reel.check(name)
        rec.update(status="PASS" if passed else "FAIL", reasons=why, duration=seconds)
    except Exception as e:  # one reel must never stop the others
        rec["status"] = "ERROR"
        rec["reasons"] = [f"{type(e).__name__}: {e}"]
    return rec


def characters(script: dict) -> list[str]:
    names: list[str] = []
    for sc in script["scenes"]:
        for v in sc.get("params", {}).values():
            for x in (v if isinstance(v, list) else [v]):
                if x in ROSTER and x not in names:
                    names.append(x)
    return [n.capitalize() for n in names]


def update_ready(rec: dict, script: dict) -> None:
    READY.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "output" / "reels" / f"{rec['name']}.mp4", READY / f"{rec['name']}.mp4")
    cover = f"{rec['name']}-cover.jpg"
    if check_reel.make_cover(ROOT / "output" / "reels" / f"{rec['name']}.mp4", READY / cover) is None:
        cover = ""
    manifest_file = READY / "manifest.json"
    manifest = json.loads(manifest_file.read_text(encoding="utf-8")) if manifest_file.exists() else []
    manifest = [m for m in manifest if m["file"] != f"{rec['name']}.mp4"]
    manifest.append({"file": f"{rec['name']}.mp4", "title": script["title"], "plot": script["story"]["plot"],
                     "characters": ", ".join(characters(script)), "duration": round(rec["duration"], 1), "cover": cover})
    manifest_file.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    rows = ["# Ready reels " + TODAY, "", "| file | cover | title | plot | characters | duration (s) |", "|---|---|---|---|---|---|"]
    for m in manifest:
        rows.append(f"| {m['file']} | {m.get('cover', '')} | {m['title']} | {m['plot']} | {m['characters']} | {m['duration']} |")
    (READY / "LIST.md").write_text("\n".join(rows) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------------------------------
def main() -> int:
    global LOG_FILE
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    count = int(args[0]) if args and args[0].isdigit() else 5
    redo = sys.argv[sys.argv.index("--redo") + 1].split(",") if "--redo" in sys.argv else []
    source = "auto"
    if "--source" in sys.argv:
        source = sys.argv[sys.argv.index("--source") + 1]
    (ROOT / "logs").mkdir(exist_ok=True)
    LOG_FILE = ROOT / "logs" / f"daily-{datetime.now().strftime('%Y%m%d-%H%M%S')}.log"

    if redo:  # fit, render and check reels whose scripts already exist (no new story)
        code, out = run(["node", "node_modules/typescript/bin/tsc"], 300)
        if code != 0:
            log(f"tsc failed: {out}")
            return 1
        done = []
        for name in redo:
            script = json.loads((ROOT / "reels" / name / "script.json").read_text(encoding="utf-8"))
            log(f"=== Redo {name} ===")
            rec = produce(name, script)
            if rec["status"] == "PASS":
                update_ready(rec, json.loads((ROOT / "reels" / name / "script.json").read_text(encoding="utf-8")))
            log(f"  {rec['status']} {name}" + (f" ({rec['duration']:.1f}s)" if rec.get("duration") else ""))
            for r in rec["reasons"]:
                log(f"    - {r}")
            done.append(rec)
        return 0 if all(r["status"] == "PASS" for r in done) else 1

    status, detail = gemma_status()
    log(f"Gemma {status} ({detail})")
    use_gemma = source in ("auto", "gemma") and status == "READY"
    if source == "gemma" and not use_gemma:
        log("--source gemma but Gemma is not ready: nothing to do")
        return 1
    log(f"Story source: {'Gemma, with bank fallback' if use_gemma and source == 'auto' else 'Gemma only' if use_gemma else 'stories/bank.md'}")

    code, out = run(["node", "node_modules/typescript/bin/tsc"], 300)  # compile the render script once
    if code != 0:
        log(f"tsc failed, cannot render: {out}")
        return 1

    mins = ms.template_minimums()
    history = History(ms.USED)
    llm, ideas = None, []
    if use_gemma:
        try:
            llm = LLM(Settings(llm_provider="ollama", llm_model=GEMMA))
            log("Gemma: planning ideas...")
            ideas = ms.plan(llm, history, count + 4)
            log(f"Gemma: {len(ideas)} idea(s)")
        except Exception as e:
            log(f"Gemma planner failed ({e}); using the bank")
            llm = None

    results, batch, batch_casts = [], [], []
    for i in range(1, count + 1):
        log(f"=== Reel {i}/{count} ===")
        closings = known_closings(history)
        story, used = None, ""
        if llm and ideas:
            try:
                story = story_from_gemma(llm, ideas, history, batch, closings, mins)
                used = "Gemma"
            except Exception as e:
                log(f"  Gemma story failed: {e}")
        if story is None and source != "gemma":
            if llm:
                log("  Gemma gave no valid story: falling back to the bank")
            story = story_from_bank(history, batch, closings, mins, batch_casts)
            used = "bank"
        if story is None:
            log("  no story available for this slot")
            results.append({"name": "-", "title": "-", "status": "FAIL", "reasons": ["no story available"], "duration": None})
            continue
        name, script = write_script(story, mins)
        history.add_used(TODAY, name, f"{story['title_hi']} ({story['title_en']})", story["plot_en"], story["closing"])
        batch.append(f"{story['title_hi']} ({story['title_en']})")
        batch_casts.append(cast_of(script))
        log(f"  story [{used}]: {name} | {story['title_hi']} | ending: {story['closing']}")
        rec = produce(name, script)
        rec.update(title=story["title_hi"], source=used)
        results.append(rec)
        if rec["status"] == "PASS":
            update_ready(rec, json.loads((ROOT / "reels" / name / "script.json").read_text(encoding="utf-8")))
        log(f"  {rec['status']} {name}" + (f" ({rec['duration']:.1f}s)" if rec.get("duration") else ""))
        for r in rec["reasons"]:
            log(f"    - {r}")

    passed = [r for r in results if r["status"] == "PASS"]
    log("=== Summary ===")
    log(f"Gemma {status}; {len(passed)} of {count} reels PASS; ready folder: {READY if passed else '(none)'}")
    for r in results:
        log(f"  {r['status']:5} {r['name']:28} {r.get('source', '-'):6} {r.get('title', '')}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
