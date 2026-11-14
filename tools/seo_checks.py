#!/usr/bin/env python3
"""DASHX SEO check catalog (report-only). Standard library only.

data/seo_checks.json is a list of DECLARATIVE checks. Each one is a "type" from the fixed list below plus validated parameters.
No check can contain code or a regular expression, so a catalog entry can never run anything: the worst a bad entry can do is be ignored.
The weekly SEO Scout (tools/seo_scout.py) may add entries; this file is what reads them. Results are WARN only (never FAIL, never an issue).

Types: header_present, meta_present, html_lang_present, img_attr_ratio, h1_count, jsonld_type, links_min, text_absent, link_rel_present
Scopes: home, blog, product, all.   Kill switch: data/PAUSE_AUTOPILOT.
Env: SITE, DATA_DIR (default data), REPORT (default seo-checks-report.json)
"""
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from html.parser import HTMLParser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import seo_health as sh  # noqa: E402

SITE = os.environ.get("SITE", "https://dashx-store-api.onrender.com").rstrip("/")
DATA = os.environ.get("DATA_DIR", "data")
SCOPES = ("all", "home", "blog", "product")
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{2,39}$")
TOKEN_RE = re.compile(r"^[A-Za-z0-9:_.-]{2,60}$")


def page_kind(url):
    path = "/" + url[len(SITE):].lstrip("/") if url.startswith(SITE) else url
    path = path.split("?")[0].split("#")[0]
    if path in ("/", ""):
        return "home"
    if re.fullmatch(r"/blog/[a-z0-9-]+/?", path):
        return "blog"
    if re.fullmatch(r"/p/[A-Za-z0-9-]+/?", path):
        return "product"
    return "other"


class Doc(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.metas, self.lang, self.imgs, self.h1, self.rels = {}, "", [], 0, set()
        self.anchors, self.jsonld, self._a, self._ld, self._buf = [], [], None, False, ""

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "html":
            self.lang = a.get("lang", "") or ""
        elif tag == "meta":
            for k in ("name", "property"):
                if a.get(k):
                    self.metas[(k, a[k].lower())] = a.get("content", "")
        elif tag == "img":
            self.imgs.append(a)
        elif tag == "h1":
            self.h1 += 1
        elif tag == "link" and a.get("rel"):
            self.rels.update(a["rel"].lower().split())
        elif tag == "a" and a.get("href"):
            self._a = [a["href"], ""]
        elif tag == "script" and a.get("type") == "application/ld+json":
            self._ld, self._buf = True, ""

    def handle_endtag(self, tag):
        if tag == "a" and self._a:
            self.anchors.append((self._a[0], self._a[1].strip()))
            self._a = None
        elif tag == "script" and self._ld:
            self._ld = False
            self.jsonld.append(self._buf)

    def handle_data(self, d):
        if self._ld:
            self._buf += d
        elif self._a is not None:
            self._a[1] += d


def jsonld_types(blocks):
    types, stack = set(), []
    for b in blocks:
        try:
            stack.append(json.loads(b))
        except ValueError:
            continue
    while stack:
        x = stack.pop()
        if isinstance(x, dict):
            t = x.get("@type")
            types.update([t] if isinstance(t, str) else [i for i in (t or []) if isinstance(i, str)])
            stack.extend(x.values())
        elif isinstance(x, list):
            stack.extend(x)
    return types


# ---------- validation: a catalog entry is data; anything outside this shape is ignored ----------
def _num(v, lo, hi):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and lo <= v <= hi


def _params_error(t, p):
    if not isinstance(p, dict):
        return "params must be an object"
    if t == "header_present":
        return None if isinstance(p.get("name"), str) and re.fullmatch(r"[A-Za-z0-9-]{2,60}", p["name"]) else "bad header name"
    if t == "meta_present":
        return None if p.get("attr") in ("name", "property") and isinstance(p.get("value"), str) and TOKEN_RE.match(p["value"]) else "bad meta"
    if t == "html_lang_present":
        return None
    if t == "img_attr_ratio":
        return None if p.get("attr") in ("alt", "width", "height") and _num(p.get("min"), 0, 1) else "bad img rule"
    if t == "h1_count":
        return None if _num(p.get("equals"), 0, 5) and float(p["equals"]).is_integer() else "bad h1 rule"
    if t == "jsonld_type":
        a = p.get("any_of")
        return None if isinstance(a, list) and 1 <= len(a) <= 8 and all(isinstance(i, str) and re.fullmatch(r"[A-Za-z]{3,40}", i) for i in a) else "bad types"
    if t == "links_min":
        return None if p.get("prefix") in ("/blog/", "/p/") and _num(p.get("min"), 0, 20) else "bad links rule"
    if t == "text_absent":
        a = p.get("phrases")
        return None if isinstance(a, list) and 1 <= len(a) <= 8 and all(isinstance(i, str) and 3 <= len(i) <= 40 for i in a) else "bad phrases"
    if t == "link_rel_present":
        return None if p.get("rel") in ("icon", "canonical", "manifest", "apple-touch-icon") else "bad rel"
    return "unknown type"


TYPES = ("header_present", "meta_present", "html_lang_present", "img_attr_ratio", "h1_count", "jsonld_type", "links_min", "text_absent", "link_rel_present")


def validate(c):
    """None if the entry is safe and well formed, else the reason it is ignored."""
    if not isinstance(c, dict):
        return "entry is not an object"
    if not isinstance(c.get("id"), str) or not ID_RE.match(c["id"]):
        return "bad id"
    if c.get("type") not in TYPES:
        return "type is not in the fixed list"
    if c.get("scope") not in SCOPES:
        return "bad scope"
    if c.get("level") != "WARN":
        return "only WARN (report-only) is allowed"
    return _params_error(c["type"], c.get("params", {}))


# ---------- running a check on one page ----------
def run_check(c, doc, headers, url):
    """(ok, detail)."""
    t, p = c["type"], c.get("params", {})
    if t == "header_present":
        have = {k.lower() for k in headers}
        return p["name"].lower() in have, "header %s %s" % (p["name"], "present" if p["name"].lower() in have else "missing")
    if t == "meta_present":
        v = doc.metas.get((p["attr"], p["value"].lower()))
        return bool(v and v.strip()), "meta %s=%s %s" % (p["attr"], p["value"], "present" if v and v.strip() else "missing or empty")
    if t == "html_lang_present":
        return bool(doc.lang.strip()), "<html lang> %s" % ("present" if doc.lang.strip() else "missing")
    if t == "img_attr_ratio":
        if not doc.imgs:
            return True, "no images"
        n = sum(1 for i in doc.imgs if (i.get(p["attr"]) or "").strip())
        r = n / len(doc.imgs)
        return r >= p["min"], "%d of %d images have %s" % (n, len(doc.imgs), p["attr"])
    if t == "h1_count":
        return doc.h1 == int(p["equals"]), "%d <h1> (want %d)" % (doc.h1, p["equals"])
    if t == "jsonld_type":
        have = jsonld_types(doc.jsonld)
        ok = any(x in have for x in p["any_of"])
        return ok, "JSON-LD %s %s" % ("/".join(p["any_of"]), "found" if ok else "missing")
    if t == "links_min":
        me = "/" + url[len(SITE):].lstrip("/") if url.startswith(SITE) else url
        links = set()
        for href, _ in doc.anchors:
            h = href[len(SITE):] if href.startswith(SITE) else href
            h = h.split("#")[0].split("?")[0].rstrip("/")
            if h.startswith(p["prefix"]) and h != me.rstrip("/"):
                links.add(h)
        return len(links) >= p["min"], "%d links to %s (want %d+)" % (len(links), p["prefix"], p["min"])
    if t == "text_absent":
        bad = sorted({ph for ph in p["phrases"] for _, txt in doc.anchors if ph.lower() in txt.lower()})
        return not bad, "link text %s" % ("ok" if not bad else "uses: " + ", ".join(bad))
    if t == "link_rel_present":
        return p["rel"] in doc.rels, "<link rel=%s> %s" % (p["rel"], "present" if p["rel"] in doc.rels else "missing")
    return True, ""


def run_catalog(pages, checks):
    """pages: {url: (headers, html)}. Returns (rows, ignored). A row is {"check","url","detail"} for every FAILED check."""
    rows, ignored, ok_checks = [], [], []
    for c in checks:
        err = validate(c)
        if err:
            ignored.append("%s: %s" % (c.get("id", "?") if isinstance(c, dict) else "?", err))
        else:
            ok_checks.append(c)
    for url, (headers, html) in pages.items():
        kind = page_kind(url)
        if kind == "other":
            continue
        doc = Doc()
        try:
            doc.feed(html)
        except Exception:
            continue
        for c in ok_checks:
            if c["scope"] not in ("all", kind):
                continue
            ok, detail = run_check(c, doc, headers, url)
            if not ok:
                rows.append({"check": c["id"], "url": url, "detail": detail})
    return rows, ignored


def load_catalog(path):
    try:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        return d.get("checks", []) if isinstance(d, dict) else []
    except (OSError, ValueError):
        return []


def fetch_pages(get=sh.get, sitemap_xml=None):
    if sitemap_xml is None:
        st, _, sitemap_xml = get(SITE + "/sitemap.xml")
        if st != 200:
            raise RuntimeError("sitemap.xml answered HTTP %s" % st)
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    pages = {}
    for u in ET.fromstring(sitemap_xml).findall("s:url", ns):
        loc = (u.findtext("s:loc", "", ns) or "").strip()
        if page_kind(loc) == "other":
            continue
        st, headers, html = get(loc)
        if st == 200:
            pages[loc] = (headers, html)
    return pages


def main(get=sh.get, data_dir=None, sitemap_xml=None, warm=True):
    d = data_dir or DATA
    if os.path.exists(os.path.join(d, "PAUSE_AUTOPILOT")):
        print("PAUSE_AUTOPILOT found: nothing was checked.")
        return 0
    if warm and not sh.warm_up():
        print("could not wake the store; catalog checks skipped (report only, not a failure)")
        return 0
    try:
        pages = fetch_pages(get, sitemap_xml)
    except Exception as e:
        print("could not read the live site: %s (report only, not a failure)" % str(e)[:120])
        return 0
    checks = load_catalog(os.path.join(d, "seo_checks.json"))
    rows, ignored = run_catalog(pages, checks)
    by = {}
    for r in rows:
        by.setdefault(r["check"], []).append(r)
    lines = ["## DASHX SEO catalog checks (report only): %d checks, %d pages, %d WARN" % (len(checks) - len(ignored), len(pages), len(rows))]
    lines += ["- **%s** on %d page(s): %s (e.g. %s)" % (k, len(v), v[0]["detail"], v[0]["url"].replace(SITE, "")) for k, v in sorted(by.items())]
    lines += ["- ignored catalog entry (invalid, nothing was run): %s" % i for i in ignored]
    out = "\n".join(lines)
    print(out)
    for k, v in sorted(by.items()):
        print("::warning::SEO catalog %s: %d page(s), %s" % (k, len(v), v[0]["detail"]))
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(out + "\n")
    with open(os.environ.get("REPORT", "seo-checks-report.json"), "w", encoding="utf-8") as f:
        json.dump({"checks": len(checks), "pages": len(pages), "warn": len(rows), "ignored": ignored, "rows": rows}, f, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
