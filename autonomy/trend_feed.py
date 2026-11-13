"""Feeds 1-2 fitting, safe trend topics (autonomy/trends.json) into the story writer prompt. Standard library only. Never raises.

Used by reelfactory/scripts/refill_bank.py prompt_for(). No trends file, an expired topic, a broken rule file or any error gives "" and the
prompt stays exactly as before. It makes NO Gemini call: the text is only added to the existing writer prompt.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

try:
    import guard
    import trends as _trends
except Exception:           # imported from another folder: add this folder to the path
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import guard
    import trends as _trends


def pick(topics: list[dict], today: date, rules: dict) -> list[dict]:
    """Up to `feed_per_day` topics that are not expired and still pass the brand rules. Same day = same choice; ties rotate by day."""
    n = rules["trends"]["feed_per_day"]
    ok = [t for t in topics if str(t.get("expires", "")) >= today.isoformat()
          and _trends.brand_ok(" ".join(str(t.get(k, "")) for k in ("topic", "why_fits", "story_angle")), rules)]
    if not ok:
        return []
    ok.sort(key=lambda t: (-float(t.get("strength", 0)), (hash_day(t["id"]) + today.toordinal()) % 7, t["id"]))
    return ok[:n]


def hash_day(s: str) -> int:
    return sum(ord(c) for c in s)


def prompt_text(root: Path | None = None, today: date | None = None) -> str:
    try:
        root = root or guard.ROOT
        today = today or date.today()
        rules = guard.load_rules()
        data = json.loads((root / "autonomy" / "trends.json").read_text(encoding="utf-8"))
        topics = pick(data.get("topics", []), today, rules)
        if not topics:
            return ""
        lines = "\n".join(f"- {t['topic']}: {t['story_angle']}" for t in topics)
        return ("TREND OF THE DAY (an optional mood; use at most ONE, only if it fits the situation naturally; "
                "a gully-cricket story comes first; no real news, people, teams or brands):\n" + lines + "\n\n")
    except Exception:
        return ""
