#!/usr/bin/env python3
"""DASHX Refresh and fix loop (F3). Standard library only. Weekly (GitHub Action). Read-only on the live site.

It looks at the live pages (store sitemap) and, when present, Search Console data (data/gsc_queries.json), and turns what it finds into
"update" tasks in data/topic_queue.json. Autopilot F2 (dashx-brain) is the one that rewrites a blog page; this script never edits a page.

Always-on rules (no Search Console needed), blog pages only:
  thin page          fewer than 250 words
  overlap            two posts share too much text: the NEWER one is told to differentiate (merge is a human call)
  weak links         fewer than 2 related guides or no product link on a blog post
  title / meta       title over 60 chars, description outside 120-155 chars
Non-blog pages (home, products) are only REPORTED: they are code or /portal work, not something F2 can rewrite.
Search Console rules (only if data/gsc_queries.json exists; the live fetch is not installed yet):
  position 8-20 with impressions            refresh the page (links + title)
  impressions but CTR under 2%              rewrite title/description, ONE variant at a time (logged in data/variants_log.json)
  query with impressions and no page        new topic (only if it passes the radar keyword rule)
  no impressions 90 days after publishing   improve or merge, never leave a thin page
One intent per page: a page that already has a queued task gets no second one. At most 3 new tasks per run.
Kill switch: data/PAUSE_AUTOPILOT -> exit at once, nothing changed.

Env: DATA_DIR (default data), SITE, TODAY (YYYY-MM-DD).
"""
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from datetime import date, datetime
from html.parser import HTMLParser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import seo_health as sh      # noqa: E402  (page parser, get, warm_up)
import trend_radar as tr     # noqa: E402  (keyword rule, clusters)

DATA = os.environ.get("DATA_DIR", "data")
SITE = os.environ.get("SITE", "https://dashx-store-api.onrender.com").rstrip("/")
MAX_NEW_TASKS = 3
MIN_WORDS = 250
OVERLAP_MIN = 0.45          # share of 3-word phrases two posts have in common (tunable; the report shows the numbers)
DESC_MIN, DESC_MAX, TITLE_MAX = 120, 155, 60
VARIANT_WAIT_DAYS = 28      # one title variant at a time: wait this long before the next one so the CTR can be compared
STOP_H2 = ("related guides", "dashx balls mentioned", "more dashx balls")
PRIORITY = {"thin": 70, "overlap": 60, "weak_links": 40, "title": 50, "meta": 20,
            "gsc_position": 80, "gsc_ctr": 75, "gsc_no_impressions": 65}


# ---------- reading pages ----------
class Text(HTMLParser):
    """Article text: from the first <h1> up to the 'Related guides' style blocks the store adds at render time."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.segs, self._tag, self._on, self._skip = [], "", False, 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript", "nav"):
            self._skip += 1
        if tag == "h1":
            self._on = True
        self._tag = tag

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript", "nav") and self._skip:
            self._skip -= 1

    def handle_data(self, d):
        if self._on and not self._skip and d.strip():
            self.segs.append((self._tag, d.strip()))


def article_text(html):
    p = Text()
    p.feed(html)
    out = []
    for tag, t in p.segs:
        if tag == "h2" and t.lower().startswith(STOP_H2):
            break
        out.append(t)
    return " ".join(out)


def words_of(text):
    return re.findall(r"[a-z0-9]+", text.lower())


def shingles(text, n=3):
    w = words_of(text)
    return {" ".join(w[i:i + n]) for i in range(max(0, len(w) - n + 1))}


def overlap(a, b):
    """Share of the smaller post's 3-word phrases that also appear in the other post (0-1)."""
    sa, sb = shingles(a), shingles(b)
    return (len(sa & sb) / min(len(sa), len(sb))) if sa and sb else 0.0


def blog_slug(url):
    m = re.search(r"/blog/([a-z0-9-]+)/?$", url)
    return m.group(1) if m else None


def load_pages(get=sh.get, sitemap_xml=None):
    """{url: {"html", "page": sh.Page, "text", "lastmod"}} for every blog, product and home page in the sitemap."""
    if sitemap_xml is None:
        st, _, sitemap_xml = get(SITE + "/sitemap.xml")
        if st != 200:
            raise RuntimeError("sitemap.xml answered HTTP %s" % st)
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    pages = {}
    for u in ET.fromstring(sitemap_xml).findall("s:url", ns):
        loc = (u.findtext("s:loc", "", ns) or "").strip()
        if not (blog_slug(loc) or "/p/" in loc or loc.rstrip("/") == SITE):
            continue
        st, _, html = get(loc)
        if st != 200:
            continue
        p = sh.Page()
        p.feed(html)
        pages[loc] = {"html": html, "page": p, "text": article_text(html), "lastmod": (u.findtext("s:lastmod", "", ns) or "").strip()}
    return pages


# ---------- always-on rules ----------
def local_links(page_obj, loc):
    out = []
    for h in page_obj.links:
        if h.startswith("/"):
            out.append(h.split("#")[0].split("?")[0].rstrip("/") or "/")
        elif h.startswith(SITE):
            out.append(h[len(SITE):].split("#")[0].split("?")[0].rstrip("/") or "/")
    return out


def audit(pages):
    """List of findings: {"rule", "page", "detail", "priority", "slug" (blog only)}."""
    found = []
    blogs = {u: d for u, d in pages.items() if blog_slug(u)}
    for loc, d in pages.items():
        p, slug = d["page"], blog_slug(loc)
        title = p.title.strip()
        if len(title) > TITLE_MAX:
            found.append({"rule": "title", "page": loc, "slug": slug, "detail": "title is %d chars (max %d)" % (len(title), TITLE_MAX), "priority": PRIORITY["title"]})
        if not slug:
            continue
        n = len(words_of(d["text"]))
        if n < MIN_WORDS:
            found.append({"rule": "thin", "page": loc, "slug": slug, "detail": "only %d words (need %d)" % (n, MIN_WORDS), "priority": PRIORITY["thin"]})
        dl = len(p.desc.strip())
        if not (DESC_MIN <= dl <= DESC_MAX):
            found.append({"rule": "meta", "page": loc, "slug": slug, "detail": "description is %d chars (want %d-%d)" % (dl, DESC_MIN, DESC_MAX), "priority": PRIORITY["meta"]})
        links = local_links(p, loc)
        guides = {l for l in links if re.fullmatch(r"/blog/[a-z0-9-]+", l) and l != "/blog/" + slug}
        products = [l for l in links if l.startswith("/p/")]
        if len(guides) < 2 or not products:
            found.append({"rule": "weak_links", "page": loc, "slug": slug, "priority": PRIORITY["weak_links"],
                          "detail": "%d related guides and %d product links (want 2+ and 1+)" % (len(guides), len(products))})
    urls = sorted(blogs, key=lambda u: blogs[u]["lastmod"])      # oldest first
    for i, a in enumerate(urls):
        for b in urls[i + 1:]:
            s = overlap(blogs[a]["text"], blogs[b]["text"])
            if s >= OVERLAP_MIN:                                  # b is newer (or same day): b must differentiate from a
                found.append({"rule": "overlap", "page": b, "slug": blog_slug(b), "other": blog_slug(a), "priority": round(PRIORITY["overlap"] + 40 * (s - OVERLAP_MIN)),
                              "detail": "shares %d%% of its text with blog/%s (differentiate, do not copy)" % (round(s * 100), blog_slug(a))})
    return found


def overlap_table(pages):
    """Every blog pair with its overlap, for the report (so the threshold can be tuned from real numbers)."""
    urls = sorted(u for u in pages if blog_slug(u))
    return sorted(({"a": blog_slug(a), "b": blog_slug(b), "overlap": round(overlap(pages[a]["text"], pages[b]["text"]), 2)} for i, a in enumerate(urls) for b in urls[i + 1:]),
                  key=lambda r: -r["overlap"])[:10]


# ---------- Search Console rules (need data/gsc_queries.json) ----------
def gsc_findings(rows, pages, variants, today, known_blog_slugs):
    """rows: [{"query","page","clicks","impressions","ctr","position"}]. Pure function; the live fetch is not installed yet."""
    found, new_topics = [], []
    by_page = {}
    for r in rows:
        by_page.setdefault(r.get("page") or "", []).append(r)
    for page, rs in by_page.items():
        slug = blog_slug(page) if page else None
        if not slug:
            continue
        imp = sum(float(r.get("impressions", 0)) for r in rs)
        clicks = sum(float(r.get("clicks", 0)) for r in rs)
        pos = (sum(float(r.get("position", 0)) * float(r.get("impressions", 0)) for r in rs) / imp) if imp else 0
        if imp >= 20 and 8 <= pos <= 20:
            found.append({"rule": "gsc_position", "page": page, "slug": slug, "priority": PRIORITY["gsc_position"], "focus": "links+title",
                          "detail": "average position %.1f with %d impressions: refresh, add internal links, improve the title" % (pos, imp)})
        if imp >= 100 and clicks / imp < 0.02:
            last = max((v["date"] for v in variants if v.get("page") == page), default="")
            if last and (today - date.fromisoformat(last)).days < VARIANT_WAIT_DAYS:
                continue                                           # one variant at a time: wait and measure the one that is live
            found.append({"rule": "gsc_ctr", "page": page, "slug": slug, "priority": PRIORITY["gsc_ctr"], "focus": "title+description",
                          "detail": "%d impressions but CTR %.1f%%: rewrite title and description (one variant)" % (imp, 100 * clicks / imp)})
    for slug in known_blog_slugs:
        page = SITE + "/blog/" + slug
        if page not in by_page and page in pages and pages[page]["lastmod"]:
            try:
                age = (today - date.fromisoformat(pages[page]["lastmod"])).days
            except ValueError:
                continue
            if age >= 90:
                found.append({"rule": "gsc_no_impressions", "page": page, "slug": slug, "priority": PRIORITY["gsc_no_impressions"], "focus": "improve-or-merge",
                              "detail": "no impressions in the data and last changed %d days ago: improve or merge, do not leave it thin" % age})
    for r in rows:
        if not r.get("page") and float(r.get("impressions", 0)) >= 10 and tr.keyword_ok(str(r.get("query", ""))):
            new_topics.append({"keyword": r["query"].strip().lower(), "impressions": float(r["impressions"])})
    return found, new_topics


# ---------- tasks ----------
def keyword_for(slug, keywords):
    """Best radar keyword aimed at this page, else the slug as words (only if it passes the keyword rule)."""
    recs = [k for k in keywords if k.get("target_page") == "/blog/" + slug and tr.keyword_ok(k.get("keyword", ""))]
    if recs:
        return max(recs, key=lambda k: k.get("trend_score", 0))["keyword"]
    guess = re.sub(r"\b(\d+)g\b", "", slug.replace("-", " ")).strip()
    guess = re.sub(r"\s+", " ", guess)
    return guess if tr.keyword_ok(guess) else ""


def build_tasks(findings, queue, keywords, today, cap=MAX_NEW_TASKS):
    queue = list(queue)
    busy = {t.get("target_page") for t in queue if t.get("status", "queued") == "queued" and t.get("target_page")}
    added, skipped = [], []
    best = {}
    for f in findings:                                  # one intent per page: keep the strongest finding of each page
        if f.get("slug") and (f["slug"] not in best or f["priority"] > best[f["slug"]]["priority"]):
            best[f["slug"]] = f
    for f in sorted(best.values(), key=lambda f: -f["priority"]):
        page = "/blog/" + f["slug"]
        if len(added) >= cap:
            skipped.append((f["slug"], "weekly cap"))
            continue
        if page in busy:
            skipped.append((f["slug"], "already has a queued task"))
            continue
        kw = keyword_for(f["slug"], keywords)
        if not kw:
            skipped.append((f["slug"], "no on-topic keyword"))
            continue
        cluster, _, _ = tr.cluster_of(kw, None)
        task = {"id": "%s-refresh-%s-%s" % (today.isoformat(), f["slug"], f["rule"])[:100], "type": "update", "keyword": kw, "language": "en",
                "intent": tr.intent_of(kw), "cluster": cluster, "target_page": page, "source": "refresh:" + f["rule"],
                "trend_score": min(100, f["priority"]), "added": today.isoformat(), "status": "queued", "note": f["detail"]}
        if f.get("focus"):
            task["focus"] = f["focus"]
        if f.get("other"):
            task["differentiate_from"] = "/blog/" + f["other"]
        queue.append(task)
        busy.add(page)
        added.append(task)
    return queue, added, skipped


def new_topic_tasks(new_topics, queue, today, cap):
    queue, added = list(queue), []
    have = {t.get("keyword") for t in queue}
    for t in sorted(new_topics, key=lambda t: -t["impressions"]):
        if len(added) >= cap:
            break
        kw = t["keyword"]
        if kw in have:
            continue
        cluster, page, ttype = tr.cluster_of(kw, None)
        task = {"id": "%s-gsc-%s" % (today.isoformat(), re.sub(r"[^a-z0-9]+", "-", kw)[:50].strip("-")), "type": ttype, "keyword": kw, "language": tr.language_of(kw),
                "intent": tr.intent_of(kw), "cluster": cluster, "target_page": page, "source": "refresh:gsc_query_without_page",
                "trend_score": min(100, 50 + int(t["impressions"] // 10)), "added": today.isoformat(), "status": "queued"}
        queue.append(task)
        added.append(task)
    return queue, added


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


def run(today=None, get=sh.get, data_dir=None, sitemap_xml=None, warm=True):
    d = data_dir or DATA
    today = today or date.fromisoformat(os.environ.get("TODAY") or datetime.utcnow().date().isoformat())
    if os.path.exists(os.path.join(d, "PAUSE_AUTOPILOT")):
        print("PAUSE_AUTOPILOT found: nothing was changed.")
        return 0
    if warm and not sh.warm_up():
        print("FAIL: the store did not wake up in 3 minutes")
        return 1
    try:
        pages = load_pages(get, sitemap_xml)
    except Exception as e:
        print("FAIL: could not read the live site: %s" % str(e)[:150])
        return 1
    blog_n = sum(1 for u in pages if blog_slug(u))
    if blog_n < 3:
        print("FAIL: only %d blog pages could be read; not trusting this run" % blog_n)
        return 1
    findings = audit(pages)
    queue = load_json(os.path.join(d, "topic_queue.json"), [])
    keywords = load_json(os.path.join(d, "keywords.json"), [])
    variants = load_json(os.path.join(d, "variants_log.json"), [])
    gsc_rows = load_json(os.path.join(d, "gsc_queries.json"), None)
    new_topics = []
    if gsc_rows:
        gf, new_topics = gsc_findings(gsc_rows, pages, variants, today, [blog_slug(u) for u in pages if blog_slug(u)])
        findings += gf
    queue, added, skipped = build_tasks(findings, queue, keywords, today)
    queue, added_new = new_topic_tasks(new_topics, queue, today, max(0, MAX_NEW_TASKS - len(added)))
    for t in added:
        if t["source"] == "refresh:gsc_ctr":      # log the variant so the next one waits and the CTR can be compared
            variants.append({"page": SITE + t["target_page"], "date": today.isoformat(), "rule": "gsc_ctr", "old_title": pages.get(SITE + t["target_page"], {}).get("page", sh.Page()).title.strip()})
    non_blog = [f for f in findings if not f.get("slug")]
    report = {"date": today.isoformat(), "pages_read": len(pages), "blog_pages": blog_n, "search_console": "used" if gsc_rows else "no data (data/gsc_queries.json missing)",
              "findings": [{k: f[k] for k in ("rule", "page", "detail", "priority")} for f in findings], "tasks_added": [t["id"] for t in added + added_new],
              "skipped": ["%s (%s)" % s for s in skipped], "overlap_top": overlap_table(pages)}
    save_json(os.path.join(d, "topic_queue.json"), queue)
    save_json(os.path.join(d, "refresh_report.json"), report)
    if variants:
        save_json(os.path.join(d, "variants_log.json"), variants)
    lines = ["## DASHX Refresh loop (%s)" % today.isoformat(),
             "- %d pages read (%d blog) | Search Console: %s | findings: %d | new tasks: %d (cap %d)" % (len(pages), blog_n, report["search_console"], len(findings), len(added) + len(added_new), MAX_NEW_TASKS)]
    lines += ["  - task %s: %s (%s)" % (t["target_page"] or t["keyword"], t["source"], t.get("note", "")) for t in added + added_new]
    lines += ["  - needs code or /portal, not a blog rewrite: %s %s" % (f["page"], f["detail"]) for f in non_blog]
    lines += ["  - skipped %s" % s for s in report["skipped"]]
    lines += ["- top overlaps (3-word phrases shared): " + ", ".join("%s~%s %d%%" % (o["a"][:18], o["b"][:18], round(o["overlap"] * 100)) for o in report["overlap_top"][:4])]
    out = "\n".join(lines)
    print(out)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(out + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(run())
