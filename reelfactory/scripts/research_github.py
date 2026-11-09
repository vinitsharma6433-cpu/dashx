"""Phase 3 research helper: ask the GitHub search API (metadata only, no code is downloaded or run) for
actively maintained, licensed repositories in each category. Output: docs/research/github_candidates.json.
Unauthenticated search allows 10 requests a minute, so the script paces itself."""

from __future__ import annotations

import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

SINCE = "2026-01-01"  # "actively maintained" = a push in the last ~7 months
CATEGORIES = {
    "1 AI story generation": "story generator",
    "2 Hindi/Hinglish dialogue": "hinglish",
    "3 script planning / storyboard": "storyboard",
    "4 character consistency": "character consistency",
    "5 2D animation / motion graphics": "motion canvas",
    "6 automated video editing": "video editing automation",
    "7 video quality analysis": "video quality",
    "8 subtitle timing / alignment": "forced alignment",
    "9 thumbnail generation": "youtube thumbnail",
    "10 YouTube SEO / metadata": "youtube seo",
    "11 YouTube publishing": "youtube uploader",
    "12 agents / workflow orchestration": "agent orchestration",
    "13 testing / self-healing pipelines": "self healing",
    "14 duplicate / originality detection": "minhash",
    "15 Hindi spelling data": "hunspell hindi",
}


def search(q: str) -> list[dict]:
    url = "https://api.github.com/search/repositories?" + urllib.parse.urlencode(
        {"q": f"{q} pushed:>{SINCE} stars:>20", "sort": "stars", "order": "desc", "per_page": 5})
    req = urllib.request.Request(url, headers={"User-Agent": "dashx-research", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        items = json.load(r).get("items", [])
    return [{"repo": i["full_name"], "stars": i["stargazers_count"], "license": (i.get("license") or {}).get("spdx_id"),
             "pushed": i["pushed_at"][:10], "archived": i["archived"], "issues": i["open_issues_count"],
             "lang": i.get("language"), "desc": (i.get("description") or "")[:110], "size_kb": i["size"]} for i in items]


def main() -> None:
    out = {}
    for cat, q in CATEGORIES.items():
        try:
            out[cat] = {"query": q, "results": search(q)}
        except Exception as e:  # rate limit or network: record and go on
            out[cat] = {"query": q, "error": str(e), "results": []}
        print(f"{cat}: {len(out[cat]['results'])} results", flush=True)
        time.sleep(7)
    dest = ROOT / "docs" / "research"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "github_candidates.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    for cat, v in out.items():
        print(f"\n## {cat}   (query: {v['query']})")
        for r in v["results"][:4]:
            print(f"  {r['repo']:38} *{r['stars']:<6} {str(r['license']):12} push {r['pushed']}  {r['desc'][:70]}")


if __name__ == "__main__":
    main()
