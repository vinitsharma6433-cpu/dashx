#!/usr/bin/env python3
"""DASHX SEO health check. Read-only: only GET requests, nothing is posted or changed.

Checks the live store (sitemap, every page, schema, feed, blog freshness) and the reel queue.
Exit code 1 if any FAIL (GitHub then emails the owner). WARN does not fail the run.

Env: SITE (default https://dashx-store-api.onrender.com), QUEUE_URL or QUEUE_FILE, REPORT (output json path).
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from html.parser import HTMLParser

SITE = os.environ.get("SITE", "https://dashx-store-api.onrender.com").rstrip("/")
QUEUE_URL = os.environ.get("QUEUE_URL", "https://raw.githubusercontent.com/vinitsharma6433-cpu/dashx/main/poster/queue.json")
QUEUE_FILE = os.environ.get("QUEUE_FILE", "")
REPORT = os.environ.get("REPORT", "seo-health-report.json")
UA = {"User-Agent": "DASHX-SEO-Health/1.0 (read-only monitor)"}
BLOG_WARN_DAYS, BLOG_FAIL_DAYS = 3, 10

results = []  # (level, check, detail)


def add(level, check, detail=""):
    results.append({"level": level, "check": check, "detail": detail})


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


_opener = urllib.request.build_opener(NoRedirect)


def get(url, timeout=60, tries=2):
    """Returns (status, headers, body_text). Redirects are NOT followed (a sitemap URL must answer 200 itself)."""
    last = (0, {}, "")
    for i in range(tries):
        try:
            r = _opener.open(urllib.request.Request(url, headers=UA), timeout=timeout)
            return r.status, dict(r.headers), r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            return e.code, dict(e.headers), ""
        except Exception as e:  # network error / timeout
            last = (0, {}, str(e)[:120])
            time.sleep(5)
    return last


def warm_up():
    """Render free plan sleeps: wake it and wait up to ~3 minutes."""
    for i in range(12):
        st, _, _ = get(SITE + "/health", timeout=40, tries=1)
        if st == 200:
            return True
        time.sleep(15)
    return False


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title, self.desc, self.canonical, self.h1 = "", "", "", 0
        self.ld, self.robots = [], ""
        self._in_title = self._in_ld = False
        self._buf = ""

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "title":
            self._in_title = True
        elif tag == "h1":
            self.h1 += 1
        elif tag == "meta" and a.get("name") == "description":
            self.desc = a.get("content", "")
        elif tag == "meta" and a.get("name") == "robots":
            self.robots = a.get("content", "")
        elif tag == "link" and a.get("rel") == "canonical":
            self.canonical = a.get("href", "")
        elif tag == "script" and a.get("type") == "application/ld+json":
            self._in_ld, self._buf = True, ""

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        elif tag == "script" and self._in_ld:
            self._in_ld = False
            self.ld.append(self._buf)

    def handle_data(self, d):
        if self._in_title:
            self.title += d
        elif self._in_ld:
            self._buf += d


def ld_types(blocks):
    types, bad = set(), 0
    for b in blocks:
        try:
            j = json.loads(b)
        except Exception:
            bad += 1
            continue
        stack = [j]
        while stack:
            x = stack.pop()
            if isinstance(x, dict):
                t = x.get("@type")
                for tt in (t if isinstance(t, list) else [t]):
                    if tt:
                        types.add(tt)
                stack.extend(x.values())
            elif isinstance(x, list):
                stack.extend(x)
    return types, bad


def check_sitemap():
    st, _, body = get(SITE + "/robots.txt")
    if st != 200 or "sitemap:" not in body.lower():
        add("FAIL", "robots.txt", "missing or has no Sitemap line (HTTP %s)" % st)
    else:
        add("OK", "robots.txt", "has Sitemap line")
    st, _, body = get(SITE + "/sitemap.xml")
    if st != 200:
        add("FAIL", "sitemap.xml", "HTTP %s" % st)
        return []
    try:
        root = ET.fromstring(body)
    except Exception as e:
        add("FAIL", "sitemap.xml", "not valid XML: %s" % e)
        return []
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    items = []
    for u in root.findall("s:url", ns):
        loc = (u.findtext("s:loc", "", ns) or "").strip()
        lm = (u.findtext("s:lastmod", "", ns) or "").strip()
        items.append((loc, lm))
    add("OK" if len(items) >= 20 else "WARN", "sitemap size", "%d URLs" % len(items))
    generic = [l for l, _ in items if re.search(r"/p/item-", l)]
    if generic:
        add("FAIL", "generic product URLs in sitemap", ", ".join(generic[:5]))
    return items


def check_pages(items):
    titles, descs = {}, {}
    broken, redirected, schema_bad, meta_warn = [], [], [], []
    for loc, _ in items:
        st, _, body = get(loc)
        if 300 <= st < 400:
            redirected.append(loc)
            continue
        if st != 200:
            broken.append("%s (HTTP %s)" % (loc, st))
            continue
        p = Page()
        try:
            p.feed(body)
        except Exception:
            pass
        t, d = p.title.strip(), p.desc.strip()
        if not t or not (15 <= len(t) <= 75):
            meta_warn.append("%s title length %d" % (loc, len(t)))
        if not d or not (50 <= len(d) <= 220):
            meta_warn.append("%s description length %d" % (loc, len(d)))
        titles.setdefault(t, []).append(loc)
        descs.setdefault(d, []).append(loc)
        if p.canonical and p.canonical.rstrip("/") != loc.rstrip("/"):
            schema_bad.append("%s canonical points to %s" % (loc, p.canonical))
        if not p.canonical:
            schema_bad.append("%s has no canonical" % loc)
        if "noindex" in p.robots.lower():
            schema_bad.append("%s is noindex" % loc)
        types, bad = ld_types(p.ld)
        if bad:
            schema_bad.append("%s has %d invalid JSON-LD block(s)" % (loc, bad))
        if "/p/" in loc and "Product" not in types:
            schema_bad.append("%s has no Product schema" % loc)
        if "/blog/" in loc and "Article" not in types:
            schema_bad.append("%s has no Article schema" % loc)
        if "/blog/" in loc and p.h1 != 1:
            meta_warn.append("%s has %d h1 tags" % (loc, p.h1))
    add("FAIL" if broken else "OK", "pages answer 200", "; ".join(broken[:6]) if broken else "%d pages checked" % len(items))
    add("FAIL" if redirected else "OK", "sitemap URLs not redirected", "; ".join(redirected[:6]))
    add("FAIL" if schema_bad else "OK", "canonical, noindex, schema", "; ".join(schema_bad[:8]))
    add("WARN" if meta_warn else "OK", "title and description length", "; ".join(meta_warn[:8]))
    dup_t = ["%s (%d pages)" % (t[:50], len(v)) for t, v in titles.items() if t and len(v) > 1]
    dup_d = [d for d, v in descs.items() if d and len(v) > 1]
    add("WARN" if dup_t or dup_d else "OK", "duplicate titles or descriptions", "; ".join(dup_t[:4]) + (" | %d duplicate descriptions" % len(dup_d) if dup_d else ""))


def check_blog(items):
    days = []
    for loc, lm in items:
        if "/blog/" in loc and re.match(r"^\d{4}-\d{2}-\d{2}$", lm):
            days.append(date.fromisoformat(lm))
    if not days:
        add("WARN", "blog freshness", "no blog posts with lastmod in sitemap")
        return
    age = (datetime.now(timezone.utc).date() - max(days)).days
    lvl = "FAIL" if age > BLOG_FAIL_DAYS else "WARN" if age > BLOG_WARN_DAYS else "OK"
    add(lvl, "blog freshness", "%d posts, newest is %d day(s) old" % (len(days), age))


def check_feed():
    st, _, body = get(SITE + "/merchant-feed.tsv")
    if st != 200:
        add("FAIL", "merchant feed", "HTTP %s" % st)
        return
    rows = [l.split("\t") for l in body.strip().split("\n")]
    head, data = rows[0], rows[1:]
    col = {n: i for i, n in enumerate(head)}
    probs = []
    for r in data:
        if len(r) != len(head):
            probs.append("row with %d columns" % len(r))
            continue
        for need in ("id", "title", "link", "image_link", "price", "availability"):
            if not r[col[need]].strip():
                probs.append("%s missing %s" % (r[0], need))
        if "/p/item-" in r[col["link"]]:
            probs.append("%s links to a generic URL" % r[0])
    add("FAIL" if probs or not data else "OK", "merchant feed", "; ".join(probs[:6]) or "%d products" % len(data))
    if data and all(r[col["identifier_exists"]] == "no" for r in data if len(r) == len(head)):
        add("WARN", "feed GTIN", "no product has a GTIN (identifier_exists=no). Add GTIN or keep the exemption.")
    if data and all(not r[col["shipping_weight"]].strip() for r in data if len(r) == len(head)):
        add("WARN", "feed shipping_weight", "empty for all products")


def check_queue():
    try:
        if QUEUE_FILE:
            q = json.load(open(QUEUE_FILE, encoding="utf-8"))
        else:
            st, _, body = get(QUEUE_URL)
            if st != 200:
                add("WARN", "reel queue", "could not read queue (HTTP %s)" % st)
                return
            q = json.loads(body)
    except Exception as e:
        add("WARN", "reel queue", "could not read queue: %s" % str(e)[:80])
        return
    posts = q.get("posts", [])
    now = datetime.now(timezone.utc)

    def when(p):
        try:
            return datetime.fromisoformat(str(p.get("when")))
        except Exception:
            return None

    future = [p for p in posts if p.get("status") == "scheduled" and when(p) and when(p) > now]
    add("OK" if future else "FAIL", "reel queue fuel", "%d reel(s) scheduled ahead" % len(future) + ("" if future else ". Queue is empty: no reel will post."))
    recent = [p for p in posts if when(p) and now - timedelta(days=3) <= when(p) <= now]
    bad = []
    for p in recent:
        for net, r in (p.get("results") or {}).items():
            if isinstance(r, dict) and r.get("error"):
                bad.append("%s/%s" % (p.get("title", "?")[:20], net))
        yc = (p.get("notes") or {}).get("yt_comment")
        if isinstance(yc, list) and any(x != "ok" for x in yc):
            bad.append("%s/yt-comment" % p.get("title", "?")[:20])
    add("WARN" if bad else "OK", "reel posting errors (last 3 days)", "; ".join(bad[:6]) or "%d recent reels, no errors" % len(recent))


def main():
    t0 = time.time()
    if not warm_up():
        add("FAIL", "store reachable", "%s/health did not answer 200 in 3 minutes" % SITE)
    else:
        add("OK", "store reachable", "")
        items = check_sitemap()
        if items:
            check_pages(items)
            check_blog(items)
        check_feed()
    check_queue()
    fails = [r for r in results if r["level"] == "FAIL"]
    warns = [r for r in results if r["level"] == "WARN"]
    report = {"site": SITE, "time": datetime.now(timezone.utc).isoformat(timespec="seconds"), "fail": len(fails), "warn": len(warns), "results": results}
    json.dump(report, open(REPORT, "w", encoding="utf-8"), indent=1)
    icon = {"OK": "PASS", "WARN": "WARN", "FAIL": "FAIL"}
    lines = ["## DASHX SEO health: %d FAIL, %d WARN (%s)" % (len(fails), len(warns), report["time"]), "", "| Result | Check | Detail |", "|---|---|---|"]
    lines += ["| %s | %s | %s |" % (icon[r["level"]], r["check"], r["detail"].replace("|", "/")) for r in results]
    out = "\n".join(lines)
    print(out)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8").write(out + "\n")
    print("\n(%.0f s)" % (time.time() - t0))
    for r in fails:
        print("::error::%s: %s" % (r["check"], r["detail"]))
    for r in warns:
        print("::warning::%s: %s" % (r["check"], r["detail"]))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
