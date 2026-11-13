"""DASHX Autonomy, Phase 6: self-improvement loop. Standard library + the `git` and `gh` command line tools.

ONE small data change a day, made safely:
  1. read the signals (7 days of autonomy/log.md, learning.json, trends.json) and pick ONE improvement from the enabled improvers
  2. make it on a temporary branch (autonomy/improve-<date>-<idea>), never on main
  3. check the REAL git diff (not what the improver says) against the sealed rules: allow list, <= 3 files, small, not inside a slot window,
     not a second change today, no kill switch. Anything on the deny list => a pull request for the owner, never a merge.
  4. CANARY: the full unit tests + the story checks (no worse than main) + ONE test reel on the temp branch with no posting that must
     pass QC 100/100. Any failure => nothing is merged, the idea is blocked for 14 days.
  5. only if everything passed (and the rules still allow it at merge time): merge to main, remember the change, start the WATCH
  6. WATCH: the next 2 posted reels (and any scheduled factory run). A NEW failure (one the 4 reels before the merge did not have)
     => AUTO-REVERT, log why, block the idea for 14 days. 2 clean reels => the change stays.

It never edits RULES.json, guard.py, a workflow, poster/*, a secret or a kill switch (the guard refuses them). Kill switches win.
Every step is logged in autonomy/log.md. The git/gh parts are small classes so the whole flow is tested with real git in a temp repo.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import guard  # noqa: E402
import ladder  # noqa: E402
import trends as _trends  # noqa: E402

ROOT = guard.ROOT
IST = guard.IST
WATCH = "autonomy/watch.json"
BLOCKED = "autonomy/blocked_ideas.json"
LEDGER = "autonomy/changes.jsonl"
LOG = "autonomy/log.md"
SITUATIONS = "reelfactory/stories/situations.json"
BOT = ["-c", "user.name=dashx-autonomy", "-c", "user.email=dashx-autonomy@users.noreply.github.com"]


# ================================================================ git / gh
class Git:
    def __init__(self, repo: Path, main: str = "main", remote: str = "origin"):
        self.repo, self.main, self.remote = Path(repo), main, remote

    def run(self, *args: str, check: bool = True) -> str:
        r = subprocess.run(["git", *BOT, *args], cwd=self.repo, capture_output=True, text=True, encoding="utf-8")
        if check and r.returncode:
            raise RuntimeError(f"git {args[0]} failed: {(r.stderr or r.stdout).strip()[:200]}")
        return r.stdout.strip()

    def head(self, ref: str = "HEAD") -> str:
        return self.run("rev-parse", ref)

    def sync_main(self) -> None:
        self.run("checkout", self.main)
        self.run("pull", "--ff-only", "-q", self.remote, self.main)

    def branch_exists(self, name: str) -> bool:
        if self.run("branch", "--list", name):
            return True
        return bool(self.run("ls-remote", "--heads", self.remote, name, check=False))

    def new_branch(self, name: str) -> None:
        self.run("checkout", "-q", "-b", name, self.main)

    def commit(self, paths: list[str], msg: str) -> None:
        self.run("add", "--", *paths)
        self.run("commit", "-q", "-m", msg)

    def push_branch(self, name: str) -> None:
        self.run("push", "-q", self.remote, f"{name}:{name}")

    def changed_files(self, base: str, head: str) -> list[str]:
        return [x for x in self.run("diff", "--name-only", f"{base}...{head}").splitlines() if x]

    def diff_lines(self, base: str, head: str) -> int:
        n = 0
        for ln in self.run("diff", "--numstat", f"{base}...{head}").splitlines():
            a, b = ln.split("\t")[:2]
            n += (int(a) if a.isdigit() else 999) + (int(b) if b.isdigit() else 999)
        return n

    def merge_no_ff(self, branch: str, msg: str) -> str:
        self.run("checkout", "-q", self.main)
        self.run("merge", "--no-ff", "-q", "-m", msg, branch)
        return self.head()

    def revert_merge(self, sha: str, msg: str) -> str:
        self.run("checkout", "-q", self.main)
        self.run("revert", "-m", "1", "--no-edit", sha)
        self.run("commit", "--amend", "-q", "-m", msg)
        return self.head()

    def push_main(self) -> None:
        self.run("push", "-q", self.remote, self.main)

    def drop_branch(self, name: str) -> None:
        self.run("checkout", "-q", self.main, check=False)
        self.run("branch", "-D", name, check=False)
        self.run("push", "-q", self.remote, "--delete", name, check=False)

    def reset_main_to(self, sha: str) -> None:
        self.run("checkout", "-q", self.main)
        self.run("reset", "--hard", sha)


class GH:
    """The GitHub side: the canary test reel (the existing Reel Factory workflow in test_only mode on the temp branch) and pull requests."""
    def __init__(self, repo: Path, timeout_min: int = 45):
        self.repo, self.timeout = Path(repo), timeout_min

    def _gh(self, *args: str) -> str:
        r = subprocess.run(["gh", *args], cwd=self.repo, capture_output=True, text=True, encoding="utf-8", timeout=120)
        if r.returncode:
            raise RuntimeError(f"gh {args[0]} failed: {(r.stderr or r.stdout).strip()[:200]}")
        return r.stdout.strip()

    def canary_reel(self, branch: str, required_qc: int) -> tuple[bool, str]:
        t0 = datetime.now().astimezone()
        self._gh("workflow", "run", "dashx-reel-factory.yml", "--ref", branch, "-f", "count=1", "-f", "test_only=true")
        run_id = None
        deadline = time.time() + self.timeout * 60
        while time.time() < deadline:
            time.sleep(20)
            runs = json.loads(self._gh("run", "list", "--workflow", "dashx-reel-factory.yml", "--branch", branch, "--json", "databaseId,status,conclusion,createdAt", "-L", "5"))
            runs = [r for r in runs if datetime.fromisoformat(r["createdAt"].replace("Z", "+00:00")) >= t0 - timedelta(minutes=2)]
            if runs:
                run_id = runs[0]["databaseId"]
                if runs[0]["status"] == "completed":
                    if runs[0]["conclusion"] != "success":
                        return False, f"test reel run {run_id} ended {runs[0]['conclusion']}"
                    break
        else:
            return False, "test reel did not finish in time"
        with tempfile.TemporaryDirectory() as d:
            self._gh("run", "download", str(run_id), "-n", "factory-output", "-D", d)
            return qc_ok(Path(d), required_qc)


    def open_pr(self, branch: str, title: str, body: str) -> str:
        return self._gh("pr", "create", "--base", "main", "--head", branch, "--title", title, "--body", body)


def qc_ok(folder: Path, required: int) -> tuple[bool, str]:
    """Read output/ready/*/manifest.json of the downloaded test run: at least one reel and every QC score == required."""
    scores = []
    for mf in folder.rglob("manifest.json"):
        try:
            for e in json.loads(mf.read_text(encoding="utf-8")):
                if e.get("qc") is not None:
                    scores.append(e["qc"])
        except Exception:
            continue
    if not scores:
        return False, "no QC score found in the test run"
    return (all(s >= required for s in scores), f"QC scores {scores} (need {required})")


def run_checks(repo: Path, git: Git) -> tuple[bool, str]:
    """Unit tests and the story checker. The story checker must be NO WORSE than main (main may already have a failing old story)."""
    py = sys.executable
    t = subprocess.run([py, "-m", "unittest", "discover", "-s", "tests"], cwd=Path(repo) / "reelfactory", capture_output=True, text=True, encoding="utf-8", env={**__import__("os").environ, "PYTHONUTF8": "1"})
    if t.returncode:
        return False, "unit tests failed: " + (t.stderr.strip().splitlines() or ["?"])[-1][:120]

    def fails(cwd: Path) -> set[str]:
        r = subprocess.run([py, "scripts/check_dialogue_bank.py"], cwd=cwd, capture_output=True, text=True, encoding="utf-8", env={**__import__("os").environ, "PYTHONUTF8": "1"})
        return {ln.split("score")[0].replace("FAIL", "").strip() for ln in r.stdout.splitlines() if ln.startswith("FAIL")}
    here = fails(Path(repo) / "reelfactory")
    with tempfile.TemporaryDirectory() as d:
        git.run("worktree", "add", "-q", "--detach", d, git.main)
        try:
            base = fails(Path(d) / "reelfactory")
        finally:
            git.run("worktree", "remove", "--force", d, check=False)
    new = here - base
    return (not new, "story checks: no new failing story" if not new else f"story checks: new failing stories {sorted(new)}")


# ================================================================ state files (machine notes only)
def _rd(root: Path, rel: str, default):
    try:
        return json.loads((root / rel).read_text(encoding="utf-8"))
    except Exception:
        return default


def _wr(root: Path, rel: str, data) -> None:
    if guard.classify(rel, guard.load_rules())[0] != "state":
        raise PermissionError(f"{rel} is not a machine-notes file")
    (root / rel).parent.mkdir(parents=True, exist_ok=True)
    (root / rel).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def log(root: Path, now: datetime, name: str, why: str, result: str = "") -> None:
    p = root / LOG
    p.parent.mkdir(parents=True, exist_ok=True)
    if not p.exists():
        p.write_text("# DASHX Autonomy log\nOne line per fix or report. Written by the machine.\n\n", encoding="utf-8", newline="\n")
    with open(p, "a", encoding="utf-8", newline="\n") as f:
        f.write(f"- {now.strftime('%Y-%m-%d %H:%M')} IST | improve | {name} | {why} | {result}\n")


def blocked_ids(root: Path, now: datetime) -> set[str]:
    return {k for k, until in _rd(root, BLOCKED, {}).get("ideas", {}).items() if str(until) >= now.date().isoformat()}


def block_idea(root: Path, now: datetime, idea: str, days: int) -> None:
    b = _rd(root, BLOCKED, {"ideas": {}})
    b.setdefault("ideas", {})[idea] = (now + timedelta(days=days)).date().isoformat()
    _wr(root, BLOCKED, b)


# ================================================================ improvers (no model call)
@dataclass
class Proposal:
    idea: str
    why: str
    files: dict[str, str] = field(default_factory=dict)      # path -> new full text


def add_situation(text: str, new: str) -> str:
    """Append one string to the "situations" list of situations.json, keeping the file's own layout (one item per line)."""
    old = json.loads(text)
    i = text.index('"situations": [')
    j = text.index("]", i)
    body = text[i:j].rstrip()
    out = text[:i] + body + ",\n    " + json.dumps(new, ensure_ascii=False) + "\n  " + text[j:]
    chk = json.loads(out)
    if chk["situations"] != old["situations"] + [new] or {k: v for k, v in chk.items() if k != "situations"} != {k: v for k, v in old.items() if k != "situations"}:
        raise ValueError("situations.json edit changed more than the one new line")
    return out


def situation_from_trend(root: Path, rules: dict, now: datetime, blocked: set[str]) -> Proposal | None:
    """Add today's best SAFE trend situation (our own pre-written, brand-checked text from trend_themes.json / festivals.json) to the seeds."""
    trends = _rd(root, "autonomy/trends.json", {})
    try:
        text = (root / SITUATIONS).read_text(encoding="utf-8")
        have = [s.lower() for s in json.loads(text)["situations"]]
    except Exception:
        return None
    if len(have) >= rules["improve"]["max_situations"]:
        return None
    for t in sorted(trends.get("topics", []), key=lambda t: (-float(t.get("strength", 0)), t.get("id", ""))):
        sit = str(t.get("story_situation", "")).strip()
        idea = f"situation:{t.get('id')}"
        if not sit or idea in blocked or sit.lower() in have or str(t.get("expires", "")) < now.date().isoformat():
            continue
        if not _trends.is_safe_headline(sit, rules) or not _trends.brand_ok(sit, rules) or len(sit) > 120:
            continue
        return Proposal(idea, f"add the trend situation '{t.get('topic')}' to the story seeds", {SITUATIONS: add_situation(text, sit)})
    return None


IMPROVERS = {"situation_from_trend": situation_from_trend}


def unstable(log_text: str, now: datetime) -> str:
    """Do not change anything while the machine is unwell: a revert in the last 3 days or failing poster runs in the last 2 days."""
    for ln in log_text.splitlines():
        m = re.match(r"- (\d{4}-\d\d-\d\d \d\d:\d\d) IST \| (\w+) \| (\w+) \|", ln)
        if not m:
            continue
        ts = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M").replace(tzinfo=IST)
        if m.group(3) == "auto_revert" and now - ts < timedelta(days=3):
            return "a change was reverted in the last 3 days"
        if m.group(3) == "poster_runs_failing" and now - ts < timedelta(days=2):
            return "the poster runs were failing in the last 2 days"
    return ""


# ================================================================ the daily step
def improve_step(root: Path, now: datetime, rules: dict, git: Git, gh, checks, now_fn, dry: bool = False) -> str:
    probe = guard.check_change([SITUATIONS], now, root, rules)
    if not probe.ok:
        if probe.wait_until:
            log(root, now, "wait", probe.reasons[0], f"try again after {probe.wait_until.strftime('%H:%M')} IST")
            return "wait"
        log(root, now, "skip", "; ".join(probe.reasons), "no change today")
        return "limit"
    why_not = unstable((root / LOG).read_text(encoding="utf-8") if (root / LOG).exists() else "", now)
    if why_not:
        log(root, now, "skip", f"machine is unstable: {why_not}", "no change today")
        return "unstable"
    blocked = blocked_ids(root, now)
    prop = None
    for name in rules["improve"]["improvers_enabled"]:
        fn = IMPROVERS.get(name)
        prop = fn(root, rules, now, blocked) if fn else None
        if prop:
            break
    if not prop:
        log(root, now, "skip", "no safe improvement idea today", "")
        return "no_idea"
    if dry:
        log(root, now, "dry", prop.why, "nothing changed")
        return "dry"
    base_name = f"{rules['improve']['branch_prefix']}{now.strftime('%Y%m%d')}-{re.sub(r'[^a-z0-9]+', '-', prop.idea.lower()).strip('-')}"
    branch = base_name
    try:
        git.sync_main()
        before = git.head()
        n = 2
        while git.branch_exists(branch):                          # an earlier branch (e.g. one kept for a pull request) must never crash today's run
            branch, n = f"{base_name}-{n}", n + 1
        git.new_branch(branch)
    except Exception as e:
        log(root, now, "error", f"{prop.idea}: could not prepare the branch ({type(e).__name__}: {str(e)[:100]})", "nothing changed")
        return "error"
    try:
        for rel, content in prop.files.items():
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            (root / rel).write_text(content, encoding="utf-8", newline="\n")
        git.commit(list(prop.files), f"Autonomy self-improvement: {prop.why}")
        changed = git.changed_files(git.main, branch)
        lines = git.diff_lines(git.main, branch)
        d = guard.check_change(changed, now, root, rules)           # the REAL diff decides
        if d.needs_human:
            git.push_branch(branch)
            url = gh.open_pr(branch, f"DASHX autonomy: {prop.why}", "Needs the owner: " + "; ".join(d.reasons))
            log(root, now, "pr_for_owner", f"{prop.why}: {'; '.join(d.reasons)}", url)
            git.run("checkout", "-q", git.main)
            return "pr"
        if not d.ok or lines > rules["improve"]["max_diff_lines"]:
            log(root, now, "refused", f"{prop.why}: {'; '.join(d.reasons) or str(lines) + ' changed lines, too big'}", "nothing merged")
            git.drop_branch(branch)
            return "refused"
        git.push_branch(branch)
        ok, detail = checks(root, git)
        if not ok:
            log(root, now, "canary_failed", f"{prop.idea}: {detail}", "nothing merged; idea blocked 14 days")
            block_idea(root, now, prop.idea, rules["limits"]["blocked_idea_days"])
            git.drop_branch(branch)
            return "canary_failed"
        ok, detail = gh.canary_reel(branch, rules["improve"]["canary"]["required_qc"])
        if not ok:
            log(root, now, "canary_failed", f"{prop.idea}: test reel: {detail}", "nothing merged; idea blocked 14 days")
            block_idea(root, now, prop.idea, rules["limits"]["blocked_idea_days"])
            git.drop_branch(branch)
            return "canary_failed"
        now2 = now_fn()                                             # time has passed: ask the rules again right before the merge
        d2 = guard.check_change(changed, now2, root, rules)
        if not d2.ok:
            log(root, now2, "refused_late", f"{prop.idea}: {'; '.join(d2.reasons)}", "nothing merged; branch removed, tries again another day")
            git.drop_branch(branch)
            return "refused_late"
        git.sync_main()
        if git.head() != before:
            git.run("checkout", "-q", branch)
            git.run("rebase", "-q", git.main)                       # main moved (poster checkpoints): replay the one small commit on top
        sha = git.merge_no_ff(branch, f"Autonomy self-improvement merged: {prop.why}")
        try:
            git.push_main()
        except Exception as e:
            git.reset_main_to(before)
            log(root, now2, "merge_failed", f"{prop.idea}: could not push main ({type(e).__name__})", "reset; nothing changed")
            git.drop_branch(branch)
            return "push_failed"
        guard.record_change(changed, now2, note=prop.idea, root=root)
        _wr(root, WATCH, {"status": "watching", "idea": prop.idea, "why": prop.why, "merge_sha": sha, "before_sha": before, "files": changed,
                          "merged_at": now2.isoformat(timespec="seconds"), "need_reels": rules["improve"]["watch"]["reels"]})
        log(root, now2, "merged", prop.why, f"{sha[:8]}; canary: {detail}; watching the next {rules['improve']['watch']['reels']} reels")
        git.commit([WATCH, LEDGER, LOG], "Autonomy: watch started")
        git.push_main()
        git.drop_branch(branch)
        return "merged"
    except Exception as e:
        log(root, now, "error", f"{prop.idea}: {type(e).__name__}: {str(e)[:120]}", "branch removed")
        git.drop_branch(branch)
        return "error"


# ================================================================ the watch
def _err_class(err: str) -> str:
    e = (err or "").lower()
    for key in ("token", "timeout", "permission", "quota", "processing", "not public"):
        if key in e:
            return key
    m = re.search(r"http (\d{3})", e)
    return f"http{m.group(1)}" if m else "other"


def signatures(post: dict) -> set[tuple]:
    out = set()
    for net, r in post.get("results", {}).items():
        if not r.get("ok") and not r.get("skipped_late"):
            out.add((net, _err_class(str(r.get("error", "")))))
    for key, v in post.get("notes", {}).items():
        if key.endswith("_comment") and isinstance(v, list) and v and v != ["ok"]:
            out.add((key, "comment_failed"))
    return out


def settled(post: dict) -> bool:
    res = post.get("results", {})
    return all(n in res and "ok" in res[n] for n in post.get("networks", []))


def watch_step(root: Path, now: datetime, rules: dict, git: Git, factory_runs: list[dict]) -> str:
    w = _rd(root, WATCH, {})
    if w.get("status") != "watching":
        return "idle"
    merged = datetime.fromisoformat(w["merged_at"])
    posts = sorted(_rd(root, "poster/queue.json", {"posts": []}).get("posts", []), key=lambda p: p.get("when", ""))
    due = lambda p: datetime.fromisoformat(p["when"])                  # noqa: E731
    before = [p for p in posts if due(p) < merged][-4:]
    after = [p for p in posts if merged <= due(p) <= now][: w["need_reels"]]
    base = set().union(*[signatures(p) for p in before]) if before else set()
    bad = []
    for p in after:
        new = signatures(p) - base
        if new or (not settled(p) and now - due(p) > timedelta(hours=3)):
            bad.append(f"{p['title']}: {sorted(new) or 'did not settle'}")
    ok_before = next((r for r in factory_runs if r["created"] < merged and r["event"] == "schedule"), None)
    for r in factory_runs:
        if r["created"] >= merged and r["event"] == "schedule" and r["conclusion"] == "failure" and (ok_before is None or ok_before["conclusion"] == "success"):
            bad.append(f"Reel Factory run {r['id']} failed after the change")
    if bad:
        return revert(root, now, rules, git, w, "; ".join(bad))
    if len(after) >= w["need_reels"] and all(settled(p) for p in after):
        w.update(status="done", closed_at=now.isoformat(timespec="seconds"))
        _wr(root, WATCH, w)
        log(root, now, "watch_ok", f"{w['idea']}: the next {len(after)} reels were clean", "change stays")
        return "watch_ok"
    if now - merged > timedelta(days=rules["improve"]["watch"]["give_up_days"]):
        w.update(status="done", closed_at=now.isoformat(timespec="seconds"), note="fewer than 2 reels posted in 5 days; no failure seen")
        _wr(root, WATCH, w)
        log(root, now, "watch_ok", f"{w['idea']}: only {len(after)} reels in 5 days, no failure", "change stays")
        return "watch_ok"
    return "watching"


def revert(root: Path, now: datetime, rules: dict, git: Git, w: dict, why: str) -> str:
    """AUTO-REVERT. Allowed even inside a blocked window (it undoes a change), but only for the files the change itself touched."""
    try:
        touched = git.changed_files(f"{w['merge_sha']}^1", w["merge_sha"])
        bad = [f for f in touched if guard.classify(f, rules)[0] not in ("allow", "state")]
        if bad or sorted(touched) != sorted(w.get("files", touched)):
            log(root, now, "auto_revert_refused", f"{w['idea']}: the merge touched unexpected files {bad or touched}", "owner must look")
            w.update(status="revert_refused", reason=why)
            _wr(root, WATCH, w)
            return "revert_refused"
        git.sync_main()
        sha = git.revert_merge(w["merge_sha"], f"Autonomy auto-revert: {w['idea']} ({why[:100]})")
        w.update(status="reverted", reason=why, revert_sha=sha, closed_at=now.isoformat(timespec="seconds"))
        _wr(root, WATCH, w)
        block_idea(root, now, w["idea"], rules["limits"]["blocked_idea_days"])
        log(root, now, "auto_revert", f"{w['idea']}: {why[:200]}", f"reverted as {sha[:8]}; idea blocked 14 days")
        git.commit([WATCH, BLOCKED, LOG], "Autonomy: revert logged")
        git.push_main()
        return "reverted"
    except Exception as e:
        log(root, now, "auto_revert_failed", f"{w.get('idea')}: {type(e).__name__}: {str(e)[:120]}", "owner must look")
        try:
            git.run("revert", "--abort", check=False)
            w.update(status="revert_failed", reason=why)
            _wr(root, WATCH, w)
        except Exception:
            pass
        return "revert_failed"


# ================================================================ entry
def run(root: Path = ROOT, now: datetime | None = None, git: Git | None = None, gh=None, checks=None, factory_runs=None,
        watch_only: bool = False, dry: bool = False, now_fn=None) -> str:
    now_fn = now_fn or (lambda: datetime.now(IST))
    now = (now or now_fn()).astimezone(IST)
    stop = guard.halted("self_change", root)
    if stop:
        print(f"{stop} is on: self-improvement does nothing")
        return "halted"
    rules = guard.load_rules()
    git = git or Git(root)
    w = _rd(root, WATCH, {})
    if w.get("status") == "watching":
        return watch_step(root, now, rules, git, factory_runs() if callable(factory_runs) else (factory_runs or []))
    if watch_only:
        return "idle"
    step = ladder.current_step(root)                  # Trust Ladder: self-improvement is OFF on step 1 (watching an existing change above is never blocked)
    if step < 2:
        log(root, now, "ladder", "self-improvement is OFF at Trust Ladder step 1 (needs the first run + 2 clean reels)", "waiting")
        return "ladder_step1"
    return improve_step(root, now, rules, git, gh or GH(root, rules["improve"]["canary"]["timeout_minutes"]), checks or run_checks, now_fn, dry)


def _factory_runs(root: Path) -> list[dict]:
    try:
        r = subprocess.run(["gh", "run", "list", "--workflow", "dashx-reel-factory.yml", "--json", "databaseId,conclusion,event,createdAt", "-L", "10"],
                           cwd=root, capture_output=True, text=True, encoding="utf-8", timeout=60)
        return [{"id": x["databaseId"], "conclusion": x["conclusion"], "event": x["event"],
                 "created": datetime.fromisoformat(x["createdAt"].replace("Z", "+00:00")).astimezone(IST)} for x in json.loads(r.stdout)]
    except Exception:
        return []


if __name__ == "__main__":
    try:
        out = run(watch_only="--watch-only" in sys.argv, dry="--dry" in sys.argv, factory_runs=lambda: _factory_runs(ROOT))
    except guard.RulesTampered as e:
        print(f"::error::RULES TAMPERED ({e}). Self-improvement stopped.")
        sys.exit(1)
    print("improve:", out)
