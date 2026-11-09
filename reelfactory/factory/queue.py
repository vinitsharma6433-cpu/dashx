"""Connect the factory to the existing poster (repo vinitsharma6433-cpu/dashx, poster/queue.json).

    npm run queue                 queue the eligible ready reels (copies the video, appends entries, pushes to main)
    npm run queue -- --dry-run    show what would be queued, change nothing
    npm run queue -- --no-push    do everything except the push

It never changes poster/poster.py or the workflow, never runs the poster, never edits or deletes an existing queue entry
or an existing file in social/. The existing workflow posts an entry when its `when` time has passed, so a pushed entry
WILL be posted by it. Create a file named STOP_QUEUE in the project root to make this command do nothing.

A reel is queued only if ALL of these hold (otherwise the reason goes to output/reports/<date>.md):
  - dialogue format (older narration reels are skipped), QC score >= 90 and every QC check passes
  - the ready video is the one QC checked (same SHA256 as output/reels/<name>.mp4)
  - there is a <name>.seo.md and <name>.seo.json next to it
  - the title, yt_title, captions and every spoken line pass the DASHX word rules
    (no price, no "best / no.1 / premium / guaranteed", no other brand, no real person, no sensitive topic)
  - it was not queued before (queue.json, social/ and the local ledger factory/data/queued.json are all checked)
Slots: at most 2 reels per day, 12:30 and 20:30 IST, the next free ones; at most 14 per run.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from . import ROOT, log
from .config import DATA

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
CONFIG_FILE = ROOT / "queue_config.json"
STOP_FILE = ROOT / "STOP_QUEUE"
LEDGER = DATA / "queued.json"
READY = ROOT / "output" / "ready"
REPORTS = ROOT / "output" / "reports"
DEFAULTS = {
    "repo_dir": r"C:\Users\vinit\dashx-repo",
    "remote": "https://github.com/vinitsharma6433-cpu/dashx.git",
    "branch": "main",
    "pages_base": "https://vinitsharma6433-cpu.github.io/dashx/social/",
    "slots": ["12:30", "20:30"],
    "max_per_run": 14,
    "min_qc": 90,
    "lead_minutes": 30,       # a slot must be at least this far in the future
    "slot_tolerance_min": 30,  # an existing queue entry within this many minutes of a slot occupies it
    "networks": ["youtube"],
}


def load_config() -> dict:
    cfg = dict(DEFAULTS)
    if CONFIG_FILE.exists():
        cfg.update(json.loads(CONFIG_FILE.read_text(encoding="utf-8")))
    if os.environ.get("DASHX_REPO_DIR"):  # GitHub Actions: the checkout itself is the poster repo
        cfg["repo_dir"] = os.environ["DASHX_REPO_DIR"]
    return cfg


# ---- text checks ----------------------------------------------------------------------------------------------
_URL = re.compile(r"https?://\S+")


def banned_problems(text: str) -> list[str]:
    """DASHX word rules on one text. URLs are removed first (they may contain ids and query strings)."""
    from .bridge import story_rules  # noqa: PLC0415
    plain = _URL.sub(" ", text)
    plain = re.sub(r"(?im)^\s*(amazon|flipkart|meesho|mystore)\s*:\s*$", " ", plain)
    out = list(story_rules.rule_problems(plain))
    # words the poster owner listed explicitly (Roman spelling of the same claims)
    if re.search(r"(?i)\b(best|no\.?\s*1|number\s*one|premium|guarantee[sd]?|cheapest|lowest price)\b", plain):
        out.append("contains best / no.1 / premium / guaranteed")
    return sorted(set(out))


# ---- caption building -----------------------------------------------------------------------------------------
def youtube_title(seo_title: str) -> str:
    t = " ".join(seo_title.split())
    if len(t) < 60:
        return t
    cut = t[:57].rsplit(" ", 1)[0].rstrip("|,.-: ")
    return (cut or t[:57]) + "..."


def captions_for(hook: str) -> tuple[str, str]:
    """(youtube, instagram) captions from the reel's own hook, never dialogue lines."""
    from . import seo as seo_mod  # noqa: PLC0415
    return seo_mod.youtube_caption(hook), seo_mod.instagram_caption(hook)


def make_entry(name: str, seo: dict, when: str, cfg: dict, hook: str) -> dict:
    """Exactly the keys and order of the poster's existing entries (see the fake-cramp-talk entry), plus captions.instagram."""
    from . import seo as seo_mod  # noqa: PLC0415
    caption, insta = captions_for(hook)
    return {
        "title": f"{name} DASHX",
        "yt_title": youtube_title(seo["title"]),
        "media": f"{cfg['pages_base']}{name}.mp4",
        "when": when,
        "networks": list(cfg["networks"]),
        "caption": caption,
        "captions": {"youtube": caption, "instagram": insta, "facebook": insta},
        "comments": [seo_mod.first_comment()],  # posted by the poster right after the upload (YouTube cannot pin: pin it by hand)
        "status": "scheduled",
    }


# ---- slots -----------------------------------------------------------------------------------------------------
def free_slots(existing_whens: list[str], now: dt.datetime, cfg: dict, count: int) -> list[str]:
    """The next `count` free slots (ISO strings, IST). A slot is taken by any existing entry within the tolerance."""
    taken = []
    for w in existing_whens:
        try:
            taken.append(dt.datetime.fromisoformat(w))
        except ValueError:
            continue
    tol = dt.timedelta(minutes=cfg["slot_tolerance_min"])
    out: list[str] = []
    day = now.astimezone(IST).date()
    while len(out) < count and (day - now.astimezone(IST).date()).days < 400:
        for hhmm in cfg["slots"]:
            h, m = (int(x) for x in hhmm.split(":"))
            slot = dt.datetime(day.year, day.month, day.day, h, m, tzinfo=IST)
            if slot < now + dt.timedelta(minutes=cfg["lead_minutes"]):
                continue
            if any(abs(t - slot) <= tol for t in taken):
                continue
            taken.append(slot)
            out.append(slot.isoformat())
            if len(out) == count:
                break
        day += dt.timedelta(days=1)
    return out


# ---- candidates ------------------------------------------------------------------------------------------------
def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass
class Result:
    queued: list[dict] = field(default_factory=list)   # entries added
    skipped: list[tuple[str, str]] = field(default_factory=list)  # (reel, reason) it could be queued later
    blocked: list[tuple[str, list[str]]] = field(default_factory=list)  # (reel, reasons) failed a check
    old_format: int = 0
    pushed: bool = False
    note: str = ""


def check_reel(mp4: Path, queued_media: set[str], repo_social: Path, cfg: dict, inspector) -> tuple[bool, str, list[str], dict | None]:
    """(eligible, kind, reasons, seo). kind: 'old' (silently skipped), 'queued', 'blocked'."""
    name = mp4.stem
    script_file = ROOT / "reels" / name / "script.json"
    if not script_file.exists():
        return False, "old", [f"no reels/{name}/script.json"], None
    script = json.loads(script_file.read_text(encoding="utf-8"))
    if not script.get("dialogue_format"):
        return False, "old", ["older narration format"], None
    if f"{name}.mp4" in queued_media or (repo_social / f"{name}.mp4").exists():
        return False, "queued", ["already queued or already in social/"], None
    ledger = json.loads(LEDGER.read_text(encoding="utf-8")) if LEDGER.exists() else {}
    if name in ledger:
        return False, "queued", [f"already queued on {ledger[name].get('when')}"], None
    why: list[str] = []
    seo_json, seo_md = mp4.with_suffix(".seo.json"), mp4.with_suffix(".seo.md")
    if not seo_md.exists() or not seo_json.exists():
        return False, "blocked", ["no .seo.md / .seo.json next to the video"], None
    seo = json.loads(seo_json.read_text(encoding="utf-8"))
    src = ROOT / "output" / "reels" / f"{name}.mp4"
    if not src.exists() or sha256(src) != sha256(mp4):
        why.append("the ready video is not the file that was checked (output/reels/<name>.mp4 differs)")
    qc_res = inspector(name)
    if qc_res["score"] < cfg["min_qc"] or not qc_res["passed"]:
        why.append(f"QC {qc_res['score']} (needs >= {cfg['min_qc']} and no failed check): {[c['id'] for c in qc_res['failed']]}")
    from . import seo as seo_mod  # noqa: PLC0415
    hook = seo_mod.reel_hook(script)
    hook_why = seo_mod.hook_problems(hook, script)
    why += [f"hook: {p}" for p in hook_why]
    yt_cap, ig_cap = captions_for(hook or "")
    for field_name, text in (("title", seo.get("title", "")), ("yt_title", youtube_title(seo.get("title", ""))), ("youtube caption", yt_cap),
                             ("instagram caption", ig_cap), ("first comment", seo_mod.first_comment()),
                             ("story title", script.get("title", ""))):
        for p in banned_problems(text):
            why.append(f"{field_name}: {p}")
    for sc in script["scenes"]:
        for line in [d["line"] for d in sc.get("dialogue", [])] or [sc.get("voice", "")]:
            for p in banned_problems(line):
                why.append(f"spoken line '{line[:30]}': {p}")
    if not seo.get("title") or not script.get("title"):
        why.append("SEO title or story title is empty")
    seo = {**seo, "_hook": hook}
    return (not why), ("queued" if not why else "blocked"), why, seo


def ready_videos() -> list[Path]:
    return sorted(READY.glob("*/*.mp4"), key=lambda p: (p.parent.name, p.name)) if READY.exists() else []


# ---- queue.json (append only) ----------------------------------------------------------------------------------
def append_entries(text: str, entries: list[dict]) -> str:
    """Return queue.json text with the entries added at the end of "posts". Everything before them stays byte for byte."""
    nl = "\r\n" if "\r\n" in text else "\n"
    end = text.rstrip().rfind("]")
    if end == -1 or not text.rstrip().endswith("}"):
        raise ValueError("poster/queue.json does not have the expected shape")
    head = text[:end].rstrip()
    blocks = []
    for e in entries:
        body = json.dumps(e, indent=2, ensure_ascii=False).replace("\n", nl + "    ")
        blocks.append("    " + body)
    return head + "," + nl + ("," + nl).join(blocks) + nl + "  " + text[end:]


def verify_append_only(old_text: str, new_text: str, n_new: int) -> None:
    old, new = json.loads(old_text)["posts"], json.loads(new_text)["posts"]
    if new[: len(old)] != old or len(new) != len(old) + n_new:
        raise RuntimeError("safety stop: the new queue.json would change an existing entry")
    keep = old_text[: old_text.rstrip().rfind("]")].rstrip()
    if not new_text.startswith(keep):
        raise RuntimeError("safety stop: the existing part of queue.json changed")


# ---- git ---------------------------------------------------------------------------------------------------------
def git(repo: Path, *args: str, check: bool = True) -> str:
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GCM_INTERACTIVE": "never"}
    r = subprocess.run(["git", "-C", str(repo), "-c", "user.name=dashx-factory", "-c", "user.email=dashx-factory@users.noreply.github.com", *args],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, timeout=300)
    if check and r.returncode:
        raise RuntimeError(f"git {' '.join(args[:2])} failed: {(r.stderr or r.stdout).strip()[:300]}")
    return (r.stdout + r.stderr).strip()


def ensure_repo(cfg: dict) -> Path:
    repo = Path(cfg["repo_dir"])
    if not (repo / ".git").exists():
        subprocess.run(["git", "clone", "--depth", "1", "--branch", cfg["branch"], cfg["remote"], str(repo)], check=True, timeout=900)
    if not os.environ.get("DASHX_CI") and git(repo, "status", "--porcelain"):
        raise RuntimeError(f"{repo} has uncommitted changes; clean it first (this tool only uses it for the queue)")
    return repo


# ---- the run ---------------------------------------------------------------------------------------------------------
def write_report(res: Result, cfg: dict, dry: bool, now: dt.datetime) -> Path:
    REPORTS.mkdir(parents=True, exist_ok=True)
    path = REPORTS / f"{now.date().isoformat()}.md"
    lines = [f"## Queue run {now.strftime('%H:%M')} IST" + (" (dry run)" if dry else ""), ""]
    if res.note:
        lines += [res.note, ""]
    lines += [f"queued: {len(res.queued)}, blocked: {len(res.blocked)}, skipped (already queued): {len(res.skipped)}, older narration reels ignored: {res.old_format}", ""]
    for e in res.queued:
        lines.append(f"- QUEUED {e['title']} at {e['when']}: {e['yt_title']}")
    for name, why in res.blocked:
        lines.append(f"- NOT QUEUED {name}: " + "; ".join(why))
    for name, why in res.skipped:
        lines.append(f"- skipped {name}: {why}")
    if res.pushed:
        lines.append("- pushed to main")
    text = "\n".join(lines) + "\n\n"
    with open(path, "a", encoding="utf-8") as f:  # append: an earlier report of the day is never overwritten
        f.write(text)
    return path


def run(dry_run: bool = False, push: bool = True, inspector=None, now: dt.datetime | None = None, cfg: dict | None = None) -> Result:
    cfg = cfg or load_config()
    now = now or dt.datetime.now(IST)
    res = Result()
    if STOP_FILE.exists():
        res.note = "STOP_QUEUE exists in the project root: nothing was done."
        log.warn(res.note)
        return res
    if inspector is None:
        from . import qc  # noqa: PLC0415
        inspector = qc.inspect
    repo = ensure_repo(cfg)  # a clone used only for the queue (a dry run also updates this local clone, nothing else)
    git(repo, "checkout", cfg["branch"])
    git(repo, "pull", "--rebase", "--autostash", "origin", cfg["branch"])
    qfile = repo / "poster" / "queue.json"
    old_text = qfile.read_bytes().decode("utf-8")
    posts = json.loads(old_text)["posts"]
    queued_media = {p["media"].rsplit("/", 1)[-1] for p in posts}

    eligible: list[tuple[Path, dict]] = []
    for mp4 in ready_videos():
        if len(eligible) >= cfg["max_per_run"]:
            break
        ok, kind, why, seo = check_reel(mp4, queued_media, repo / "social", cfg, inspector)
        if ok:
            eligible.append((mp4, seo))
        elif kind == "old":
            res.old_format += 1
        elif kind == "queued":
            res.skipped.append((mp4.stem, why[0]))
        else:
            res.blocked.append((mp4.stem, why))
    # no two reels in one batch may share the same hook wording
    from .seo import hooks_clash  # noqa: PLC0415
    unique: list[tuple[Path, dict]] = []
    for mp4, seo in eligible:
        clash = next((m.stem for m, s2 in unique if hooks_clash(seo["_hook"], s2["_hook"])), None)
        if clash:
            res.blocked.append((mp4.stem, [f"hook is too close to the hook of {clash}; write a different one"]))
        else:
            unique.append((mp4, seo))
    eligible = unique
    when = free_slots([p["when"] for p in posts], now, cfg, len(eligible))
    entries = [make_entry(mp4.stem, seo, w, cfg, seo["_hook"]) for (mp4, seo), w in zip(eligible, when)]
    res.queued = entries
    if not entries or dry_run:
        res.note = "dry run: nothing was changed" if dry_run else ""
        write_report(res, cfg, dry_run, now)
        return res

    for (mp4, _), e in zip(eligible, entries):
        target = repo / "social" / mp4.name
        if target.exists():
            raise RuntimeError(f"{target} already exists; never overwritten")
        shutil.copy2(mp4, target)
    covers = [mp4.with_name(f"{mp4.stem}-cover.jpg") for mp4, _ in eligible]
    covers = [c for c in covers if c.exists() and not (repo / "social" / c.name).exists()]
    for c in covers:
        shutil.copy2(c, repo / "social" / c.name)
    new_text = append_entries(old_text, entries)
    verify_append_only(old_text, new_text, len(entries))
    qfile.write_bytes(new_text.encode("utf-8"))
    git(repo, "add", "poster/queue.json", *[f"social/{mp4.name}" for mp4, _ in eligible], *[f"social/{c.name}" for c in covers])
    git(repo, "commit", "-m", f"Factory: queue {len(entries)} reel(s)\n\n" + "\n".join(f"- {e['title']} at {e['when']}" for e in entries))
    if push:
        for attempt in range(3):
            try:
                git(repo, "pull", "--rebase", "--autostash", "origin", cfg["branch"])
                git(repo, "push", "origin", cfg["branch"])
                res.pushed = True
                break
            except RuntimeError as err:
                log.warn(f"push attempt {attempt + 1} failed: {err}")
                if attempt == 2:
                    res.note = f"committed locally but NOT pushed: {err}"
                    break
    ledger = json.loads(LEDGER.read_text(encoding="utf-8")) if LEDGER.exists() else {}
    for (mp4, _), e in zip(eligible, entries):
        ledger[mp4.stem] = {"when": e["when"], "pushed": res.pushed, "at": now.isoformat()}
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    LEDGER.write_text(json.dumps(ledger, indent=1), encoding="utf-8")
    write_report(res, cfg, dry_run, now)
    return res
