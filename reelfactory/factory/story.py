"""Story intelligence: categories, character personalities, originality (duplicate detection) and the
Story Quality Score (0-100). Plain Python on purpose: these are rules that must be repeatable, not guesses."""

from __future__ import annotations

import json
import re
from difflib import SequenceMatcher

from . import ROOT
from . import spell

# Personalities, kept the same in every episode. Used for casting hints and the character-fit check.
PROFILES = {
    "sachin": {"role": "main batter", "trait": "confident, loves big shots, a little sleepy"},
    "surya": {"role": "main bowler", "trait": "boastful, fast, funny when he loses"},
    "dadaji": {"role": "the calm elder", "trait": "sits on his chair and catches everything"},
    "aunty": {"role": "the neighbour", "trait": "warm, sharp-eyed, protects her window"},
    "pintu": {"role": "the umpire", "trait": "serious about rules, blows his whistle"},
    "golu": {"role": "the small fielder", "trait": "tiny, spots things first"},
    "meena": {"role": "the girl batter", "trait": "fearless, hits sixes"},
    "coach": {"role": "the coach uncle", "trait": "big, loud, laughs at the end"},
    "bruno": {"role": "the dog", "trait": "barks, chases the ball, never bats"},
}
MAIN_CAST = {"sachin", "surya", "dadaji"}

CATEGORY_WORDS = {
    "School Cricket": ["क्लास", "स्कूल", "कोच", "टीम"],
    "Family Comedy": ["दादाजी", "आंटी", "चाय", "कुर्सी", "आँगन", "खिड़की"],
    "Cricket Rivalry": ["चैलेंज", "आउट", "छक्का", "टॉस", "दिखा", "मुक़ाबला"],
    "Funny Characters": ["जादूगर", "जम्हाई", "भौंक", "आँखें बंद", "पतंग"],
    "Unexpected Endings": ["ग़ायब", "बिना देखे", "सोते", "वापस"],
}


def infer_categories(story: dict) -> list[str]:
    text = " ".join(s["line"] for s in story["scenes"]) + " " + story.get("closing", "")
    cats = ["Gali Cricket"]
    cast = cast_of(story)
    for cat, words in CATEGORY_WORDS.items():
        if any(w in text for w in words):
            cats.append(cat)
    if cast & {"bruno", "golu"} and "Funny Characters" not in cats:
        cats.append("Funny Characters")
    return cats


def cast_of(story: dict) -> set[str]:
    out: set[str] = set()
    for sc in story["scenes"]:
        for v in sc.get("params", {}).values():
            out |= {x for x in (v if isinstance(v, list) else [v]) if x in PROFILES}
    return out


# ---- similarity and the corpus of everything already made ------------------------------------------
def _norm(t: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", "", t.lower())).strip()


def _tri(t: str) -> set[str]:
    t = _norm(t)
    return {t[i:i + 3] for i in range(max(1, len(t) - 2))}


def similarity(a: str, b: str) -> float:
    """0..1: the larger of sequence similarity and character-trigram overlap (Jaccard)."""
    ta, tb = _tri(a), _tri(b)
    jac = len(ta & tb) / len(ta | tb) if ta and tb else 0.0
    return max(SequenceMatcher(None, _norm(a), _norm(b)).ratio(), jac)


def corpus() -> dict:
    """Plots, titles, endings and spoken lines of every reel script on disk."""
    plots, titles, endings, lines = [], [], [], []
    for f in (ROOT / "reels").glob("*/script.json"):
        try:
            j = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        plots.append(j.get("story", {}).get("plot", ""))
        titles.append(j.get("title", ""))
        endings.append(j.get("story", {}).get("closing", ""))
        lines += [s.get("voice", "") for s in j["scenes"][:-1]]
    return {"plots": [p for p in plots if p], "titles": titles, "endings": [e for e in endings if e], "lines": lines}


# ---- Hindi orthography sanity (malformed sequences), separate from the dictionary check ---------------
_BAD_SEQ = [
    (re.compile(r"(?:^|\s)[ा-ौँ-ः]"), "a vowel sign with no letter before it"),
    (re.compile(r"[ा-ौ]{2}"), "two vowel signs in a row"),
    (re.compile(r"्(?=\s|$|[!?।,])"), "a halant at the end of a word"),
    (re.compile(r"[ऀ-ॿ][A-Za-z]|[A-Za-z][ऀ-ॿ]"), "Hindi and English letters glued together"),
]


def orthography_problems(text: str) -> list[str]:
    return [why for rx, why in _BAD_SEQ if rx.search(text)]


# ---- Story Quality Score ------------------------------------------------------------------------------
WEIGHTS = {"hook": 20, "structure": 20, "language": 15, "punchline": 15, "originality": 15, "ending": 5, "characters": 10}


def score_story(story: dict, repaired_roles: int = 0, ref: dict | None = None) -> dict:
    """Returns {"score": 0-100, "parts": {...}, "notes": [...]}. Every part is a plain, inspectable rule."""
    ref = ref or corpus()
    lines = []
    for s in story["scenes"]:
        lines += [d["line"] for d in s.get("dialogue", [])] or [s["line"]]
    closing = story.get("closing", "")
    notes: list[str] = []
    parts: dict[str, float] = {}

    # hook: the first line must grab: 4-8 words, with ! or ?, or a dare
    first = lines[0]
    n = len(first.split())
    parts["hook"] = 20 if (4 <= n <= 8 and re.search(r"[!?]", first)) else 14 if 3 <= n <= 8 else 8
    if parts["hook"] < 20:
        notes.append("opening line is not a strong hook (4-8 words with ! or ?)")

    # structure: at least 3 different visuals, a pay-off scene (catch or a reaction face-off) last
    temps = [s["template"] for s in story["scenes"]]
    ok_last = temps[-1] in ("catch", "face-off", "shot")
    parts["structure"] = (10 if len(set(temps)) >= 3 else 4) + (10 if ok_last else 5) if len(temps) == 4 else 0
    if len(set(temps)) < 3:
        notes.append("fewer than 3 different visuals")

    # language: orthography is hard, dictionary is soft (names and loanwords are allowed)
    bad = [p for ln in lines + [closing] for p in orthography_problems(ln)]
    ratio = spell.unknown_ratio(" ".join(lines + [closing]))
    lang = 15 - 5 * len(bad)
    if ratio is not None:
        lang -= 0 if ratio <= 0.15 else 3 if ratio <= 0.3 else 8
    parts["language"] = max(0, lang)
    if bad:
        notes.append("spelling/orthography: " + "; ".join(sorted(set(bad))))
    if ratio is not None and ratio > 0.3:
        notes.append(f"{round(ratio * 100)}% of the words are not in the Hindi dictionary")

    # punchline: the ending is short, punchy, and not just a repeat of the last scene
    words = len(closing.split())
    punchy = 3 <= words <= 5 and re.search(r"[!?]$", closing) is not None
    parts["punchline"] = 15 if punchy and similarity(closing, lines[-1]) < 0.5 else 9 if closing else 0
    if parts["punchline"] < 15:
        notes.append("ending is weak or repeats the last scene")

    # originality: compare with every earlier plot, title and spoken line
    worst = max([similarity(story["plot_en"], p) for p in ref["plots"]] + [similarity(story["title_hi"], t) for t in ref["titles"]] + [0.0])
    dup_lines = sum(1 for ln in lines if any(similarity(ln, o) > 0.85 for o in ref["lines"]))
    parts["originality"] = max(0.0, 15 * (1 - max(0.0, worst - 0.35) / 0.65) - 4 * dup_lines)
    if worst > 0.8 or dup_lines:
        notes.append(f"too close to an earlier story (similarity {worst:.2f}, {dup_lines} repeated lines)")

    # ending variety
    near = max([similarity(closing, e) for e in ref["endings"]] + [0.0])
    parts["ending"] = 5 if near < 0.5 else 2 if near < 0.7 else 0
    if near >= 0.7:
        notes.append("ending is almost the same as an earlier ending")

    # characters: every character keeps its role (roles repaired by the builder cost points)
    parts["characters"] = max(0, 10 - 3 * repaired_roles) if cast_of(story) else 0

    # critical weaknesses cap the score, so a story cannot hide them behind points from other parts
    caps = []
    if worst >= 0.85 or dup_lines >= 2:
        caps.append((55, "duplicate of an earlier story"))
    if len(set(temps)) < 3:
        caps.append((60, "fewer than 3 different visuals"))
    if not (2 <= words <= 5):
        caps.append((65, "ending is not a 2-5 word punchline"))
    if parts["language"] < 8:
        caps.append((60, "language problems"))
    total = round(min([sum(parts.values())] + [c for c, _ in caps]), 1)
    notes += [f"score capped at {c}: {why}" for c, why in caps]
    return {"score": total, "parts": {k: round(v, 1) for k, v in parts.items()}, "notes": notes, "categories": infer_categories(story)}
