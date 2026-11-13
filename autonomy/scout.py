"""DASHX Autonomy, Phase 9: Repo Scout. Standard library only. MODE 1 (propose only). There is NO apply code in this file.

What it does, once a week and never inside a blocked posting window:
  1. rotates 3 of the search topics (by ISO week) and searches public repos with the GitHub REST API (GITHUB_TOKEN, free, read-only)
  2. scores every repo with 5 checks: licence, last push, commit count vs stars, open-issue health, contributors
  3. reads ONLY the README text (and up to 2 docs .md files) over HTTPS from api.github.com. No clone, no install, no build, no binary, nothing is run.
  4. turns what it reads into ideas from OUR OWN catalog (autonomy/scout_config.json). It never copies text from a repo.
  5. writes autonomy/scout/<date>.md. The ideas are only PROPOSALS for the owner.

Safety: everything read from a repo is untrusted DATA. A line that tries to give instructions is logged as "injection attempt" with the repo name and the whole
repo is dropped. The token goes ONLY to api.github.com. No link found in a repo is ever followed. Topics about posting, tokens, schedules, accounts,
engagement tricks, copied text or false brand claims are never proposed. Kill switch: STOP_AUTONOMY. Rule file: unchanged and sealed; the report path must
be a state file in RULES.json or the scout refuses to write (fail closed).
"""
from __future__ import annotations

import base64
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import guard  # noqa: E402

ROOT = guard.ROOT
IST = guard.IST
CONFIG = "autonomy/scout_config.json"
OUT_DIR = "autonomy/scout"
LOG = "autonomy/log.md"
UA = "DASHX-autonomy-scout/1.0 (read-only)"


# ---------------------------------------------------------------- config
def load_config(root: Path = ROOT) -> dict:
    return json.loads((root / CONFIG).read_text(encoding="utf-8"))


# ---------------------------------------------------------------- the only network door
def api_get(url: str, cfg: dict, raw: bool = False) -> tuple[bytes, dict]:
    """GET one URL on api.github.com over HTTPS. Any other host or scheme is refused, so a link inside a repo can never be followed."""
    u = urllib.parse.urlparse(url)
    if u.scheme != "https" or u.hostname != cfg["api_host"]:
        raise PermissionError(f"refused: {u.scheme}://{u.hostname} is not {cfg['api_host']}")
    headers = {"User-Agent": UA, "Accept": "application/vnd.github.raw+json" if raw else "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    tok = os.environ.get("GITHUB_TOKEN", "")
    if tok:
        headers["Authorization"] = "Bearer " + tok          # only ever sent to api.github.com (checked above)
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=cfg["timeout_seconds"]) as r:
        return r.read(cfg["max_readme_bytes"] * 4), dict(r.headers)


def last_page(headers: dict) -> int | None:
    """Number of items when asked with per_page=1: the page number in the rel=last link."""
    link = headers.get("Link") or headers.get("link") or ""
    m = re.search(r'[?&]page=(\d+)>; rel="last"', link)
    return int(m.group(1)) if m else None


# ---------------------------------------------------------------- the 5 checks
def license_check(spdx: str | None, cfg: dict) -> tuple[str, float]:
    """MIT/Apache = reusable ideas. None or GPL/AGPL (and similar) = ideas only. Unknown = skip."""
    if spdx is None:
        return "ideas only (no licence)", 0.5
    if spdx in cfg["license_reusable"]:
        return "reusable ideas", 1.0
    if spdx in cfg["license_ideas_only"]:
        return "ideas only", 0.5
    return "skip (unknown licence)", 0.0


def recency_check(pushed_at: str, now: datetime, cfg: dict) -> tuple[bool, str]:
    try:
        t = datetime.fromisoformat(pushed_at.replace("Z", "+00:00"))
    except Exception:
        return False, "skip (no push date)"
    age = (now.astimezone(timezone.utc) - t).days
    return (age <= cfg["stale_days"]), (f"last push {age} days ago" if age <= cfg["stale_days"] else f"skip (last push {age} days ago, older than 12 months)")


def commits_check(stars: int, commits: int | None, cfg: dict) -> tuple[bool, str]:
    if commits is None:
        return True, "commit count unknown"
    if stars >= cfg["popular_stars"] and commits < cfg["min_commits_if_popular"]:
        return False, f"skip (suspicious: {stars} stars but only {commits} commits)"
    return True, f"{commits} commits"


def issues_check(titles: list[str], cfg: dict) -> tuple[bool, str]:
    pat = re.compile(cfg["bad_issue_pattern"], re.I)
    hits = sum(1 for t in titles if pat.search(t or ""))
    return (hits < cfg["bad_issue_hits"]), (f"{hits} 'does not work' issues in the last {len(titles)}" if hits < cfg["bad_issue_hits"] else f"skip ({hits} 'does not work' issues in the last {len(titles)})")


def contributors_check(n: int | None) -> tuple[bool, str]:
    if n is None:
        return True, "contributors unknown"
    return (n >= 2), (f"{n} contributors" if n >= 2 else "weak (1 contributor only)")


# ---------------------------------------------------------------- reading text safely
def injection_hits(text: str, cfg: dict) -> list[str]:
    """Which of OUR patterns matched (numbers only). The repo's own words are never kept, logged or printed."""
    return [f"pattern {i + 1}" for i, p in enumerate(cfg["injection_patterns"]) if re.search(p, text, re.I | re.S)]


def blocked_topics(text: str, cfg: dict) -> list[str]:
    return sorted(k for k, p in cfg["never_apply_topics"].items() if re.search(p, text, re.I))


def ideas_from(text: str, cfg: dict) -> list[dict]:
    """Our OWN ideas whose keywords appear in the text. The repo's words are never copied into an idea."""
    found = []
    for idea in cfg["ideas"]:
        if re.search(idea["keywords"], text, re.I):
            found.append({k: idea[k] for k in ("id", "label", "target", "kind")})
    return found


# ---------------------------------------------------------------- the scouting of one repo
def evaluate(repo: dict, cfg: dict, fetch, now: datetime) -> dict:
    """Returns a record with verdict 'candidate' | 'skip' | 'injection'. Never raises for a bad repo."""
    name = repo.get("full_name", "?")
    spdx = (repo.get("license") or {}).get("spdx_id")
    if spdx in ("NOASSERTION", "", "other"):
        spdx = "NOASSERTION"
    lic, lic_score = license_check(spdx, cfg)
    rec = {"repo": name, "stars": repo.get("stargazers_count", 0), "license": spdx or "none", "checks": {}, "verdict": "skip", "ideas": [], "blocked": [], "notes": []}
    rec["checks"]["license"] = lic
    if lic_score == 0.0:
        rec["notes"].append("skipped: unknown licence")
        return rec
    ok, msg = recency_check(repo.get("pushed_at", ""), now, cfg)
    rec["checks"]["last push"] = msg
    if not ok:
        return rec
    base = f"https://{cfg['api_host']}/repos/{name}"
    try:
        _, h = fetch(base + "/commits?per_page=1", cfg)
        commits = last_page(h)
    except Exception:
        commits = None
    ok, msg = commits_check(rec["stars"], commits, cfg)
    rec["checks"]["commits"] = msg
    if not ok:
        return rec
    try:
        body, _ = fetch(base + "/issues?state=open&per_page=30", cfg)
        titles = [i.get("title", "") for i in json.loads(body) if "pull_request" not in i]
    except Exception:
        titles = []
    ok, msg = issues_check(titles, cfg)
    rec["checks"]["open issues"] = msg
    if not ok:
        return rec
    try:
        cb, ch = fetch(base + "/contributors?per_page=1&anon=1", cfg)
        n = last_page(ch)
        if n is None:
            n = len(json.loads(cb)) or None
    except Exception:
        n = None
    cok, msg = contributors_check(n)
    rec["checks"]["contributors"] = msg
    rec["score"] = round(lic_score + 1 + 1 + 1 + (1 if cok else 0), 1)     # 5 checks, 1 point each (licence counts 0.5 for ideas only)
    # read ONLY README text (+ up to N docs .md names listed by the API; their TEXT is read over the same API, never by following a link)
    texts: list[str] = []
    try:
        body, _ = fetch(base + "/readme", cfg, raw=True)
        texts.append(body.decode("utf-8", "replace")[: cfg["max_readme_bytes"]])
    except Exception:
        rec["notes"].append("no README text")
    try:
        body, _ = fetch(base + "/contents/docs", cfg)
        docs = [f["path"] for f in json.loads(body) if isinstance(f, dict) and f.get("type") == "file" and str(f.get("name", "")).lower().endswith((".md", ".txt"))][: cfg["max_doc_files"]]
        for path in docs:
            b, _ = fetch(f"{base}/contents/{urllib.parse.quote(path)}", cfg, raw=True)
            texts.append(b.decode("utf-8", "replace")[: cfg["max_readme_bytes"]])
    except Exception:
        pass
    text = "\n".join(texts)
    inj = injection_hits(text + "\n" + "\n".join(titles), cfg)
    if inj:
        rec["verdict"], rec["notes"] = "injection", [f"injection attempt in this repo's text: {', '.join(inj)}"]
        rec["ideas"] = []
        return rec
    rec["blocked"] = blocked_topics(text, cfg)
    rec["ideas"] = ideas_from(text, cfg)
    rec["verdict"] = "candidate" if rec["ideas"] else "skip"
    if not rec["ideas"]:
        rec["notes"].append("no idea from our catalog matched")
    return rec


# ---------------------------------------------------------------- queries
def week_queries(today: date, cfg: dict) -> list[tuple[str, str]]:
    """Rotate through the topics by ISO week so every topic comes round. Returns [(topic, query)]."""
    topics = list(cfg["query_topics"])
    wk = today.isocalendar()[1]
    out = []
    for i in range(cfg["queries_per_week"]):
        t = topics[(wk + i * 2) % len(topics)]
        qs = cfg["query_topics"][t]
        out.append((t, qs[(wk + i) % len(qs)]))
    return out


def search(query: str, cfg: dict, fetch) -> list[dict]:
    pushed_after = (datetime.now(timezone.utc) - timedelta(days=cfg["stale_days"])).strftime("%Y-%m-%d")
    q = urllib.parse.quote(f"{query} pushed:>{pushed_after} fork:false")
    body, _ = fetch(f"https://{cfg['api_host']}/search/repositories?q={q}&sort=updated&per_page={cfg['results_per_query']}", cfg)
    return json.loads(body).get("items", [])


# ---------------------------------------------------------------- the report
def render(today: date, queries, records: list[dict], cfg: dict) -> str:
    L = [f"# Repo Scout {today.isoformat()}", "",
         "MODE 1: propose only. Nothing here was applied. Nothing was cloned, installed or run. All text read from a repo is treated as untrusted data.", "",
         "Searched this week: " + "; ".join(f"{t} -> `{q}`" for t, q in queries), ""]
    cands = [r for r in records if r["verdict"] == "candidate"]
    inj = [r for r in records if r["verdict"] == "injection"]
    L += [f"Repos looked at: {len(records)}. Candidates: {len(cands)}. Skipped: {len(records) - len(cands) - len(inj)}. Injection attempts: {len(inj)}.", ""]
    L.append("## Proposals (for the owner; the machine applies none)")
    seen = {}
    for r in cands:
        for i in r["ideas"]:
            seen.setdefault(i["id"], {"idea": i, "repos": []})["repos"].append(r["repo"])
    if not seen:
        L.append("- none this week")
    for v in seen.values():
        i = v["idea"]
        L.append(f"- **{i['label']}** ({i['kind']}). Would touch: `{i['target']}` (on the ALLOW list). Seen in: {', '.join(v['repos'][:3])}")
    L += ["", "## Repos"]
    for r in sorted(records, key=lambda r: (r["verdict"] != "candidate", -r.get("score", 0))):
        chk = "; ".join(f"{k}: {v}" for k, v in r["checks"].items())
        L.append(f"- `{r['repo']}` ({r['stars']} stars, licence {r['license']}) -> **{r['verdict']}**" + (f", score {r['score']}/5" if "score" in r else ""))
        L.append(f"  - {chk}")
        for n in r["notes"]:
            L.append(f"  - {n}")
        if r["blocked"]:
            L.append(f"  - never applied (blocked topic): {', '.join(r['blocked'])}")
    if inj:
        L += ["", "## Injection attempts (logged, repo dropped)"] + [f"- injection attempt: `{r['repo']}`" for r in inj]
    return "\n".join(L) + "\n"


def can_write(rel: str, rules: dict) -> bool:
    kind, _ = guard.classify(rel, rules)
    return kind == "state"


def write_report(root: Path, today: date, text: str, rules: dict) -> str | None:
    rel = f"{OUT_DIR}/{today.isoformat()}.md"
    if not can_write(rel, rules):
        return None                                            # fail closed: the rule file does not allow this path (yet)
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8", newline="\n")
    return rel


def note(root: Path, msg: str, rules: dict, now: datetime) -> None:
    if not can_write(LOG, rules):
        return
    p = root / LOG
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8", newline="\n") as f:
        f.write(f"- {now.strftime('%Y-%m-%d %H:%M')} IST scout: {msg}\n")


def done_this_week(root: Path, today: date) -> bool:
    d = root / OUT_DIR
    if not d.exists():
        return False
    for f in d.glob("*.md"):
        try:
            if 0 <= (today - date.fromisoformat(f.stem)).days < 7:
                return True
        except ValueError:
            continue
    return False


def run(root: Path = ROOT, now: datetime | None = None, force: bool = False, fetch=api_get) -> dict:
    now = (now or datetime.now(IST)).astimezone(IST)
    out = {"status": "ok", "report": None}
    if guard.halted("trends", root):
        out["status"] = "halted"
        return out
    rules = guard.load_rules()                                 # raises RulesTampered: the machine stops
    cfg = load_config(root)
    if cfg.get("mode2_auto_apply"):
        note(root, "mode 2 (auto-apply) requested in scout_config.json: ignored, the scout has no apply code", rules, now)
    blk = guard.blocked_until(now, rules)
    if blk:
        out["status"] = f"waiting: {blk[1]} window"
        return out
    if not force and done_this_week(root, now.date()):
        out["status"] = "already done this week"
        return out
    queries = week_queries(now.date(), cfg)
    records, seen = [], set()
    for topic, q in queries:
        try:
            items = search(q, cfg, fetch)
        except Exception as e:
            note(root, f"search failed for '{q}': {type(e).__name__}", rules, now)
            continue
        for repo in items:
            n = repo.get("full_name")
            if not n or n in seen or len(records) >= cfg["max_repos_per_week"]:
                continue
            seen.add(n)
            try:
                records.append(evaluate(repo, cfg, fetch, now))
            except Exception as e:                             # one bad repo never stops the scout
                note(root, f"{n} could not be checked: {type(e).__name__}", rules, now)
    for r in records:
        if r["verdict"] == "injection":
            note(root, f"injection attempt in {r['repo']}: repo dropped", rules, now)
    rel = write_report(root, now.date(), render(now.date(), queries, records, cfg), rules)
    out["report"] = rel
    out["records"] = records
    if rel is None:
        out["status"] = "refused: RULES.json does not list autonomy/scout/*.md as a machine-notes file"
        note(root, out["status"], rules, now)
    return out


if __name__ == "__main__":
    res = run(force="--force" in sys.argv)
    print(res["status"], res.get("report") or "")
