"""Auto story maker: keeps stories/dialogue_bank.md from ever running dry.

    python scripts/refill_bank.py                  # if fewer than --min-usable stories are left, write --make new ones
    python scripts/refill_bank.py --force --make 6 # always write
    python scripts/refill_bank.py --dry-run        # write nothing, only print (candidates go to stories/refill_dry_run.md)
    python scripts/refill_bank.py --probe          # only test which free models answer (no story is made)

How it works (every story must pass ALL of these, nothing is lowered):
  1. a free model (GitHub Models with the built-in GITHUB_TOKEN; optionally Gemini free key or Hugging Face) writes ONE story in the bank format, from a random gully-cricket situation
     (stories/situations.json) and a hook formula (stories/viral_formats.json, idea credit: rediumvex/viral-hooks-skill, MIT)
  2. the same checker as for hand-written stories (scripts/check_dialogue_bank.py: format, DASHX rules, roles, hook, score >= 80,
     no repeated line / ending / hook against the whole bank and every reel made)
  3. a second model call that grades funny / clear / natural Hindi / kid-safe (all must be >= 7)
  Only then the story is appended to the bank. Nothing is ever deleted or rewritten. No token is ever printed.
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
from datetime import date
from pathlib import Path

import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BANK = ROOT / "stories" / "dialogue_bank.md"
LOG = ROOT / "stories" / "refill_log.md"
DRY = ROOT / "stories" / "refill_dry_run.md"
# (name, chat-completions URL, token, models). The first provider+model that answers is used for the whole run.
PROVIDERS = [
    ("github-models", "https://models.github.ai/inference/chat/completions", os.environ.get("GITHUB_TOKEN", "").strip(),
     ["openai/gpt-4.1", "openai/gpt-4o", "meta/Llama-3.3-70B-Instruct", "openai/gpt-4.1-mini"]),
    ("gemini", "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions", os.environ.get("GEMINI_API_KEY", "").strip(),
     ["gemini-2.5-flash", "gemini-2.0-flash"]),
    ("huggingface", "https://router.huggingface.co/v1/chat/completions", os.environ.get("HF_TOKEN", "").strip(),
     ["Qwen/Qwen2.5-72B-Instruct", "meta-llama/Llama-3.3-70B-Instruct"]),
]
SECRETS = [p[2] for p in PROVIDERS if p[2]]
ACTIVE: dict = {}
MIN_JUDGE = 7
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
}


def scrub(s) -> str:
    s = str(s)
    for t in SECRETS:
        s = s.replace(t, "<token>")
    return s


def chat(model: str, messages: list[dict], temperature: float = 0.9, max_tokens: int = 1100) -> tuple[int, str]:
    """(http status, text). The text is the model's answer or a scrubbed error message."""
    body = json.dumps({"model": model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens}).encode("utf-8")
    req = urllib.request.Request(ACTIVE["url"], data=body, headers={"Authorization": "Bearer " + ACTIVE["token"], "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            raw = r.read().decode("utf-8", "replace")
            try:
                return r.status, json.loads(raw)["choices"][0]["message"]["content"] or ""
            except Exception:
                ACTIVE["last_raw"] = scrub(raw)[:400]
                return r.status, ""
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            msg = json.loads(raw).get("error", raw)
            msg = msg.get("message", msg) if isinstance(msg, dict) else msg
        except Exception:
            msg = raw
        return e.code, scrub(msg)[:240]
    except Exception as e:  # network problem
        return 0, scrub(e)[:200]


def pick_model() -> str | None:
    """Probe the providers in order; set ACTIVE and return the model name of the first one that answers."""
    for name, url, tok, models in PROVIDERS:
        if not tok:
            print(f"provider {name}: no key, skipped")
            continue
        ACTIVE.update(url=url, token=tok)
        for m in models:
            code, txt = chat(m, [{"role": "user", "content": "Say OK."}], 0, 8)
            print(f"provider {name} model {m}: HTTP {code}" + ("" if code == 200 else f" - {txt[:120]}"))
            if code == 200:
                ACTIVE["name"] = name
                return m
            if code in (401, 402, 403, 429):
                break  # this provider refuses (key, credits or rate limit): next provider
    print("::warning::no free model answered (GitHub Models, Gemini, Hugging Face); the existing bank is still used")
    return None


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
        data = {"title_hi": b["title_hi"], "title_en": b["title_en"], "plot_en": b["plot_en"], "scenes": b["rows"], "closing_hi": b["closing"], "hook": b.get("hook", "")}
        st, probs = daily.from_dialogue_data(data, i, {})
        if st:
            probs += daily.story_problems(st, hist, [], [])
        if st and not probs and sm.score_story(st, ref=ref)["score"] >= 70:
            left += 1
    return left, len(stories)


def prompt_for(seed: dict, titles: list[str], endings: list[str]) -> list[dict]:
    cast = random.sample(["sachin", "surya", "dadaji", "aunty", "pintu", "golu", "meena", "coach", "bruno"], 4)
    if "sachin" not in cast and "surya" not in cast:
        cast[0] = random.choice(["sachin", "surya"])
    hook = seed["formula"]
    sysmsg = (
        "You write ONE short funny cartoon story for kids, as a 25-second Hindi reel about gully cricket in Meerut, India. "
        "You follow the file format below EXACTLY. Output only the story block, nothing else, no code fence, no explanation.\n\n"
        + bank_header()
        + "\n\nExtra hard rules:\n"
        "- Write all spoken lines, the ending, the hook and the Hindi title in natural everyday Hindi (Devanagari), the way kids in Meerut talk. Short, simple words.\n"
        "- English is allowed only in the title before the | and in the plot line. No digits anywhere in Hindi text.\n"
        "- Spell the names exactly: सचिन, सूर्या, दादाजी, आंटी, पिंटू, गोलू, मीना, कोच, ब्रूनो.\n"
        "- Use at least 3 different templates among the 4 scenes. A story must NOT end in a catch scene unless the joke needs it.\n"
        "- Never mention price, discounts, 'best', brands, politics, religion, accidents, hospitals or police.\n"
        "- Each scene has 1 or 2 lines. With 2 lines the two speakers differ. The speaker of every line must be on stage in that scene.\n"
        "- The FIRST spoken line is a 4 to 8 word hook that ends with ! or ?. The LAST line is the punchline and ends with ! or ?.\n"
        "- The whole story has at most 40 spoken words. Every line is at most 10 words.\n"
        "- The `hook:` line is the title card text: Hindi, at most 60 characters, exactly ONE emoji, no digits, not a line from the dialogue.\n"
        "- The `ending:` is 2 to 5 Hindi words, a different idea from the punchline.\n"
    )
    user = (
        f"Situation for this story: {seed['situation']}.\n"
        f"Characters to use (at least 3 of these): " + "; ".join(f"{c} ({CAST_HELP[c]})" for c in cast) + ".\n"
        f"Hook style for the `hook:` line: {hook['name']} - pattern {hook['pattern']} (example: {hook['example']}). Make a NEW hook for THIS story, do not copy the example.\n\n"
        "Here are two finished stories in the right format (do NOT copy them, write a different story):\n\n" + examples() + "\n\n"
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
    keep = [ln for ln in lines if ln.startswith(("## ", "plot:", "ending:", "hook:", "- "))]
    if not keep or not keep[0].startswith("## ") or "|" not in keep[0]:
        return None
    return "\n".join(keep)


def judge(model: str, block: str) -> tuple[bool, dict]:
    msg = ("You are a strict editor of kids' Hindi comedy reels. Grade this story. Reply with ONLY a JSON object: "
           '{"funny":1-10,"clear":1-10,"natural_hindi":1-10,"kid_safe":true|false,"issue":"one short sentence"}. '
           "funny = does the punchline really land; clear = a kid understands what happens; natural_hindi = the sentences are correct, "
           "everyday Hindi, no broken grammar or odd words; kid_safe = nothing unsuitable or unfair to anyone.\n\n" + block)
    code, txt = chat(model, [{"role": "user", "content": msg}], 0.0, 200)
    m = re.search(r"\{.*\}", txt or "", re.S)
    if code != 200 or not m:
        return False, {"issue": f"judge unavailable (HTTP {code})"}
    try:
        j = json.loads(m.group(0))
        ok = j.get("kid_safe") is True and all(int(j.get(k, 0)) >= MIN_JUDGE for k in ("funny", "clear", "natural_hindi"))
        return ok, j
    except Exception:
        return False, {"issue": "judge answer not understood"}


def check_blocks(blocks: list[str]) -> dict[str, list[str]]:
    """Run the hand-written-story checker on (existing bank + the candidates). Returns {english title: problems} for the candidates."""
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "combined.md"
        out = Path(d) / "result.json"
        f.write_text(BANK.read_text(encoding="utf-8").rstrip() + "\n\n" + "\n\n".join(blocks) + "\n", encoding="utf-8")
        subprocess.run([sys.executable, str(ROOT / "scripts" / "check_dialogue_bank.py"), str(f), "--json", str(out)],
                       cwd=ROOT, capture_output=True, text=True, timeout=900)
        res = json.loads(out.read_text(encoding="utf-8")) if out.exists() else []
    n_old = len(res) - len(blocks)
    return {r["title"]: r["problems"] for r in res[n_old:]} | {"__last__": {r["title"]: r["last_template"] for r in res[n_old:]}}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-usable", type=int, default=14, help="write new stories when fewer than this many are left")
    ap.add_argument("--make", type=int, default=10, help="how many new stories to aim for")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--seed", type=int, default=None)
    a = ap.parse_args()
    if a.seed is not None:
        random.seed(a.seed)
    if a.probe:
        return 0 if pick_model() else 1
    left, total = usable_count()
    print(f"bank: {total} stories, {left} usable now")
    if left >= a.min_usable and not a.force:
        print(f"enough stories (>= {a.min_usable}): nothing to do")
        return 0
    model = pick_model()
    if not model:
        print(f"::warning::story maker could not start; {left} usable stories remain in the bank")
        return 0
    cfg = json.loads((ROOT / "stories" / "viral_formats.json").read_text(encoding="utf-8"))["formulas"]
    sits = json.loads((ROOT / "stories" / "situations.json").read_text(encoding="utf-8"))["situations"]
    random.shuffle(sits)
    existing = re.findall(r"^## (.+?) \|", BANK.read_text(encoding="utf-8"), re.M)
    endings = re.findall(r"^ending: (.+)$", BANK.read_text(encoding="utf-8"), re.M)
    accepted: list[tuple[str, dict]] = []
    tried = 0
    for rnd in range(3):  # up to 3 rounds
        want = a.make - len(accepted)
        if want <= 0:
            break
        cands: list[str] = []
        for _ in range(want + 3):
            seed = {"situation": sits[tried % len(sits)], "formula": random.choice(cfg)}
            tried += 1
            code, txt = chat(model, prompt_for(seed, existing[-40:] + [b.split("\n")[0][3:].split("|")[0].strip() for b, _ in accepted], endings[-40:]))
            if code != 200:
                print(f"  writer HTTP {code}: {txt}")
                if code in (401, 402, 403, 429):
                    print('  provider refuses further calls (credits / rate limit): stopping the writer')
                    break
                continue
            blk = extract_block(txt)
            if blk:
                cands.append(blk)
            else:
                print("  unusable answer (first 400 chars):", txt[:400].replace(chr(10), " / "), "| raw:", ACTIVE.get("last_raw", "")[:400].replace(chr(10), " / "))
        print(f"round {rnd + 1}: {len(cands)} candidate(s)")
        if not cands:
            break
        res = check_blocks(cands)
        last = res.pop("__last__", {})
        for blk in cands:
            title = blk.split("\n")[0][3:].split("|")[0].strip()
            probs = res.get(title)
            if probs is None:
                print(f"  - {title}: not found in checker output, skipped")
                continue
            if probs:
                print(f"  x {title}: {'; '.join(probs)[:200]}")
                continue
            if last.get(title) == "catch" and sum(1 for b, _ in accepted if b.splitlines()[-1].startswith("- catch")) + 1 > max(1, (len(accepted) + 1) // 5):
                print(f"  x {title}: too many stories ending in a catch scene")
                continue
            ok, j = judge(model, blk)
            if not ok:
                print(f"  x {title}: editor says {json.dumps(j, ensure_ascii=False)[:200]}")
                continue
            print(f"  + {title}: accepted {json.dumps(j, ensure_ascii=False)[:120]}")
            accepted.append((blk, j))
    print(f"accepted {len(accepted)} new stories")
    if accepted:
        stamp = f"\n<!-- auto-written {date.today().isoformat()} by {ACTIVE.get('name')}/{model}; passed the same checks as hand-written stories + editor grade >= {MIN_JUDGE} -->\n\n"
        text = stamp + "\n\n".join(b for b, _ in accepted) + "\n"
        if a.dry_run:
            DRY.write_text(text, encoding="utf-8")
            print("dry run: candidates saved to", DRY)
        else:
            with BANK.open("a", encoding="utf-8", newline="\n") as f:
                f.write(text)
            with LOG.open("a", encoding="utf-8", newline="\n") as f:
                for b, j in accepted:
                    f.write(f"- {date.today().isoformat()} | {ACTIVE.get('name')}/{model} | {b.splitlines()[0][3:]} | {json.dumps(j, ensure_ascii=False)}\n")
    left2, total2 = usable_count() if accepted and not a.dry_run else (left, total)
    print(f"bank now: {total2} stories, {left2} usable")
    if left2 < a.min_usable and not a.dry_run:
        print(f"::warning::only {left2} usable stories left in the bank after the refill")
    return 0


if __name__ == "__main__":
    sys.exit(main())
