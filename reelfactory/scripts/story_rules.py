"""DASHX content rules for generated stories (checked in code, not left to the LLM).

Rules: no price, no "best / no.1 / premium / guaranteed", no fake claims, no other brands,
no real people, no sensitive news. Spoken lines are Hindi only (Devanagari), so no brand name can
slip into a story line; the DASHX brand line is added by the adapter, never written by the LLM.
"""

from __future__ import annotations

import re

# Plain-text substrings / words that must never appear in a spoken line or a title.
_BAD_EN = re.compile(
    r"(price|rupee|rs\.?\s*\d|\bmrp\b|cheap|discount|offer|\bsale\b|\bbest\b|no\.?\s*1\b|number\s*one|premium|"
    r"guarante|100\s*%|\bfree\b|nike|adidas|puma|\bmrf\b|\bss\b|\bsg\b|kookaburra|cosco|nivia|decathlon|"
    r"\bipl\b|bcci|\bicc\b|dhoni|kohli|tendulkar|rohit)",
    re.I,
)
_BAD_HI = re.compile(
    "(कीमत|दाम|रुपये|रुपए|रुपया|रूपये|₹|सस्ता|सस्ती|छूट|ऑफर|ऑफ़र|सेल|बेस्ट|सबसे अच्छ|सबसे बढ़िया|नंबर वन|नम्बर वन|"
    "प्रीमियम|गारंटी|गारण्टी|मुफ़्त|मुफ्त|धोनी|कोहली|तेंदुलकर|रोहित|आईपीएल|बीसीसीआई|नाइके|अडिडास|एमआरएफ|कूकाबूरा)"
)
# Sensitive topics (deaths, war, crime, elections, religion, accidents ...): never used for jokes or promotion.
_SENSITIVE_EN = re.compile(
    r"\b(die[sd]?|dead|death|kill\w*|murder\w*|war|bomb\w*|rape|suicide|terror\w*|election|vote|politic\w*|"
    r"religio\w*|riot\w*|accident|funeral|hospital|police|arrest\w*)\b",
    re.I,
)
_SENSITIVE_HI = re.compile(
    "(मौत|मर गय|मरा |हत्या|खून|युद्ध|जंग|बम|आतंक|चुनाव|वोट|राजनीत|दंगा|दंगे|धर्म|मंदिर|मस्जिद|हिंदू|मुस्लिम|"
    "सरकार|नेता|अस्पताल|दुर्घटना|एक्सीडेंट|श्मशान|पुलिस|गिरफ्तार|पाकिस्तान|चीन)"
)

_JUNK = re.compile(r"[“”\"‘’'`<>{}\[\]]")
# the three characters must always be spelled the same way: सचिन, सूर्या, दादाजी
_BAD_NAMES = re.compile("सूरज|सूर्य(?!ा)|सचीन|दादा जी|सुर्या")

_DEVANAGARI = re.compile(r"[ऀ-ॿ]")
_LATIN = re.compile(r"[A-Za-z]")
_DIGIT = re.compile(r"[0-9०-९]")


def rule_problems(text: str) -> list[str]:
    """DASHX rule violations in one piece of text (empty list = fine)."""
    out: list[str] = []
    if _BAD_EN.search(text) or _BAD_HI.search(text):
        out.append("contains a price / superlative / guarantee / other-brand / real-person word")
    if _SENSITIVE_EN.search(text) or _SENSITIVE_HI.search(text):
        out.append("touches a sensitive topic")
    if _DIGIT.search(text):
        out.append("contains digits (numbers invite price or stat claims)")
    return out


def hindi_problems(text: str, min_words: int = 2, max_words: int = 9) -> list[str]:
    """A spoken line must be Devanagari Hindi only, short, and clean."""
    out = rule_problems(text)
    if _JUNK.search(text):
        out.append("contains quote or bracket characters (leftover JSON junk)")
    if _BAD_NAMES.search(text):
        out.append("misspells a character name (use सचिन, सूर्या, दादाजी)")
    if _LATIN.search(text):
        out.append("contains Latin letters (spoken lines must be pure Devanagari)")
    letters = _DEVANAGARI.findall(text)
    if len(letters) < 4:
        out.append("is not Hindi (Devanagari)")
    words = len(text.split())
    if not (min_words <= words <= max_words):
        out.append(f"has {words} words (want {min_words}-{max_words})")
    return out


def similar(a: str, b: str) -> float:
    from difflib import SequenceMatcher

    norm = lambda t: re.sub(r"\s+", " ", re.sub(r"[^\w\s]", "", t.lower())).strip()
    return SequenceMatcher(None, norm(a), norm(b)).ratio()


# ---- dialogue format (every spoken line belongs to a character who says it in the first person) -----------------
SPEAKERS = {"sachin", "surya", "dadaji", "aunty", "pintu", "golu", "meena", "coach", "bruno", "pappu", "chhotu", "mintu"}
SPEAKER_HI = {"sachin": "सचिन", "surya": "सूर्या", "dadaji": "दादाजी", "aunty": "आंटी", "pintu": "पिंटू", "golu": "गोलू", "meena": "मीना", "coach": "कोच", "bruno": "ब्रूनो", "pappu": "पप्पू", "chhotu": "छोटू", "mintu": "मिंटू"}
MAX_DIALOGUE_WORDS = 14
# A dialogue line is what the character SAYS. Narration tags like "X बोला" are not allowed in it.
_NARRATION = re.compile(r"(बोला|बोली|बोले|बोलीं|ने कहा|ने पूछा|कहा था|चिल्लाया|चिल्लाई|चिल्लाए|फुसफुसाया|पूछा)")


def dialogue_problems(line: str, speaker: str | None) -> list[str]:
    """Problems of one dialogue line (empty list = fine). `speaker` must be a cast name."""
    out: list[str] = []
    if not speaker or speaker not in SPEAKERS:
        out.append("has no valid speaker")
    out += hindi_problems(line, 1, MAX_DIALOGUE_WORDS)
    if _NARRATION.search(line):
        out.append("contains a narration tag (बोला / बोली / ने कहा ...): write what the character says")
    if speaker in SPEAKER_HI and re.search(rf"{SPEAKER_HI[speaker]} (ने|को|का|की|के) ", line + " "):
        out.append("talks about its own speaker in the third person")
    return out


# ---- story-upgrade checks: apply ONLY to stories in the new format (they carry a `card:` field); older bank stories are never judged by them ----
# 1. cold open: the first spoken line is the conflict or the payoff, never a polite question or a greeting
_POLITE = re.compile(r"(कृपया|प्लीज़|प्लीज|क्या मैं|क्या आप|क्या हम|डालूँ क्या|दूँ क्या|करूँ क्या|चलूँ क्या|चलें क्या|सकता हूँ|सकती हूँ|शुरू करें|नमस्ते|ज़रा सुनिए|आपको .*क्या\?$)")
_BLAME = re.compile(r"(किसने|किसकी|किसका|कहाँ|क्यों|कैसे|ये क्या|यह क्या|वो क्या|कौन)")


def cold_open_problems(first_line: str) -> list[str]:
    line = " ".join(first_line.split())
    if _POLITE.search(line):
        return ["cold open: the first line is a polite question or greeting; open with the conflict or the payoff"]
    if line.endswith("?") and not _BLAME.search(line):
        return ["cold open: the first line is a plain question; open with a claim, a loss or a boast that ends in !"]
    return []


# 2. plot vs dialogue: the people the plot names must be in the story, and a character who talks a lot must be in the plot
_PLOT_KEYS = {"sachin": ["sachin"], "surya": ["surya"], "dadaji": ["dadaji", "grandfather"], "aunty": ["aunty"], "pintu": ["pintu"],
              "golu": ["golu"], "meena": ["meena"], "coach": ["coach"], "bruno": ["bruno", "the dog"], "pappu": ["pappu"],
              "chhotu": ["chhotu"], "mintu": ["mintu"]}


def plot_dialogue_problems(plot_en: str, scenes: list[dict]) -> list[str]:
    plot = plot_en.lower()
    named = {c for c, keys in _PLOT_KEYS.items() if any(re.search(rf"\b{re.escape(k)}\b", plot) for k in keys)}
    spoken: dict[str, int] = {}
    on_stage: set[str] = set()
    text = ""
    for sc in scenes:
        for v in sc.get("params", {}).values():
            on_stage |= {x for x in (v if isinstance(v, list) else [v]) if x in SPEAKERS}
        for d in sc.get("dialogue", []):
            spoken[d["speaker"]] = spoken.get(d["speaker"], 0) + 1
            text += " " + d["line"]
    out = []
    for c in sorted(named):
        if c not in on_stage and SPEAKER_HI.get(c, "~") not in text:
            out.append(f"plot names {c} but {c} is not in the story")
    for c, n in sorted(spoken.items()):
        if n >= 2 and c not in named:
            out.append(f"plot/lines disagree: {c} speaks {n} times but the plot never mentions {c}")
    return out


# 3. Hindi typos. No Hindi dictionary can be used (tested and rejected, see factory/spell.py), so this is a list of known wrong spellings
#    of words our stories use, plus pattern checks. The second-model grade also lists misspelled words (same call, no extra call).
TYPO_MAP = {"फ़ीलडर": "फ़ील्डर", "फीलडर": "फील्डर", "फिल्डर": "फील्डर", "फील्डिग": "फील्डिंग", "फ़ील्डिग": "फ़ील्डिंग", "बैटिग": "बैटिंग",
            "बालिंग": "बॉलिंग", "बोलिंग": "बॉलिंग", "क्रिकट": "क्रिकेट", "क्रीकेट": "क्रिकेट", "अम्पायर": "अंपायर", "कैपटन": "कैप्टन",
            "छक्का": "छक्का", "चौक्का": "चौका", "चौकका": "चौका", "दुकान्दार": "दुकानदार",
            "बल्ले बाज": "बल्लेबाज़", "पतन्ग": "पतंग", "गैंद": "गेंद", "गेद": "गेंद", "छोटु": "छोटू", "पप्पु": "पप्पू", "मिन्टू": "मिंटू"}
_TOKEN = re.compile(r"[ऀ-ॿ]+")


def typo_problems(text: str) -> list[str]:
    out = []
    toks = _TOKEN.findall(text)
    for t in toks:
        fix = TYPO_MAP.get(t)
        if fix and fix != t:
            out.append(f"spelling: {t} -> {fix}")
    for a, b in zip(toks, toks[1:]):
        if a == b and len(a) > 2 and a not in ("भौं", "हाहा", "नहीं"):   # barks and "नहीं नहीं" are legitimate repeats
            out.append(f"the same word twice in a row: {a}")
    return out


# 4. on-screen hook card (new `card:` field): 3 to 5 Hindi words, short, no digits, no emoji (the card font has none)
def card_problems(card: str) -> list[str]:
    c = " ".join(card.split())
    words = c.split()
    out = []
    if not 3 <= len(words) <= 5:
        out.append(f"card: needs 3 to 5 words, has {len(words)}")
    if len(c) > 30:
        out.append(f"card: {len(c)} characters, at most 30")
    if re.search(r"[A-Za-z0-9०-९]", c):
        out.append("card: Hindi words only (no Latin letters or digits)")
    if re.search(r"[\U0001F000-\U0001FFFF\u2600-\u27BF]", c):
        out.append("card: no emoji on the card")
    return out


# 5. series fields: `series:` and `ep:` go together; a series story ends on the question that tomorrow answers (last spoken line ends with ?)
def series_problems(series: str, ep: str, last_line: str) -> list[str]:
    if not series and not ep:
        return []
    out = []
    if not series or not ep:
        out.append("series: `series:` and `ep:` must both be set")
    elif not re.fullmatch(r"[1-9][0-9]?", ep.strip()):
        out.append("series: ep must be a number from 1 to 99")
    if not last_line.rstrip().endswith("?"):
        out.append("series: the last spoken line must end with ? (it plants the next episode's question)")
    return out
