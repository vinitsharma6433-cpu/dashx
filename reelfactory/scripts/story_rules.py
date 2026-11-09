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
SPEAKERS = {"sachin", "surya", "dadaji", "aunty", "pintu", "golu", "meena", "coach", "bruno"}
SPEAKER_HI = {"sachin": "सचिन", "surya": "सूर्या", "dadaji": "दादाजी", "aunty": "आंटी", "pintu": "पिंटू", "golu": "गोलू", "meena": "मीना", "coach": "कोच", "bruno": "ब्रूनो"}
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
