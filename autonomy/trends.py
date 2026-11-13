"""DASHX Autonomy, Phase 3: trend radar. Standard library only, FREE public sources only (see RULES.json `trends`).

How it stays safe: it NEVER copies a headline. It reads public RSS (Google Trends India, Google News searches), throws away every
headline that contains a blocked word (politics, religion, tragedy, crime), and then only COUNTS how many safe headlines hit one of
our own pre-written themes (autonomy/trend_themes.json). The output (autonomy/trends.json) holds our own safe angle for the theme,
not the news. Festivals come from the calendar file autonomy/festivals.json. Every angle is checked again against the brand rules.

No login, no scraping of accounts, no Instagram, no cookies. A source that fails is skipped; with no source at all the evergreen
themes still give a safe result. It writes only autonomy/trends.json and autonomy/log.md (state files). Kill switches win.
"""
from __future__ import annotations

import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import guard  # noqa: E402

ROOT = guard.ROOT
IST = guard.IST
OUT = "autonomy/trends.json"
LOG = "autonomy/log.md"
UA = "DASHX-autonomy/1.0 (public RSS reader)"


# ---------------------------------------------------------------- rules: word lists
def _word_re(words: list[str]) -> re.Pattern:
    parts = []
    for w in words:
        w = w.lower()
        exact = w.endswith(" ")
        w = re.escape(w.strip())
        parts.append(r"\b" + w + (r"\b" if exact else r"\w*"))
    return re.compile("|".join(parts), re.I) if parts else re.compile(r"(?!x)x")


def blocked_re(rules: dict) -> re.Pattern:
    return _word_re([w for group in rules["trends"]["blocked_words"].values() for w in group])


def brand_re(rules: dict) -> re.Pattern:
    return _word_re(rules["trends"]["brand_words"])


def is_safe_headline(text: str, rules: dict) -> bool:
    """False when the headline has a blocked word (politics, religion, tragedy, crime) or a brand/price word."""
    return not (blocked_re(rules).search(text or "") or brand_re(rules).search(text or ""))


def brand_ok(text: str, rules: dict) -> bool:
    return not brand_re(rules).search(text or "")


# ---------------------------------------------------------------- fetch (public RSS, no login)
def fetch(url: str, rules: dict) -> bytes:
    if not url.startswith("https://"):
        raise ValueError("only https sources")
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/rss+xml, application/xml, text/xml"})
    with urllib.request.urlopen(req, timeout=rules["trends"]["timeout_seconds"]) as r:
        data = r.read(rules["trends"]["max_bytes"] + 1)
    if len(data) > rules["trends"]["max_bytes"]:
        raise ValueError("feed too large")
    return data


def headlines(xml_bytes: bytes) -> list[str]:
    """Titles of the RSS items. Titles are used only for counting, never stored."""
    root = ET.fromstring(xml_bytes)
    return [t.text.strip() for t in root.iter("title") if t.text and t.text.strip()][1:]   # [0] is the feed's own title


# ---------------------------------------------------------------- themes + festivals
def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def theme_hits(titles: list[str], themes: list[dict]) -> dict[str, int]:
    out = {}
    for t in themes:
        rx = _word_re(t["keywords"])
        out[t["id"]] = sum(1 for h in titles if rx.search(h))
    return out


def festival_topics(today: date, cal: dict) -> list[dict]:
    out = []
    for d in cal["days"]:
        day = date.fromisoformat(d["date"])
        if day - timedelta(days=cal["lead_days"]) <= today <= day + timedelta(days=cal["after_days"]):
            out.append({"id": d["id"], "topic": d["label"], "why_fits": d["why"], "story_angle": d["angle"], "story_situation": d.get("situation", ""),
                        "strength": 10 - abs((day - today).days), "sources": ["festival calendar"] + (["date approximate: owner to confirm"] if d.get("check") else []),
                        "expires": (day + timedelta(days=cal["after_days"])).isoformat()})
    return out


def build(today: date, fetched: dict[str, list[str]], rules: dict, themes: dict, cal: dict, failed: list[str] | None = None) -> dict:
    """The trends.json content. `fetched` = source id -> raw titles. Pure function: easy to test."""
    seen = dropped = 0
    safe: dict[str, list[str]] = {}
    for sid, titles in fetched.items():
        keep = []
        for h in titles:
            seen += 1
            if is_safe_headline(h, rules):
                keep.append(h)
            else:
                dropped += 1
        safe[sid] = keep
    topics: list[dict] = []
    days = rules["trends"]["default_expiry_days"]
    for th in themes["themes"]:
        rx = _word_re(th["keywords"])
        srcs = [sid for sid, hs in safe.items() if any(rx.search(h) for h in hs)]
        n = sum(1 for hs in safe.values() for h in hs if rx.search(h))
        if not n and not th.get("evergreen"):
            continue
        if not (brand_ok(th["angle"], rules) and brand_ok(th["label"], rules) and brand_ok(th["why"], rules)):
            continue                                   # a theme that breaks the brand rules is dropped, never used
        topics.append({"id": th["id"], "topic": th["label"], "why_fits": th["why"], "story_angle": th["angle"], "story_situation": th.get("situation", ""),
                       "strength": min(n, 5) + (0 if n else 0.5), "sources": srcs or ["evergreen"],
                       "expires": (today + timedelta(days=days)).isoformat()})
    for f in festival_topics(today, cal):
        if brand_ok(f["story_angle"], rules) and brand_ok(f["topic"], rules) and brand_ok(f["why_fits"], rules):
            topics.append(f)
    topics.sort(key=lambda t: (-t["strength"], t["id"]))
    return {"generated": datetime.now(IST).isoformat(timespec="minutes"), "day": today.isoformat(),
            "topics": topics[: rules["trends"]["max_topics"]],
            "stats": {"headlines_seen": seen, "dropped_unsafe": dropped, "sources_ok": sorted(fetched), "sources_failed": sorted(failed or [])},
            "note": "Headlines are never stored or copied. Topics are our own safe themes, ranked by how many safe headlines matched."}


def fresh_enough(root: Path, now: datetime, rules: dict) -> bool:
    try:
        g = datetime.fromisoformat(json.loads((root / OUT).read_text(encoding="utf-8"))["generated"])
        return now - g < timedelta(hours=rules["trends"]["refresh_after_hours"])
    except Exception:
        return False


def write_trends(root: Path, data: dict) -> None:
    kind, _ = guard.classify(OUT, guard.load_rules())
    if kind != "state":                       # the machine may only write its own notes
        raise PermissionError(f"{OUT} is not a machine-notes file")
    p = root / OUT
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def run(root: Path = ROOT, now: datetime | None = None, force: bool = False, fetcher=fetch) -> dict | None:
    now = (now or datetime.now(IST)).astimezone(IST)
    if guard.halted("trends", root):
        print(f"{guard.halted('trends', root)} is on: trend radar does nothing")
        return None
    rules = guard.load_rules()                # raises RulesTampered: the machine stops
    if not force and fresh_enough(root, now, rules):
        print("trends.json is fresh, nothing to do")
        return None
    fetched, failed = {}, []
    for src in rules["trends"]["sources"]:
        try:
            fetched[src["id"]] = headlines(fetcher(src["url"], rules))
        except Exception as e:                # one source down is normal: skip it
            failed.append(src["id"])
            print(f"::warning::source {src['id']} skipped: {type(e).__name__}")
    data = build(now.date(), fetched, rules, load_json(root / "autonomy/trend_themes.json"), load_json(root / "autonomy/festivals.json"), failed)
    write_trends(root, data)
    lp = root / LOG
    lp.parent.mkdir(parents=True, exist_ok=True)
    with open(lp, "a", encoding="utf-8", newline="\n") as f:
        top = ", ".join(t["id"] for t in data["topics"][:3]) or "none"
        f.write(f"- {now.strftime('%Y-%m-%d %H:%M')} IST | info | trend_radar | top: {top}; seen {data['stats']['headlines_seen']}, dropped {data['stats']['dropped_unsafe']}, failed sources {len(failed)} | written\n")
    return data


if __name__ == "__main__":
    try:
        d = run(force="--force" in sys.argv)
    except guard.RulesTampered as e:
        print(f"::error::RULES TAMPERED ({e}). Trend radar stopped.")
        sys.exit(1)
    if d:
        for t in d["topics"]:
            print(f"{t['strength']:>4} {t['id']}: {t['topic']}")
