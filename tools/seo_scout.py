#!/usr/bin/env python3
"""DASHX SEO Scout (weekly). Standard library only. Finds good public SEO repos and switches on our OWN matching checks.

What it does, and what it can never do:
  1. Searches public GitHub repos about SEO audits (api.github.com only, read-only), vets each with the SAME scout code the reel system uses
     (autonomy/scout.py: licence, last push, commits vs stars, open-issue health, contributors, prompt-injection patterns, README/docs text only).
  2. Counts which of OUR fixed check templates (data/seo_scout_ideas.json) the good repos talk about.
  3. Switches on at most 2 new templates a week by adding them to data/seo_checks.json. The new check is REPORT-ONLY (WARN).
  4. Writes data/seo_scout_report.json and data/seo_scout_state.json. Commits only those files plus the catalog.
It NEVER clones, installs, imports or runs anything from a repo, never copies a repo's words, never adds a dependency, never touches posting, tokens,
schedules, prices, accounts, workflows, rules or code. A catalog entry is data of a fixed type (tools/seo_checks.py validates it), so even a wrong
entry cannot do anything but show a harmless WARN. A new TYPE of check needs code and a human review.
Kill switch: data/PAUSE_AUTOPILOT. Env: DATA_DIR, TODAY (YYYY-MM-DD), GITHUB_TOKEN (read-only API token, sent only to api.github.com).
"""
import copy
import json
import os
import sys
import urllib.parse
from collections import Counter
from datetime import date, datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "autonomy"))
import seo_checks as sc  # noqa: E402
import scout             # noqa: E402  (autonomy/scout.py: the vetting code, imported read-only)

DATA = os.environ.get("DATA_DIR", "data")
MAX_NEW_CHECKS = 2
MIN_REPOS_PER_IDEA = 1
MIN_STARS = 20          # a quality signal: ideas only count when a repo other people actually use talks about them


def search(query, cfg, fetch):
    """Like scout.search, but the best-known repos first (sort=stars, at least MIN_STARS) instead of 'recently updated' ones with 0 stars."""
    pushed_after = (datetime.now(timezone.utc) - timedelta(days=cfg["stale_days"])).strftime("%Y-%m-%d")
    q = urllib.parse.quote("%s stars:>=%d pushed:>%s fork:false" % (query, MIN_STARS, pushed_after))
    body, _ = fetch("https://%s/search/repositories?q=%s&sort=stars&per_page=%d" % (cfg["api_host"], q, cfg["results_per_query"]), cfg)
    return [r for r in json.loads(body).get("items", []) if r.get("stargazers_count", 0) >= MIN_STARS]


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


def seo_cfg(base, ideas_doc):
    """The reel scout's safety config (licences, injection patterns, limits) with SEO topics and SEO ideas swapped in."""
    cfg = copy.deepcopy(base)
    cfg["query_topics"] = ideas_doc["query_topics"]
    cfg["ideas"] = [{k: i[k] for k in ("id", "label", "keywords", "target", "kind")} for i in ideas_doc["ideas"]]
    cfg["queries_per_week"] = min(3, len(ideas_doc["query_topics"]))
    return cfg


def pick_new_checks(idea_repos, ideas_by_id, catalog_ids, rejected, today, cap=MAX_NEW_CHECKS):
    """idea_repos: {idea_id: [repo names]}. Most-mentioned first. Returns (new_entries, rejected_now)."""
    new, rej = [], []
    for idea_id, repos in sorted(idea_repos.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        if len(new) >= cap:
            break
        if idea_id in catalog_ids or idea_id in rejected or len(repos) < MIN_REPOS_PER_IDEA:
            continue
        idea = ideas_by_id.get(idea_id)
        if not idea:
            continue
        entry = dict(idea["check"], id=idea_id, level="WARN", source="scout:" + ",".join(sorted(repos)[:3]), added=today)
        err = sc.validate(entry)
        if err:
            rej.append(idea_id)
            continue
        new.append(entry)
    return new, rej


def run(today=None, fetch=scout.api_get, data_dir=None, now=None):
    d = data_dir or DATA
    today = today or date.fromisoformat(os.environ.get("TODAY") or datetime.now(timezone.utc).date().isoformat())
    now = now or datetime.now(timezone.utc)
    if os.path.exists(os.path.join(d, "PAUSE_AUTOPILOT")):
        print("PAUSE_AUTOPILOT found: nothing was changed.")
        return 0
    ideas_doc = load_json(os.path.join(d, "seo_scout_ideas.json"), None)
    if not ideas_doc or not ideas_doc.get("ideas"):
        print("FAIL: data/seo_scout_ideas.json is missing or empty")
        return 1
    cfg = seo_cfg(scout.load_config(), ideas_doc)
    ideas_by_id = {i["id"]: i for i in ideas_doc["ideas"]}
    queries = scout.week_queries(today, cfg)
    repos, failed = {}, 0
    for topic, q in queries:
        try:
            for r in search(q, cfg, fetch):
                repos.setdefault(r.get("full_name", "?"), r)
        except Exception:
            failed += 1
    if failed == len(queries) or not repos:
        print("FAIL: GitHub search returned nothing (%d of %d queries failed); nothing was changed" % (failed, len(queries)))
        return 1
    chosen = list(repos.values())[: cfg.get("max_repos_per_week", 12)]
    records = [scout.evaluate(r, cfg, fetch, now) for r in chosen]
    idea_repos = {}
    for rec in records:
        if rec["verdict"] == "candidate":
            for idea in rec["ideas"]:
                idea_repos.setdefault(idea["id"], []).append(rec["repo"])
    cat_path, state_path = os.path.join(d, "seo_checks.json"), os.path.join(d, "seo_scout_state.json")
    catalog = load_json(cat_path, {"checks": []})
    catalog.setdefault("checks", [])
    state = load_json(state_path, {"rejected": [], "weeks": []})
    new, rej = pick_new_checks(idea_repos, ideas_by_id, {c.get("id") for c in catalog["checks"] if isinstance(c, dict)}, set(state.get("rejected", [])), today.isoformat())
    catalog["checks"] += new
    state["rejected"] = sorted(set(state.get("rejected", [])) | set(rej))
    state["weeks"] = (state.get("weeks", []) + [today.isoformat()])[-26:]
    verdicts = Counter(r["verdict"] for r in records)
    report = {"date": today.isoformat(), "queries": [q for _, q in queries], "repos_seen": len(repos), "repos_vetted": len(records), "verdicts": dict(verdicts),
              "injection_repos": [r["repo"] for r in records if r["verdict"] == "injection"],
              "good_repos": [{"repo": r["repo"], "stars": r["stars"], "license": r["license"], "score": r.get("score"), "ideas": [i["id"] for i in r["ideas"]]} for r in records if r["verdict"] == "candidate"],
              "idea_counts": {k: len(v) for k, v in sorted(idea_repos.items(), key=lambda kv: -len(kv[1]))}, "new_checks": [c["id"] for c in new], "rejected_now": rej}
    save_json(cat_path, catalog)
    save_json(state_path, state)
    save_json(os.path.join(d, "seo_scout_report.json"), report)
    out = ["## DASHX SEO Scout (%s)" % today.isoformat(),
           "- %d repos found, %d vetted: %s | injection attempts dropped: %d" % (len(repos), len(records), dict(verdicts), len(report["injection_repos"])),
           "- ideas our templates share with the good repos: %s" % (", ".join("%s x%d" % kv for kv in report["idea_counts"].items()) or "none"),
           "- new report-only checks switched on: %s" % (", ".join(c["id"] for c in new) or "none (nothing new this week)")]
    text = "\n".join(out)
    print(text)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(text + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(run())
