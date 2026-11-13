#!/usr/bin/env python3
"""Submit new or changed store URLs to IndexNow (Bing, Yandex and others; Google ignores IndexNow).

Reads the live sitemap, compares each URL's lastmod with state/indexnow.json and submits only
what is new or changed. A URL with no lastmod is submitted once. State is saved only after the
submit succeeds, so a failed run retries the same URLs next time.
The key is public by design (it is served at /<key>.txt on the store). No secret is used.

Env: SITE, INDEXNOW_KEY, STATE_FILE, DRY_RUN=1 (print only).
"""
import json
import os
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

SITE = os.environ.get("SITE", "https://dashx-store-api.onrender.com").rstrip("/")
KEY = os.environ.get("INDEXNOW_KEY", "")
STATE_FILE = os.environ.get("STATE_FILE", "state/indexnow.json")
ENDPOINT = "https://api.indexnow.org/indexnow"
UA = {"User-Agent": "DASHX-IndexNow/1.0"}
NS = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}


def parse_sitemap(xml_text):
    """Returns {url: lastmod or ''}."""
    root = ET.fromstring(xml_text)
    out = {}
    for u in root.findall("s:url", NS):
        loc = (u.findtext("s:loc", "", NS) or "").strip()
        if loc:
            out[loc] = (u.findtext("s:lastmod", "", NS) or "").strip()
    return out


def pending(sitemap, state):
    """URLs never submitted, or whose lastmod differs from the submitted one."""
    return sorted(u for u, lm in sitemap.items() if u not in state or state[u] != lm)


def load_state(path):
    try:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        return d.get("submitted", {}) if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def save_state(path, state):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"submitted": dict(sorted(state.items()))}, f, indent=1)
        f.write("\n")


def payload(host, key, urls):
    return {"host": host, "key": key, "keyLocation": "https://%s/%s.txt" % (host, key), "urlList": urls}


def fetch(url, data=None, headers=None, timeout=60):
    req = urllib.request.Request(url, data=data, headers=dict(UA, **(headers or {})))
    return urllib.request.urlopen(req, timeout=timeout)


def main():
    if not KEY or len(KEY) < 8:
        print("INDEXNOW_KEY is not set")
        return 1
    host = SITE.split("://", 1)[1]
    sitemap = parse_sitemap(fetch(SITE + "/sitemap.xml").read().decode("utf-8"))
    if not sitemap:
        print("sitemap has no URLs; nothing submitted")
        return 1
    # the key file must be live, otherwise IndexNow rejects the submit
    kf = fetch("%s/%s.txt" % (SITE, KEY)).read().decode("utf-8").strip()
    if kf != KEY:
        print("key file at /%s.txt does not match the key" % KEY)
        return 1
    state = load_state(STATE_FILE)
    todo = pending(sitemap, state)
    print("sitemap %d URLs, %d new or changed" % (len(sitemap), len(todo)))
    if not todo:
        return 0
    if os.environ.get("DRY_RUN") == "1":
        print("\n".join(todo))
        return 0
    for i in range(0, len(todo), 9000):  # IndexNow allows 10000 per request
        chunk = todo[i:i + 9000]
        body = json.dumps(payload(host, KEY, chunk)).encode("utf-8")
        try:
            r = fetch(ENDPOINT, body, {"Content-Type": "application/json; charset=utf-8"})
            code = r.status
        except urllib.error.HTTPError as e:
            code = e.code
        if code not in (200, 202):
            print("IndexNow answered HTTP %s; state not updated for this batch" % code)
            save_state(STATE_FILE, state)
            return 1
        for u in chunk:
            state[u] = sitemap[u]
        save_state(STATE_FILE, state)
        print("submitted %d URLs (HTTP %s)" % (len(chunk), code))
    return 0


if __name__ == "__main__":
    sys.exit(main())
