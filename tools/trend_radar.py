#!/usr/bin/env python3
"""DASHX Trend Radar (F1). Standard library only. Runs weekly (GitHub Action) and writes two data files:

  data/keywords.json     every keyword idea we know (keyword, language, source, intent, cluster, target_page, status,
                         first_seen, last_seen, trend_score)
  data/topic_queue.json  what to write or refresh next (max 5 new tasks per week)

Sources: Google autosuggest (free), data/seasonal_calendar.json (you edit it), Search Console queries (only if the secret
GSC_SA_JSON exists and a Google auth library is installed; otherwise skipped). Google Trends is NOT used until the owner approves
installing pytrends.

Keyword rule: only the balls DASHX sells. Bats, gloves, kits, coaching, wholesale, shop or city names, competitor brands and
price keywords are dropped. One search intent per page: a keyword that fits an existing page becomes an "update" task, never a new page.
Kill switch: if data/PAUSE_AUTOPILOT exists the run exits at once and changes nothing.

Env: DATA_DIR (default data), SITE (default https://dashx-store-api.onrender.com), TODAY (YYYY-MM-DD, for tests).
"""
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime

DATA = os.environ.get("DATA_DIR", "data")
SITE = os.environ.get("SITE", "https://dashx-store-api.onrender.com").rstrip("/")
UA = {"User-Agent": "DASHX-TrendRadar/1.0 (+https://dashx-store-api.onrender.com)"}
MAX_NEW_TASKS_PER_WEEK = 5
STALE_DAYS = 60
SUGGEST_URL = "https://suggestqueries.google.com/complete/search?client=firefox&hl={hl}&gl=in&q={q}"

SEEDS = [  # (seed, language of the suggest call)
    ("tennis ball cricket", "en"), ("cricket tennis ball", "en"), ("heavy tennis ball", "en"), ("light tennis ball", "en"),
    ("red tennis ball", "en"), ("green tennis ball", "en"), ("yellow tennis ball", "en"), ("tennis ball 90g", "en"),
    ("tennis ball 110g", "en"), ("tennis ball pack of 10", "en"), ("tennis ball for gully cricket", "en"),
    ("how to choose tennis ball for cricket", "en"),
    ("cricket tennis ball kaise chune", "hi"), ("क्रिकेट टेनिस बॉल", "hi"),
]
SUFFIXES = ["", " for", " weight"]   # a few expansions per seed; keeps the run short and polite

# ---------- the keyword rule ----------
OFF_TOPIC = re.compile(r"\b(bat|bats|batting|bowling|glove|gloves|kit|kits|pad|pads|helmet|shoes|jersey|stumps?|coaching|academy|federation|"
                       r"manufacturers?|wholesale|dealers?|shop|store|near me|price|prices|cost|rate|buy|cheap|cheapest|discount|offer|"
                       r"tutorial|bangalore|bengaluru|delhi|mumbai|chennai|kolkata|pune|hyderabad|jaipur|lucknow|ahmedabad|meerut|"
                       r"amazon|flipkart|meesho|snapdeal|myntra)\b", re.I)
COMPETITORS = re.compile(r"\b(kookaburra|gray[- ]?nicolls|gunn\s*(?:&|and)\s*moore|slazenger|dunlop|decathlon|cosco|nivia|nike|adidas|puma|wilson|ss|sg|mrf|sanspareils)\b", re.I)
HOW_TO_PLAY = re.compile(r"\bhow to (bowl|bat|hit|throw|play|spin|swing)\b|\btips?\b", re.I)   # "how to choose / care" stays allowed


def keyword_ok(kw):
    k = kw.lower().strip()
    if len(k) < 6 or len(k) > 80:
        return False
    if not ("ball" in k or "बॉल" in k or "गेंद" in k):
        return False
    return not (OFF_TOPIC.search(k) or COMPETITORS.search(k) or HOW_TO_PLAY.search(k))


def language_of(kw):
    if re.search(r"[\u0900-\u097F]", kw):
        return "hi"
    if re.search(r"\b(kaise|kaisa|kya|kaun|chune|chunna|wala|wali|liye|hai|sabse)\b", kw.lower()):
        return "hinglish"
    return "en"


def intent_of(kw):
    k = kw.lower()
    if re.search(r"\b(how|which|why|what|difference|vs|guide|choose|chune|kaise|care|size|weight|diameter|material)\b", k):
        return "informational"
    return "commercial-investigation"   # people comparing variants before they decide; buying keywords are dropped by the rule


# (cluster, regex, existing page slug or None = no page yet)
CLUSTERS = [
    ("pack-of-10", r"pack of 10|\b10 (balls|pack)|munna", "cricket-tennis-ball-pack-of-10-munna"),
    ("color-red", r"\bred\b|लाल", "red-tennis-ball-cricket-110g"),
    ("color-green", r"\bgreen\b|हरा", "green-tennis-ball-cricket-90g"),
    ("color-yellow", r"\byellow\b|पीला", "yellow-tennis-ball-cricket-90g"),
    ("heavy", r"\bheavy\b|भारी", "heavy-tennis-ball-cricket-90g-110g"),
    ("light", r"\blight\b|हल्का", "light-tennis-ball-cricket-90g"),
    ("material-size", r"material|size|diameter|felt|rubber|core|cm\b", "tennis-ball-cricket-material-weight-size"),
    ("weight-and-packs", r"weight|90 ?g|110 ?g|gram|pack of|dozen|variant", "cricket-tennis-ball-weights-packs-variants"),
    ("how-to-choose", r"choose|which|chune|chunna|kaise|pick|select", "cricket-with-tennis-ball-guide"),
    ("care", r"\bcare\b|maintain|clean|durab|last longer|store", None),
    ("dual-colour", r"dual|two colou?r|2 colou?r|bi[- ]?colou?r", None),
    ("match-practice", r"practice|match|tournament|gully|street|box cricket|school|club|holiday|diwali|season", None),
]
DEFAULT_CLUSTER = ("general", "cricket-with-tennis-ball-guide")


def cluster_of(kw, known_pages):
    """Returns (cluster, target_page, task_type). task_type is 'update' when a page for this intent exists, else 'new'."""
    k = kw.lower()
    for name, rx, slug in CLUSTERS:
        if re.search(rx, k):
            if slug and (known_pages is None or slug in known_pages):
                return name, "/blog/" + slug, "update"
            return name, "", "new"
    name, slug = DEFAULT_CLUSTER
    if known_pages is None or slug in known_pages:
        return name, "/blog/" + slug, "update"
    return name, "", "new"


# ---------- sources ----------
def http_get(url, timeout=20):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout).read()


def autosuggest(seed, hl, fetch=http_get):
    """Returns the suggestion list for one query (best first), or [] on any problem."""
    try:
        raw = fetch(SUGGEST_URL.format(hl=hl, q=urllib.parse.quote(seed)))
        j = json.loads(raw.decode("utf-8", "replace"))
        return [s for s in (j[1] if isinstance(j, list) and len(j) > 1 else []) if isinstance(s, str)]
    except Exception:
        return []


def collect_autosuggest(fetch=http_get, sleep=time.sleep, seeds=SEEDS, suffixes=SUFFIXES):
    """{keyword: score}. Rank 1 of 10 counts most; a keyword seen for several seeds adds up."""
    found, calls, failed = {}, 0, 0
    for seed, hl in seeds:
        for suf in suffixes:
            sugs = autosuggest(seed + suf, hl, fetch)
            calls += 1
            if not sugs:
                failed += 1
            for rank, s in enumerate(sugs[:10]):
                found[s.strip().lower()] = found.get(s.strip().lower(), 0.0) + (10 - rank) / 10.0
            sleep(1.0)
    return found, calls, failed


def seasonal_ideas(calendar, today):
    """Modifier keywords for events active this month or starting next month. Returns {keyword: (score, event_id)}."""
    out = {}
    nxt = today.month % 12 + 1
    for ev in calendar.get("events", []):
        months = ev.get("months", [])
        if today.month in months or nxt in months:
            boost = 2.0 if today.month in months else 1.2
            for m in ev.get("modifiers", []):
                out[m.lower()] = (boost, ev.get("id", ""))
    return out


def gsc_available():
    return bool(os.environ.get("GSC_SA_JSON"))


def gsc_rows_to_keywords(rows):
    """Search Console rows [{'keys': ['query'], 'impressions': n, ...}] -> {keyword: impressions}. (Parser only; the live fetch needs a
    Google auth library, so it stays skipped until the owner approves installing one.)"""
    out = {}
    for r in rows or []:
        keys = r.get("keys") or []
        if keys:
            out[keys[0].strip().lower()] = float(r.get("impressions", 0))
    return out


# ---------- merge into the data files ----------
def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def save_json(path, obj):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=1, ensure_ascii=False)
        f.write("\n")


def normalize_scores(raw):
    top = max(raw.values()) if raw else 0
    return {k: (round(100.0 * v / top) if top else 0) for k, v in raw.items()}


def merge_keywords(existing, scored, sources, today, known_pages):
    """existing: list of records. scored: {kw: score 0-100}. sources: {kw: source name}. Returns (records, n_new)."""
    by_kw = {r["keyword"]: r for r in existing}
    seen = set()
    n_new = 0
    for kw, score in scored.items():
        if not keyword_ok(kw):
            continue
        seen.add(kw)
        cluster, page, _ = cluster_of(kw, known_pages)
        rec = by_kw.get(kw)
        if rec is None:
            rec = {"keyword": kw, "language": language_of(kw), "source": sources.get(kw, "autosuggest"), "intent": intent_of(kw),
                   "cluster": cluster, "target_page": page, "status": "new", "first_seen": today.isoformat(), "last_seen": today.isoformat(),
                   "trend_score": score}
            by_kw[kw] = rec
            n_new += 1
        else:
            rec.update({"cluster": cluster, "target_page": page, "last_seen": today.isoformat(), "trend_score": score})
            if rec.get("status") == "stale":
                rec["status"] = "active"
            elif rec.get("status") == "new" and rec["first_seen"] != today.isoformat():
                rec["status"] = "active"
    for kw, rec in by_kw.items():
        if kw not in seen:
            age = (today - date.fromisoformat(rec["last_seen"])).days
            if age > STALE_DAYS:
                rec["status"] = "stale"
    return sorted(by_kw.values(), key=lambda r: (-r["trend_score"], r["keyword"])), n_new


def build_queue(records, queue, today, known_pages, cap=MAX_NEW_TASKS_PER_WEEK):
    """Adds at most `cap` tasks. One intent per page: a page or cluster already waiting in the queue gets no second task."""
    queue = [t for t in queue if t.get("status") == "queued"]          # finished or dropped tasks leave the file
    busy_pages = {t["target_page"] for t in queue if t.get("target_page")}
    busy_clusters = {t["cluster"] for t in queue if t.get("type") == "new"}
    added = []
    for rec in sorted(records, key=lambda r: -r["trend_score"]):
        if len(added) >= cap:
            break
        if rec["status"] not in ("new", "active") or rec["trend_score"] < 20:
            continue
        _, page, ttype = cluster_of(rec["keyword"], known_pages)
        if ttype == "update" and page in busy_pages:
            continue
        if ttype == "new" and rec["cluster"] in busy_clusters:
            continue
        task = {"id": "%s-%s" % (today.isoformat(), re.sub(r"[^a-z0-9]+", "-", rec["keyword"])[:50].strip("-")), "type": ttype,
                "keyword": rec["keyword"], "language": rec["language"], "intent": rec["intent"], "cluster": rec["cluster"],
                "target_page": page, "source": rec["source"], "trend_score": rec["trend_score"], "added": today.isoformat(), "status": "queued"}
        queue.append(task)
        added.append(task)
        rec["status"] = "queued"
        if page:
            busy_pages.add(page)
        elif ttype == "new":
            busy_clusters.add(rec["cluster"])
    return queue, added


def fetch_known_pages(fetch=http_get):
    """Blog slugs live in the store sitemap. None = could not read it (then every mapped page is assumed to exist)."""
    try:
        root = ET.fromstring(fetch(SITE + "/sitemap.xml"))
        ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        locs = [(u.findtext("s:loc", "", ns) or "") for u in root.findall("s:url", ns)]
        return {l.rsplit("/blog/", 1)[1] for l in locs if "/blog/" in l}
    except Exception:
        return None


def paused(data_dir=None):
    return os.path.exists(os.path.join(data_dir or DATA, "PAUSE_AUTOPILOT"))


def run(today=None, fetch=http_get, sleep=time.sleep, data_dir=None):
    d = data_dir or DATA
    today = today or date.fromisoformat(os.environ.get("TODAY") or datetime.utcnow().date().isoformat())
    if paused(d):
        print("PAUSE_AUTOPILOT found: nothing was changed.")
        return 0
    known = fetch_known_pages(fetch)
    raw, calls, failed = collect_autosuggest(fetch, sleep)
    sources = {k: "autosuggest" for k in raw}
    cal = load_json(os.path.join(d, "seasonal_calendar.json"), {})
    season = seasonal_ideas(cal, today)
    for kw, (boost, ev) in season.items():
        raw[kw] = raw.get(kw, 0.0) + boost
        sources[kw] = "seasonal_calendar:" + ev if kw not in sources else sources[kw]
    gsc_note = "skipped (no GSC_SA_JSON)" if not gsc_available() else "skipped (needs an approved Google auth library)"
    if not raw:
        print("FAIL: no source returned anything (autosuggest %d/%d calls failed)" % (failed, calls))
        return 1
    scored = normalize_scores(raw)
    kw_path, q_path = os.path.join(d, "keywords.json"), os.path.join(d, "topic_queue.json")
    records, n_new = merge_keywords(load_json(kw_path, []), scored, sources, today, known)
    queue, added = build_queue(records, load_json(q_path, []), today, known)
    save_json(kw_path, records)
    save_json(q_path, queue)
    lines = ["## DASHX Trend Radar (%s)" % today.isoformat(),
             "- autosuggest: %d calls, %d empty | seasonal ideas: %d | Search Console: %s | sitemap pages known: %s" % (calls, failed, len(season), gsc_note, "yes" if known is not None else "no (assumed)"),
             "- keywords kept: %d (new this run: %d) | queue: %d waiting, %d added now" % (len(records), n_new, len(queue), len(added))]
    lines += ["  - %s: %s -> %s" % (t["type"], t["keyword"], t["target_page"] or "(new page)") for t in added]
    out = "\n".join(lines)
    print(out)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(out + "\n")
    if failed == calls:
        print("::warning::every autosuggest call failed; only seasonal ideas were used")
    return 0


if __name__ == "__main__":
    sys.exit(run())
