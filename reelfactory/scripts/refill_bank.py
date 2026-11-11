"""Daily story maker: adds 2 new stories a day to stories/dialogue_bank.md with the free Gemini key, using very little quota.

    python scripts/refill_bank.py                              # the daily run: aim for 2 stories, at most 12 Gemini calls per day
    python scripts/refill_bank.py --dry-run --target 6 --max-calls 30   # review run: nothing is written to the bank
    python scripts/refill_bank.py --probe                      # only list the Gemini models (no story)

Rules (every story must pass ALL of these, nothing is lowered to reach the target; 0 or 1 story on a bad day is fine):
  1. Gemini writes ONE story in the bank format from a random gully-cricket situation (stories/situations.json) and a hook
     formula (stories/viral_formats.json, idea credit: rediumvex/viral-hooks-skill, MIT)
  2. the same checker as for hand-written stories (scripts/check_dialogue_bank.py: format, DASHX rules, roles, hook, score >= 80,
     no repeated line / ending / hook against the whole bank and every reel made)
  3. one repair try per story that failed only on fixable things
  4. a second Gemini call grades funny / clear / natural Hindi / kid-safe (all >= 7)
Quota safety:
  - stops as soon as the target number of stories is accepted
  - hard cap of Gemini calls per quota day (default 12, counted in stories/refill_usage.json); a 429 / quota answer ends the day at once
  - skips completely when the bank has more than 60 usable stories
  - ALWAYS exits 0: a Gemini problem is only a warning, it can never turn the poster or the reel factory red
No token is ever printed.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BANK = ROOT / "stories" / "dialogue_bank.md"
LOG = ROOT / "stories" / "refill_log.md"
DRY = ROOT / "stories" / "refill_dry_run.md"
USAGE = ROOT / "stories" / "refill_usage.json"
DAILY = ROOT / "stories" / "refill_daily.txt"
URL = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
KEY = os.environ.get("GEMINI_API_KEY", "").strip()
MIN_JUDGE = 7
MIN_MEERUT = 6   # the 'Meerut feel' and 'twist' scores of the second-model grade (same call as before, no extra Gemini call)
MIN_TWIST = 6
BUDGET_S = 540   # the whole run stops after this many seconds, so the daily job never hangs
CALLS = {"n": 0, "cap": 12}
STATE: dict = {"models": [], "idx": 0, "quota_hit": False, "last_raw": ""}
CAST_HELP = {
    "sachin": "main batter: confident, loves big shots, a little sleepy",
    "surya": "main bowler: boastful, fast, funny when he loses",
    "dadaji": "calm elder who sits on his chair and catches everything",
    "aunty": "neighbour: warm, sharp-eyed, protects her window",
    "pintu": "the umpire: serious about rules, blows his whistle",
    "golu": "tiny fielder: spots things first",
    "meena": "girl batter: fearless, hits sixes",
    "coach": "big loud coach uncle, laughs at the end",
    "bruno": "the dog: only barks (bruno: भौं भौं!), never bats",
    "pappu": "Pappu Bhaiya, the gali captain: talks big, every plan backfires",
    "chhotu": "Chhotu, the small shop boy: sharp, knows bats, balls and rates",
    "mintu": "Mintu, the sneaky kid of the rival gali: tries tricks and gets caught",
}


def cast_help(who: str) -> str:
    """The voice card of a character for the writer prompt (stories/characters.json); falls back to the short CAST_HELP line."""
    try:
        c = json.loads((ROOT / "stories" / "characters.json").read_text(encoding="utf-8"))["characters"][who]
        return (f"{c['role']}: {c['trait']} | wants: {c['wants']} | often says: " + ", ".join(f"«{w}»" for w in c["voice_words"])
                + " | never says: " + ", ".join(f"«{w}»" for w in c["voice_avoid"]) + f" | style: {c['style']}")
    except Exception:
        return CAST_HELP.get(who, who)


def scrub(s) -> str:
    s = str(s)
    return s.replace(KEY, "<token>") if KEY else s


def clean(x, n: int = 200) -> str:
    """Make model/checker text safe for the GitHub log: no control characters, no '::' workflow commands, bounded length."""
    t = re.sub(r"[\x00-\x1f\x7f  ]+", " ", str(x))
    return scrub(t).replace("::", ": :")[:n]


# ---------------------------------------------------------------------------------------------------
# quota day + call counter (Gemini's free quota resets at midnight US Pacific = about 13:30 IST)
def quota_day() -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=8)).date().isoformat()


def load_usage() -> int:
    try:
        j = json.loads(USAGE.read_text(encoding="utf-8"))
        return int(j["calls"]) if j.get("day") == quota_day() else 0
    except Exception:
        return 0


def save_usage() -> None:
    USAGE.write_text(json.dumps({"day": quota_day(), "calls": CALLS["n"], "cap": CALLS["cap"]}) + "\n", encoding="utf-8", newline="\n")


def calls_left() -> int:
    return 0 if STATE["quota_hit"] else max(0, CALLS["cap"] - CALLS["n"])


# ---------------------------------------------------------------------------------------------------
def http(url: str, body: dict | None, timeout: int) -> tuple[int, str]:
    """One Gemini HTTP call, counted. (status, text). Never raises."""
    CALLS["n"] += 1
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, headers={"Authorization": "Bearer " + KEY, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        if e.code == 429:
            STATE["quota_hit"] = True   # quota answer: the day is over, no retry
        try:
            msg = json.loads(raw)
            msg = msg[0] if isinstance(msg, list) else msg
            msg = msg.get("error", raw)
            msg = msg.get("message", msg) if isinstance(msg, dict) else msg
        except Exception:
            msg = raw
        return e.code, scrub(msg)[:240]
    except Exception as e:  # network problem / timeout
        return 0, scrub(e)[:200]


def gemini_models() -> list[str]:
    """Ask Gemini which models this key may use and rank the text 'flash' models (newest stable first). Model names change often."""
    code, raw = http("https://generativelanguage.googleapis.com/v1beta/openai/models", None, 60)
    if code != 200:
        print(f"gemini model list failed: HTTP {code} {clean(raw, 100)}")
        return ["gemini-flash-latest"]
    try:
        names = [m["id"].split("/")[-1] for m in json.loads(raw).get("data", [])]
    except Exception:
        return ["gemini-flash-latest"]
    bad = re.compile(r"(image|tts|live|audio|embed|vision|robotics|computer|thinking|exp|learnlm|gemma|aqa|imagen|veo|omni|nano)")
    cand = [n for n in names if n.startswith("gemini") and "flash" in n and not bad.search(n)]

    def rank(n: str):
        nums = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", n)]
        return (0 if "preview" not in n else 1, 1 if "lite" in n else 0, -(nums[0] if nums else 0), n)
    models = sorted(cand, key=rank)[:4] or ["gemini-flash-latest"]
    print("gemini models to use:", ", ".join(models))
    return models


def ask(messages: list[dict], temperature: float = 0.9, max_tokens: int = 4000) -> tuple[int, str]:
    """One Gemini chat call. -1 = no call left today. On 404 / 5xx / timeout it moves to the next model (each try is a counted call).
    A 429 / quota answer stops everything for the day: no retry."""
    while True:
        if calls_left() <= 0:
            return -1, "no Gemini call left today"
        m = STATE["models"][STATE["idx"]]
        payload = {"model": m, "messages": messages, "temperature": temperature, "max_tokens": max_tokens,
                   "reasoning_effort": "low"}   # new Gemini models "think" first; without this the thinking can eat the whole token budget
        code, raw = http(URL, payload, 100)
        if code == 200:
            try:
                return 200, json.loads(raw)["choices"][0]["message"]["content"] or ""
            except Exception:
                STATE["last_raw"] = scrub(raw)[:300]
                return 200, ""
        if code in (0, 404, 500, 502, 503, 504) and STATE["idx"] + 1 < len(STATE["models"]):
            STATE["idx"] += 1
            print(f"  model {m}: HTTP {code}, switching to {STATE['models'][STATE['idx']]}")
            continue
        return code, raw


# ---------------------------------------------------------------------------------------------------
def bank_header() -> str:
    t = BANK.read_text(encoding="utf-8")
    return t.split("\n## ", 1)[0].strip()


def examples(n: int = 2) -> str:
    blocks = re.split(r"\n(?=## )", BANK.read_text(encoding="utf-8"))[1:]
    return "\n\n".join(random.sample(blocks, min(n, len(blocks)))).strip()


def usable_count() -> tuple[int, int]:
    """(stories left that the factory can still use, stories in the bank). Same tests as factory/pipeline.py _bank()."""
    import daily  # noqa: PLC0415
    from factory import story as sm  # noqa: PLC0415
    hist = daily.History(daily.ms.USED)
    done = " ".join(hist.recent_titles(500))
    ref = sm.corpus()
    stories, left = daily.parse_dialogue_bank(), 0
    for i, b in enumerate(stories):
        if b["title_hi"] in done or b["title_en"] in done:
            continue
        data = {"title_hi": b["title_hi"], "title_en": b["title_en"], "plot_en": b["plot_en"], "scenes": b["rows"], "closing_hi": b["closing"], "hook": b.get("hook", ""), "card": b.get("card", ""), "series": b.get("series", ""), "ep": b.get("ep", "")}
        st, probs = daily.from_dialogue_data(data, i, {})
        if st:
            probs += daily.story_problems(st, hist, [], [])
        if st and not probs and sm.score_story(st, ref=ref)["score"] >= 70:
            left += 1
    return left, len(stories)


FORMATS = ["rivalry", "shop", "normal", "series", "normal"]   # the daily mix: 2 of 5 stories are the new formats, 1 of 5 is a Bruno Files episode


def next_episode(bank_text: str) -> int:
    eps = [int(x) for x in re.findall(r"^ep: *([0-9]+)", bank_text, re.M)]
    return (max(eps) + 1) if eps else 1


FORMAT_HELP = {
    "normal": "A normal gully-cricket comedy.",
    "rivalry": "RIVALRY: our gali against Mintu's gali. Mintu (rival kid) tries a sneaky trick to win (a fake no-ball call, a swapped ball, a late 'rule'), "
               "our side (Pappu Bhaiya talks big, Golu spots the trick) turns it around. Mintu must be one of the characters. The joke is that the trick backfires.",
    "shop": "SHOP COUNTER COMEDY at a small Meerut sports shop. Chhotu (small shop boy) is behind the counter: sharp, knows every bat, ball and rate, "
            "and always one step ahead of the customer (Pappu Bhaiya, Surya or Sachin). Chhotu must be one of the characters. "
            "Never say the brand name DASHX, never say a price or call anything 'best'. At most Chhotu confidently hands over 'the heavy tennis ball' that takes the hit. It must feel like comedy, never an ad.",
    "series": "BRUNO FILES, episode {ep}: Bruno the dog and Golu (who spots clues nobody believes) and Surya (boasts, then it backfires). "
              "The story is a COMPLETE joke by itself. Only the LAST spoken line plants tomorrow's question (it ends with ?). No extra scene, no 'to be continued'.",
}


def prompt_for(seed: dict, titles: list[str], endings: list[str], fmt: str = "normal", ep: int = 1) -> list[dict]:
    pool = ["sachin", "surya", "dadaji", "aunty", "pintu", "golu", "meena", "coach", "bruno", "pappu", "chhotu", "mintu"]
    must = {"rivalry": ["mintu", "pappu"], "shop": ["chhotu"], "series": ["bruno", "golu"]}.get(fmt, [])
    cast = must + random.sample([c for c in pool if c not in must], 4 - len(must))
    if not set(cast) & {"sachin", "surya", "pappu", "mintu", "chhotu"}:
        cast[-1] = random.choice(["sachin", "surya"])
    hook = seed["formula"]
    sysmsg = (
        "You write ONE short funny cartoon story for kids, as a 25-second Hindi reel about gully cricket in Meerut, India. "
        "You follow the file format below EXACTLY. Output only the story block, nothing else, no code fence, no explanation.\n\n"
        + bank_header()
        + "\n\nExtra hard rules:\n"
        "- Write all spoken lines, the ending, the hook, the card and the Hindi title in natural everyday Hindi (Devanagari), the way kids in Meerut talk. Short, simple words, light western-UP flavour (अरे यार, ओ भाई), no heavy dialect.\n"
        "- English is allowed only in the title before the | and in the plot line. No digits anywhere in Hindi text.\n"
        "- Spell the names exactly: सचिन, सूर्या, दादाजी, आंटी, पिंटू, गोलू, मीना, कोच, ब्रूनो, पप्पू भैया (पप्पू), छोटू, मिंटू.\n"
        "- VOICE: every character sounds like themselves. Use what each character WANTS as their goal in the story, let them reach for their own 'often says' words and phrases, and NEVER put a 'never says' word or phrase in their mouth. "
        "Pappu, Chhotu and Mintu must not sound alike: Pappu is a loud captain with big promises, Chhotu is a quick polite shop boy, Mintu is sweet and innocent while he cheats.\n"
        "- The `plot:` line must describe exactly what the spoken lines show: every character the plot names must appear in the story, and every character who speaks more than once must be named in the plot.\n"
        "- Use at least 3 different templates among the 4 scenes. A story must NOT end in a catch scene unless the joke needs it.\n"
        "- Never mention price, discounts, 'best', brands (also not DASHX), politics, religion, accidents, hospitals or police.\n"
        "- Each scene has 1 or 2 lines. With 2 lines the two speakers differ. The speaker of every line must be on stage in that scene, "
        "and a character named inside a line must be on stage in that scene too.\n"
        "- COLD OPEN: the FIRST spoken line is the conflict or the payoff already happening (a loss, a claim, a boast, a trick), 4 to 8 words, ends with ! (or a blaming question like 'मेरी गेंद कौन ले गया?'). "
        "NEVER open with a greeting, a polite question or a request ('...डालूँ क्या?', '...है क्या?').\n"
        "- The LAST line is the punchline and ends with ! or ?. The whole story has at most 34 spoken words (the reel is 25 seconds including a 7 second end card). Every line is at most 9 words.\n"
        "- The `card:` line is the 3 to 5 word on-screen hook shown in the first 1.5 seconds: Hindi only, at most 30 characters, no emoji, no digits, it teases the conflict.\n"
        "- The `hook:` line is the caption text: Hindi, at most 60 characters, exactly ONE emoji, no digits, not a line from the dialogue.\n"
        "- The `ending:` is 2 to 5 Hindi words, a different idea from the punchline.\n"
        "- Give the story a real TWIST: the last scene must flip what the viewer expected. Add ONE real Meerut touch (a place or thing people from Meerut know) in the plot or a line.\n"
        "- Put the field lines in this order: plot, ending, hook, card" + (", series, ep" if fmt == "series" else "") + ", then the four scene rows.\n"
    )
    fmt_text = FORMAT_HELP[fmt].format(ep=ep)
    series_lines = (f"Also write the lines `series: Bruno Files` and `ep: {ep}` right after `card:`.\n" if fmt == "series" else "")
    trend_part = ""
    try:   # DASHX Autonomy trend of the day (autonomy/trends.json): optional, empty on any problem, no Gemini call
        sys.path.insert(0, str(ROOT.parent / "autonomy"))
        import trend_feed  # noqa: PLC0415
        trend_part = trend_feed.prompt_text(ROOT.parent)
    except Exception:
        trend_part = ""
    user = (
        f"Format for this story: {fmt_text}\n{series_lines}"
        f"Situation: {seed['situation']}.\n"
        f"Characters to use (all of these; the first ones are required by the format): " + "; ".join(f"{c} ({cast_help(c)})" for c in cast) + ".\n"
        f"Hook style for the `hook:` line: {hook['name']} - pattern {hook['pattern']} (example: {hook['example']}). Make a NEW hook for THIS story, do not copy the example.\n\n"
        "Here are two finished stories in the right format (do NOT copy them, write a different story; the real new format also has a `card:` line):\n\n" + examples() + "\n\n"
        + trend_part +
        "Titles already used (do not repeat these ideas): " + "; ".join(titles) + "\n"
        "Endings already used (do not repeat): " + "; ".join(endings) + "\n\n"
        "Now write the new story block, starting with '## '."
    )
    return [{"role": "system", "content": sysmsg}, {"role": "user", "content": user}]


def extract_block(text: str) -> str | None:
    text = re.sub(r"```[a-z]*", "", text)
    i = text.find("## ")
    if i < 0:
        return None
    block = text[i:].strip()
    block = re.split(r"\n## ", block)[0]
    lines = [ln.rstrip() for ln in block.splitlines() if ln.strip()]
    keep = [ln for ln in lines if ln.startswith(("## ", "plot:", "ending:", "hook:", "card:", "series:", "ep:", "- "))]
    if not keep or not keep[0].startswith("## ") or "|" not in keep[0]:
        return None
    return "\n".join(keep)


def title_of(blk: str) -> str:
    return blk.splitlines()[0][3:].split("|")[0].strip()


def first_spoken_line(blk: str) -> str:
    for ln in blk.splitlines():
        if ln.startswith("- "):
            return ln.split("|", 4)[-1].split("//")[0].split(":", 1)[-1].strip()
    return ""


def hook_log(blk: str) -> str:
    """The Hindi hook score of a candidate, as text for the log. Log only: it never rejects a story and never calls a model."""
    import story_rules  # noqa: PLC0415
    return story_rules.hook_score_text(first_spoken_line(blk))


def judge(block: str) -> tuple[bool, dict]:
    msg = ("You are a strict editor of kids' Hindi comedy reels. Grade this story. Reply with ONLY a JSON object: "
           '{"funny":1-10,"clear":1-10,"natural_hindi":1-10,"meerut_feel":1-10,"twist":1-10,"plot_matches":1-10,"complete_alone":1-10,'
           '"kid_safe":true|false,"typos":["misspelled Hindi words, empty list if none"],"issue":"one short sentence"}. '
           "funny = does the punchline really land; clear = a kid understands what happens; natural_hindi = the sentences are correct, "
           "everyday Hindi, no broken grammar or odd words; meerut_feel = does it feel like real Meerut gully life (places, things, talk), not a generic story; "
           "twist = does the last scene flip what the viewer expected; plot_matches = the `plot:` line says exactly what the spoken lines show "
           "(same characters, same events); complete_alone = a new viewer understands and enjoys it without any other episode; "
           "kid_safe = nothing unsuitable or unfair to anyone; typos = every misspelled Hindi word you can see.\n\n" + block)
    code, txt = ask([{"role": "user", "content": msg}], 0.0, 1500)
    m = re.search(r"\{.*\}", txt or "", re.S)
    if code != 200 or not m:
        return False, {"issue": f"judge unavailable (HTTP {code})"}
    try:
        j = json.loads(m.group(0))
        need = {"funny": MIN_JUDGE, "clear": MIN_JUDGE, "natural_hindi": MIN_JUDGE, "meerut_feel": MIN_MEERUT, "twist": MIN_TWIST, "plot_matches": MIN_JUDGE}
        if "\nseries:" in block:
            need["complete_alone"] = MIN_JUDGE
        ok = j.get("kid_safe") is True and not j.get("typos") and all(int(j.get(k, 0)) >= v for k, v in need.items())
        return ok, j
    except Exception:
        return False, {"issue": "judge answer not understood"}


def check_block(blk: str, prior: list[str]) -> tuple[list[str], str]:
    """Run the hand-written-story checker on (existing bank + stories accepted earlier in this run + this candidate). (problems, last template). No Gemini call."""
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "combined.md"
        out = Path(d) / "result.json"
        f.write_text(BANK.read_text(encoding="utf-8").rstrip() + "\n\n" + "\n\n".join(prior + [blk]) + "\n", encoding="utf-8")
        subprocess.run([sys.executable, str(ROOT / "scripts" / "check_dialogue_bank.py"), str(f), "--json", str(out)],
                       cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
        res = json.loads(out.read_text(encoding="utf-8")) if out.exists() else []
    if not res:
        return ["checker gave no result"], ""
    return res[-1]["problems"], res[-1]["last_template"]


FIXABLE_NOT = ("too close", "repeats", "same word", "nearly the same", "similarity", "capped", "checker gave no result")


def write_report(left: int, added: int, a, extra: str = "") -> None:
    line = f"Story refill {quota_day()}: {left} stories left in the bank, {added} added today, Gemini calls used {CALLS['n']}/{CALLS['cap']}{extra}"
    print(line)
    if not a.dry_run:
        DAILY.write_text(line + "\n", encoding="utf-8", newline="\n")
    summ = os.environ.get("GITHUB_STEP_SUMMARY")
    if summ:
        try:
            with open(summ, "a", encoding="utf-8") as f:
                f.write("### Story refill\n" + line + "\n")
        except Exception:
            pass


def steer_format(default: str) -> str:
    """DASHX Autonomy learning loop: more of the formats that work, 20 percent experiments. Any problem or no data = the normal cycle."""
    try:
        sys.path.insert(0, str(ROOT.parent / "autonomy"))
        import steer  # noqa: PLC0415
        return steer.pick("format", list(FORMATS), default, ROOT.parent)
    except Exception:
        return default


def steer_formula(cfg: list):
    """Same for the hook style. Any problem or no data = a random formula, exactly as before."""
    try:
        sys.path.insert(0, str(ROOT.parent / "autonomy"))
        import steer  # noqa: PLC0415
        return steer.pick_formula(cfg, ROOT.parent)
    except Exception:
        return random.choice(cfg)


def run(a) -> int:
    t0 = time.time()
    CALLS["cap"] = a.max_calls
    CALLS["n"] = load_usage()
    left, total = usable_count()
    print(f"bank: {total} stories, {left} usable now; Gemini calls used today so far: {CALLS['n']} of {CALLS['cap']}")
    if left > a.max_bank:
        write_report(left, 0, a, f" (bank has more than {a.max_bank} usable stories: nothing to write)")
        return 0
    if not KEY:
        print("::warning::GEMINI_API_KEY is not set: no story written (the existing bank is still used)")
        write_report(left, 0, a, " (no key)")
        return 0
    if calls_left() < 2:
        print("::warning::the Gemini call limit for today is already used: no story written")
        write_report(left, 0, a, " (daily limit reached)")
        return 0
    STATE["models"] = gemini_models()
    if a.probe:
        save_usage()
        return 0
    cfg = json.loads((ROOT / "stories" / "viral_formats.json").read_text(encoding="utf-8"))["formulas"]
    situations = json.loads((ROOT / "stories" / "situations.json").read_text(encoding="utf-8"))
    sits = list(situations["situations"])
    random.shuffle(sits)
    fmt_offset = random.randrange(len(FORMATS))
    bank_text = BANK.read_text(encoding="utf-8")
    existing = re.findall(r"^## (.+?) \|", bank_text, re.M)
    ep_next = next_episode(bank_text)
    endings = re.findall(r"^ending: (.+)$", bank_text, re.M)
    accepted: list[tuple[str, dict]] = []
    tried = 0
    stop_msg = ""
    while len(accepted) < a.target:
        if STATE["quota_hit"]:
            stop_msg = " (Gemini quota answer: stopped for the day)"
            break
        if calls_left() < 2:
            stop_msg = " (call limit reached)"
            break
        if time.time() - t0 > BUDGET_S:
            stop_msg = " (time budget used up)"
            break
        fmt = FORMATS[(tried + fmt_offset) % len(FORMATS)]
        fmt = steer_format(fmt)
        pool_ = {"rivalry": situations.get("rivalry"), "shop": situations.get("shop")}.get(fmt) or sits
        anchor = random.choice(situations.get("meerut_anchors") or [""])
        seed = {"situation": random.choice(pool_) + (f" (Meerut touch to use: {anchor})" if anchor else ""), "formula": steer_formula(cfg)}
        tried += 1
        code, txt = ask(prompt_for(seed, existing[-40:] + [title_of(b) for b, _ in accepted], endings[-40:], fmt, ep_next))
        if code != 200:
            print(f"  writer HTTP {code}: {clean(txt)}")
            stop_msg = f" (Gemini answered HTTP {code}: stopped)"
            break
        blk = extract_block(txt)
        if not blk:
            print("  unusable answer:", clean(txt, 200), "| raw:", clean(STATE["last_raw"], 200))
            continue
        prior = [b for b, _ in accepted]
        probs, last = check_block(blk, prior)
        print(f"  . {clean(title_of(blk), 60)}: {hook_log(blk)}")
        if probs and not any(k in " ".join(probs) for k in FIXABLE_NOT) and calls_left() >= 3:
            print(f"  ~ {clean(title_of(blk), 60)}: fixable problems, one repair try: {clean('; '.join(probs), 160)}")
            sys_msg = ("You fix ONE kids' Hindi cartoon story so it passes a checker. Keep the idea and the jokes, change only what the problems say. "
                       "Follow the file format exactly. Output only the corrected story block starting with '## ', nothing else.\n\n" + bank_header())
            user_msg = blk + "\n\nProblems found by the checker:\n- " + "\n- ".join(probs[:6]) + "\n\nWrite the corrected story block."
            code, txt = ask([{"role": "system", "content": sys_msg}, {"role": "user", "content": user_msg}], 0.4)
            fixed = extract_block(txt) if code == 200 else None
            if not fixed:
                continue
            blk = fixed
            probs, last = check_block(blk, prior)
        if probs:
            print(f"  x {clean(title_of(blk), 60)}: {clean('; '.join(probs))}")
            continue
        if last == "catch" and sum(1 for b, _ in accepted if b.splitlines()[-1].startswith("- catch")) + 1 > max(1, (len(accepted) + 1) // 5):
            print(f"  x {clean(title_of(blk), 60)}: too many stories ending in a catch scene")
            continue
        ok, j = judge(blk)
        if not ok:
            print(f"  x {clean(title_of(blk), 60)}: editor says {clean(json.dumps(j, ensure_ascii=False))}")
            continue
        print(f"  + {clean(title_of(blk), 60)}: accepted {clean(json.dumps(j, ensure_ascii=False), 120)}")
        accepted.append((blk, j))
    model = STATE["models"][STATE["idx"]]
    print(f"accepted {len(accepted)} new stories (target {a.target}){stop_msg}")
    if accepted:
        if a.dry_run:
            print("--- accepted stories, in full, for review ---")
            for b, j in accepted:
                print("  ---")
                for ln in b.splitlines():
                    print("  |", clean(ln, 300))
                print("  | editor:", clean(json.dumps(j, ensure_ascii=False), 200))
            DRY.write_text("\n\n".join(b for b, _ in accepted) + "\n", encoding="utf-8", newline="\n")
        else:
            stamp = f"\n<!-- auto-written {date.today().isoformat()} by gemini/{model}; passed the same checks as hand-written stories + editor grade >= {MIN_JUDGE} -->\n\n"
            with BANK.open("a", encoding="utf-8", newline="\n") as f:
                f.write(stamp + "\n\n".join(b for b, _ in accepted) + "\n")
            with LOG.open("a", encoding="utf-8", newline="\n") as f:
                for b, j in accepted:
                    f.write(f"- {date.today().isoformat()} | gemini/{model} | {b.splitlines()[0][3:]} | {json.dumps(j, ensure_ascii=False)} | {hook_log(b)}\n")
    save_usage()
    left2 = usable_count()[0] if accepted and not a.dry_run else left
    write_report(left2, 0 if a.dry_run else len(accepted), a, stop_msg + (" [dry run: nothing saved]" if a.dry_run else ""))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=int, default=2, help="stop as soon as this many stories are accepted (the factory uses 2 reels a day)")
    ap.add_argument("--max-calls", type=int, default=12, help="hard cap of Gemini calls per quota day")
    ap.add_argument("--max-bank", type=int, default=60, help="write nothing when more than this many usable stories are left")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--seed", type=int, default=None)
    a = ap.parse_args()
    if a.seed is not None:
        random.seed(a.seed)
    try:
        return run(a)
    except Exception as e:  # never turn a job red because of the story maker
        print(f"::warning::story refill stopped by an error: {clean(type(e).__name__ + ': ' + str(e), 200)}")
        try:
            save_usage()
        except Exception:
            pass
        return 0


if __name__ == "__main__":
    sys.exit(main())
