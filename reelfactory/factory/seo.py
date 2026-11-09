"""SEO Agent: YouTube Shorts title, Hindi description, hashtags, tags, keyword suggestions, a short CTA and an SEO
score (0-100). No fake engagement claims, no price, no superlatives: every text goes through the DASHX rules.
The buy block is copied from the dashx-reel-engine skill, links unchanged."""

from __future__ import annotations

import re

from .bridge import story_rules

BRAND = "DASHX by Nav Durga Sports, Meerut"
BUY_BLOCK = """Amazon: https://www.amazon.in/dp/B0H4QG8FKG
Flipkart: https://dl.flipkart.com/dl/product/p/itme?pid=BALHZ5DAYUNTZD82&lid=LSTBALHZ5DAYUNTZD82W6Z0R4
Meesho: https://meesho.com/dash-x-power-yellow/p/hetayl?_ms=1.3
Mystore: https://www.mystore.in/product/dash-x-extra-duty-cricket-tennis-balls-pack-of-3
Website: https://vinitsharma6433-cpu.github.io/dashx/"""
BUY_HEADER = "BUY LINKS"
CTA = "मज़ा आया? कमेंट में अपना पसंदीदा सीन बताओ!"
IG_BRAND_LINE = "DASHX ball - Meerut se."
LINKS_IN_BIO = "Amazon, Flipkart, Meesho links: bio me"
# every post ends with exactly these hashtags, in this order
HASHTAGS = ["#DASHX", "#GullyCricket", "#CricketReels", "#Meerut"]
IG_HASHTAGS = YT_HASHTAGS = HASHTAGS
COMMENT_INTRO = "DASHX cricket tennis ball yahan se lo:"
HOOK_MAX = 60  # characters, including the one emoji
EMOJI = re.compile(r"[\U0001F300-\U0001FAFF\u2600-\u27BF]")
REMOVED_PHRASES = ("आख़िर में क्या हुआ? देखो", "मिस मत करना")  # the old template wording must never come back


def reel_hook(script: dict) -> str | None:
    """The hook written for THIS story: stored in script.json (story.hook), or, for a reel made before that field existed,
    the hook of the same story in stories/dialogue_bank.md. None when the story has none (there is no template fallback)."""
    h = (script.get("story") or {}).get("hook")
    if h:
        return h
    from .bridge import daily  # noqa: PLC0415
    for b in daily.parse_dialogue_bank():
        if b["title_hi"] == script.get("title") and b.get("hook"):
            return b["hook"]
    return None


_STOP = {"का", "की", "के", "में", "पर", "से", "को", "ने", "है", "हैं", "तो", "या", "कि", "और", "क्या", "कौन", "कैसे", "क्यों", "कहाँ", "अब", "भी", "ही", "एक", "थी", "था", "गया", "गई", "हुआ", "हो"}


def hooks_clash(a: str, b: str) -> bool:
    """True when two hooks have (nearly) the same wording: they share half of their content words, or read almost the same."""
    from difflib import SequenceMatcher  # noqa: PLC0415
    clean = lambda t: re.sub(r"\s+", " ", re.sub(r"[^\w\s]", "", EMOJI.sub("", t))).strip()
    ta, tb = clean(a), clean(b)
    wa, wb = {w for w in ta.split() if w not in _STOP}, {w for w in tb.split() if w not in _STOP}
    jacc = len(wa & wb) / len(wa | wb) if wa and wb else 0.0
    return jacc >= 0.5 or SequenceMatcher(None, ta, tb).ratio() >= 0.75


def hook_problems(hook: str | None, script: dict | None = None) -> list[str]:
    """Every rule for a hook: one Hindi line, at most 60 characters, exactly one emoji, DASHX word rules, not a dialogue line,
    does not give away the ending, none of the removed template phrases."""
    from .story import similarity  # noqa: PLC0415
    if not hook:
        return ["no reel-specific hook (add a `hook:` line to the story)"]
    out = []
    if len(hook) > HOOK_MAX:
        out.append(f"hook is {len(hook)} characters (max {HOOK_MAX})")
    n = len(EMOJI.findall(hook))
    if n != 1:
        out.append(f"hook has {n} emoji (needs exactly 1)")
    if len(re.findall(r"[ऀ-ॿ]", hook)) < 8:
        out.append("hook is not Hindi")
    if "\n" in hook:
        out.append("hook must be one line")
    out += story_rules.rule_problems(hook)
    if any(ph in hook for ph in REMOVED_PHRASES):
        out.append("hook uses a removed template phrase")
    if script:
        lines = [d["line"] for sc in script["scenes"] for d in sc.get("dialogue", [])]
        text = EMOJI.sub("", hook).strip()
        if any(similarity(text, ln) >= 0.7 for ln in lines):
            out.append("hook repeats a dialogue line")
        closing = (script.get("story") or {}).get("closing", "")
        from difflib import SequenceMatcher  # noqa: PLC0415
        punch = lines[-1] if lines else ""
        if (closing and SequenceMatcher(None, text, closing).ratio() >= 0.75) or (punch and hooks_clash(text, punch)):
            out.append("hook gives away the ending")
    return out


def instagram_caption(hook: str) -> str:
    """line 1 hook, line 2 blank, line 3 brand line, then the five hashtags, and the closing line for the link in the bio."""
    return f"{hook}\n\n{IG_BRAND_LINE}\n{LINKS_IN_BIO}\n\n{' '.join(HASHTAGS)}"  # hashtags last (Instagram and Facebook)


def youtube_caption(hook: str) -> str:
    """The same hook, the brand line and the buy links block (the poster's format), then the hashtags."""
    return f"{hook}\n\n{BRAND}.\n\n{BUY_HEADER}\n{BUY_BLOCK}\n\n{' '.join(HASHTAGS)}"  # hashtags last


def first_comment() -> str:
    """The first comment under the YouTube video: the same links. (The API cannot pin it: pin it by hand in YouTube Studio.)"""
    return f"{COMMENT_INTRO}\n{BUY_BLOCK}"
BASE_KEYWORDS = ["gali cricket", "tennis ball cricket", "cricket comedy", "hindi cartoon", "cricket shorts", "DASHX", "Meerut"]
CAST_NAMES = {"sachin": "Sachin", "surya": "Surya", "dadaji": "Dadaji", "aunty": "Aunty", "pintu": "Pintu", "golu": "Golu", "meena": "Meena", "coach": "Coach", "bruno": "Bruno"}


def generate(script: dict, categories: list[str], cast: list[str]) -> dict:
    title_hi = script["title"]
    lines = [s["voice"] for s in script["scenes"][:-1]]
    closing = script.get("story", {}).get("closing", "")
    title = f"{title_hi} | गली क्रिकेट | DASHX"
    if len(title) > 60:
        title = f"{title_hi} | DASHX"
    hashtags = list(YT_HASHTAGS)
    desc = youtube_caption(reel_hook(script) or title_hi)  # the reel's own hook (or just its title), never dialogue lines
    names = [CAST_NAMES[c] for c in cast if c in CAST_NAMES]
    tags = list(dict.fromkeys(BASE_KEYWORDS + [n.lower() + " cricket cartoon" for n in names] + [c.lower() for c in categories] + ["hindi comedy", "kids cricket", "tennis ball", "cartoon shorts"]))
    kept, total = [], 0
    for t in tags:
        if total + len(t) + 1 <= 450:  # YouTube tag budget is 500 characters
            kept.append(t)
            total += len(t) + 1
    meta = {"title": title, "description": desc, "hashtags": hashtags, "tags": kept,
            "keyword_suggestions": [f"{n.lower()} gali cricket" for n in names[:4]] + ["गली क्रिकेट कार्टून", "हिंदी क्रिकेट कॉमेडी", "tennis ball cricket shorts"],
            "cta": CTA, "made_with_ai": True}
    meta["seo_score"], meta["seo_notes"] = score(meta)
    return meta


def score(meta: dict) -> tuple[float, list[str]]:
    notes: list[str] = []
    pts = 0
    t, d = meta["title"], meta["description"]
    if 20 <= len(t) <= 60:
        pts += 15
    else:
        notes.append(f"title length {len(t)} (want 20-60)")
    if "DASHX" in t:
        pts += 10
    else:
        notes.append("title has no brand")
    if len(re.findall(r"[ऀ-ॿ]+", d)) >= 3:
        pts += 15
    else:
        notes.append("the hook has too little Hindi")
    tags = meta["hashtags"]
    if tags == HASHTAGS and d.rstrip().endswith(" ".join(HASHTAGS)):
        pts += 15
    else:
        notes.append("hashtags: the description must end with " + " ".join(HASHTAGS))
    if len(meta["tags"]) >= 10:
        pts += 15
    else:
        notes.append("fewer than 10 tags")
    if any(k.split()[0].lower() in d.lower() or k in d for k in ("गली क्रिकेट", "gali cricket")):
        pts += 10
    else:
        notes.append("main keyword missing from the description")
    if "amazon.in" in d and "flipkart" in d.lower():
        pts += 10  # the call to action is the buy links block
    else:
        notes.append("no buy links in the description")
    bad = story_rules.rule_problems(t + " " + meta["cta"] + " " + re.sub(r"https?://\S+", "", d))
    if not bad:
        pts += 10
    else:
        notes.append("rule violation: " + "; ".join(bad))
    return float(pts), notes
