"""Steers the story mix with what the learning loop found (autonomy/learning.json). Standard library only. Never raises.

  - 80 percent of the time: pick more of what works (weights from the average score of each value, neutral until a value has enough reels)
  - 20 percent of the time: an EXPERIMENT = the least-tried option, so new hook styles and formats keep being explored
  - no learning file, steering OFF (fewer than 5 reels with data), a dimension not on the list, or any error: the caller's own default,
    so the machine behaves exactly as before

It makes no model call and changes no file. Used by reelfactory/scripts/refill_bank.py (format and hook style of a new story).
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
ROOT = Path(__file__).resolve().parent.parent


def load(root: Path | None = None) -> dict:
    try:
        return json.loads(((root or ROOT) / "autonomy" / "learning.json").read_text(encoding="utf-8"))
    except Exception:
        return {}


def weight(dim: str, option: str, data: dict) -> float:
    g = data.get("groups", {}).get(dim, {}).get(option)
    if not g or g.get("avg") is None:
        return 1.0                                   # not enough reels yet: neutral
    return max(0.25, float(g["avg"]) / 50.0)         # score 50 = normal; a weak option still keeps a quarter chance


def pick(dim: str, options: list[str], default, root: Path | None = None, rng=None, data: dict | None = None):
    """One of `options` (a value may repeat in the list: that keeps the old mix), or `default` when there is nothing to steer with."""
    try:
        data = data if data is not None else load(root)
        st = data.get("steer", {})
        if not options or not st.get("active") or dim not in st.get("dimensions", []):
            return default
        rng = rng or random
        if rng.random() < float(st.get("explore_share", 0.2)):
            n = lambda o: (data.get("groups", {}).get(dim, {}).get(o) or {}).get("n", 0)      # noqa: E731
            least = min(n(o) for o in options)
            return rng.choice([o for o in options if n(o) == least])
        w = [weight(dim, o, data) for o in options]
        return rng.choices(options, weights=w, k=1)[0]
    except Exception:
        return default


def pick_formula(formulas: list[dict], root: Path | None = None, rng=None):
    """A hook formula whose style (question / number / exclaim / statement) is chosen by `pick`; a random one when nothing to steer with."""
    rng = rng or random
    try:
        import learning  # noqa: PLC0415
        by_type: dict[str, list[dict]] = {}
        for f in formulas:
            by_type.setdefault(learning.hook_type(f.get("example", "")), []).append(f)
        t = pick("hook_type", sorted(by_type), None, root, rng)
        if t and by_type.get(t):
            return rng.choice(by_type[t])
    except Exception:
        pass
    return rng.choice(formulas)
