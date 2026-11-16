"""DASHX Autonomy: the weekly "NotebookLM pack" (autonomy/notebooklm_pack.md), written by the Pattern Engine. Standard library only.

NotebookLM has no API, so the machine only PREPARES a study pack; the owner pastes it into NotebookLM by hand.
  (a) our own top 5 and bottom 5 reels (our own repo slugs only) with links, views and reactions per day and their genome tags,
      the performance numbers come from autonomy/learning.json (links come from the poster's own results)
  (b) public Shorts of the niche that look like hits: links, views and dates ONLY, and only when the engine had a YouTube Data API key
  (c) deep study questions: general ones and one per weak genome part
Zero-leak: no outside title, quote, comment or channel name ever goes into this file. Written only via the engine (guarded path).
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import genome
import guard
import pattern_advisor as adv

NETS = ("youtube", "instagram", "facebook")
QUESTIONS = [
    "Hook: what exactly happens in the first line or frame of each top reel, and what is different in the bottom reels?",
    "First 3 seconds: what does the viewer see and hear before any setup? Which of our tags (first_3s) fits best?",
    "Length and pacing: where would you cut 2 seconds? Is the pacing (cuts_fast, cuts_medium, slow_build) right for the story?",
    "Emotion: which single feeling does each top reel aim for (nostalgia, laughter, suspense, pride, wholesome_chaos)?",
    "Structure: how does the last scene flip or pay off the first? Compare twist_ending with escalating_chaos and underdog_win.",
    "Ending: does the ending make a viewer watch again (seamless_audio_loop) or wait for part 2 (cliffhanger_part2)?",
    "Shareable: why would a kid or a parent send this to a friend (tag_a_friend, childhood_memory, unexpected_twist, cute_bruno_moment)?",
    "Compared with our bottom 5: which single change would you try first, and which tag would you test next week?",
]


def links_for(posts: list[dict]) -> dict[str, dict]:
    out = {}
    for p in posts:
        res = p.get("results") or {}
        out[str(p.get("title", "")).replace(" DASHX", "")] = {n: str((res.get(n) or {}).get("link", "")) for n in NETS}
    return out


def render(now: datetime, rows: list[dict], scores: list[float], hits, data: dict, links: dict, why_no_hits: str) -> str:
    tag = adv.week_tag(now.date())
    L = [f"# DASHX NotebookLM pack, week {tag}", f"<!-- week: {tag} -->", "",
         "How to use: open NotebookLM, make a notebook, paste this whole page as a source, add the reel links as sources, then ask the study questions.",
         "Written by the machine once a week. Our own numbers only; public reels are links and numbers only (no titles, no channel names, no text).", ""]
    ranked = sorted(zip(rows, scores), key=lambda x: -x[1])

    def line(r, s):
        tg = ", ".join(f"{f}={v}" for f, v in r["tags"].items()) or "no tags yet"
        lk = "; ".join(f"{n}: {u}" for n, u in (links.get(r["slug"]) or {}).items() if u) or "no link"
        return f"- {r['slug']} (score {s}, views/day {round(r['views_per_day'], 1)}, reactions/day {round(r['reactions_per_day'], 2)}; tags: {tg}) {lk}"
    L.append("## (a) Our top 5 reels (score = views and reactions per day)")
    L += [line(r, s) for r, s in ranked[:5]] or ["- no reel with data yet"]
    L += ["", "## (a) Our bottom 5 reels"]
    L += [line(r, s) for r, s in ranked[-5:][::-1]] if len(ranked) > 5 else ["- fewer than 6 reels with data: see the top list"]
    L += ["", f"Score mode this week: {data.get('score_mode')}. Tagged reels: {data.get('tagged_reels')} of {data.get('reels_with_data')}.", "",
          "## (b) Public Shorts in our niche that look like hits"]
    if hits is None:
        L.append(f"- Left empty: {why_no_hits}")
    else:
        L += [f"- {h['link']} ({h['views']} views, published {h['published']})" for h in hits] or ["- nothing found this week"]
    L += ["", "## (c) Study questions (ask NotebookLM for each reel)"] + [f"{i}. {q}" for i, q in enumerate(QUESTIONS, 1)]
    bp = data.get("blueprint") or {}
    if bp.get("experiments"):
        L += ["", "## This week's experiments to discuss", *[f"- {e['key']}: {e['why']}" for e in bp["experiments"]]]
    return "\n".join(L) + "\n"


def write_pack(root: Path, now: datetime, rows: list[dict], scores: list[float], hits, data: dict, why_no_hits: str = "") -> None:
    import pattern_engine as eng  # noqa: PLC0415
    try:
        posts = json.loads((root / "poster/queue.json").read_text(encoding="utf-8")).get("posts", [])
    except Exception:
        posts = []
    eng.write_state(root, eng.OUT_PACK, render(now, rows, scores, hits, data, links_for(posts), why_no_hits))
