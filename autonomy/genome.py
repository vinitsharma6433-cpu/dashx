"""DASHX story genome: seven tags with FIXED ASCII-slug values. Standard library only, pure functions.

Every value that the pattern pipeline stores or compares comes from these lists, so no title, quote, comment or channel name
can ever be stored. Tags of OUR stories are set when a story is written (by our own story generator, see scripts/refill_bank.py)
and are kept in the story bank as one line:   tags: hook_type=curiosity_gap; emotion=laughter; ...
Old stories get ONLY the tags that follow with certainty from the bank entry itself (backfill_certain); the rest stays empty.
"""
from __future__ import annotations

import re

ENUMS = {
    "hook_type": ("curiosity_gap", "visual_shock", "relatable_pain", "challenge", "absurdity"),
    "first_3s": ("fast_action", "character_closeup", "bold_text_question", "sound_effect_drop"),
    "emotion": ("nostalgia", "laughter", "suspense", "pride", "wholesome_chaos"),
    "structure": ("twist_ending", "escalating_chaos", "loop_back_to_start", "underdog_win"),
    "pacing_bucket": ("cuts_fast", "cuts_medium", "slow_build"),
    "ending_loop": ("seamless_audio_loop", "cliffhanger_part2", "punchline_freeze"),
    "shareable_because": ("tag_a_friend", "childhood_memory", "unexpected_twist", "cute_bruno_moment"),
}
FIELDS = tuple(ENUMS)
SLUG = re.compile(r"^[a-z0-9_]+$")

# Our own mapping from the hook formula the generator picked (stories/viral_formats.json) to the hook_type tag.
FORMULA_TO_HOOK = {
    "curiosity gap": "curiosity_gap", "wait for it": "curiosity_gap", "secret": "curiosity_gap",
    "unexpected result": "visual_shock",
    "who is right": "challenge", "guess": "challenge",
    "nobody talks about": "relatable_pain",
    "it went wrong": "absurdity",
}

_TAGS_LINE = re.compile(r"^tags:[ \t]*(.*)$", re.M)


def validate(tags) -> dict:
    """Keep only known fields with allowed values (a value from any other source is dropped)."""
    out = {}
    if isinstance(tags, dict):
        for f, allowed in ENUMS.items():
            v = tags.get(f)
            if isinstance(v, str) and v in allowed:
                out[f] = v
    return out


def parse_tags(text: str) -> dict:
    """The tags of a bank block (or any text with a 'tags:' line). Unknown fields and values are ignored."""
    m = _TAGS_LINE.search(text or "")
    if not m:
        return {}
    raw = {}
    for part in m.group(1).split(";"):
        k, _, v = part.partition("=")
        raw[k.strip().lower()] = v.strip().lower()
    return validate(raw)


def format_tags(tags: dict) -> str:
    t = validate(tags)
    return "tags: " + "; ".join(f"{f}={t[f]}" for f in FIELDS if f in t) if t else ""


def set_tags(block: str, tags: dict) -> str:
    """Put exactly one canonical tags line into a bank block (after the last field line before the scene rows)."""
    line = format_tags(tags)
    body = [ln for ln in block.rstrip("\n").split("\n") if not ln.strip().startswith("tags:")]
    if not line:
        return "\n".join(body) + "\n"
    at = next((i for i, ln in enumerate(body) if ln.startswith("- ")), len(body))
    return "\n".join(body[:at] + [line] + body[at:]) + "\n"


def finalize_new_story(block: str, formula_name: str = "") -> str:
    """For a story our generator just wrote: keep the tags the writer gave only if every value is an allowed one,
    and set hook_type from the formula WE chose (never from the story text)."""
    tags = parse_tags(block)
    if formula_name in FORMULA_TO_HOOK:
        tags["hook_type"] = FORMULA_TO_HOOK[formula_name]
    return set_tags(block, tags)


def _scene_cast(block: str) -> list[set]:
    out = []
    for ln in block.splitlines():
        if ln.startswith("- ") and ln.count("|") == 4:
            _t, a, b, _board, _text = [c.strip() for c in ln[2:].split("|")]
            out.append({a, b})
    return out


def backfill_certain(block: str) -> dict:
    """Tags that follow with CERTAINTY from the bank entry itself. Everything else is left empty.
      first_3s = bold_text_question  when the on-screen card (shown in the first 1.5 s) ends with a question mark
      shareable_because = cute_bruno_moment  when the English title starts with 'Bruno' and Bruno is on stage in at least 2 scenes
    """
    tags = {}
    card = re.search(r"^card:[ \t]*(.*)$", block, re.M)
    if card and card.group(1).strip().endswith("?"):
        tags["first_3s"] = "bold_text_question"
    title = block.splitlines()[0][3:].split("|")[0].strip() if block.startswith("## ") else ""
    if title.lower().startswith("bruno") and sum(1 for c in _scene_cast(block) if "bruno" in c) >= 2:
        tags["shareable_because"] = "cute_bruno_moment"
    return tags


def backfill_bank(text: str) -> tuple[str, int]:
    """Add certain tags to every story that has no tags line yet. Returns (new text, how many stories were tagged)."""
    parts = re.split(r"\n(?=## )", text)
    n = 0
    for i, blk in enumerate(parts):
        if not blk.startswith("## ") or _TAGS_LINE.search(blk):
            continue
        t = backfill_certain(blk)
        if t:
            parts[i] = set_tags(blk, t).rstrip("\n") + blk[len(blk.rstrip("\n")):]      # keep the blank line(s) between stories
            n += 1
    return "\n".join(parts), n


def tags_prompt_line() -> str:
    """The instruction for the story writer: label ITS OWN story with allowed values only."""
    return ("- Add ONE line `tags:` right after the other field lines (before the four scene rows) that labels THIS story: "
            + "; ".join(f"{f}={'|'.join(v)}" for f, v in ENUMS.items() if f != "hook_type")
            + ". Use exactly one allowed value for each field, no other words.\n")
