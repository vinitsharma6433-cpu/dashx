"""DASHX Autonomy guard: the ONLY place that decides whether the machine may make a change. Standard library only.

The rule file autonomy/RULES.json is law. This module reads it and enforces it:
  - the rule file is sealed (autonomy/RULES.sha256). If it does not match, the machine stops (RulesTampered). Only the owner re-seals it.
  - default DENY: a path that is not in `allow` or `state_files` may not be changed by the machine.
  - DENY paths (secrets, poster, workflows, the rule file, this file, kill switches, ...) are never changed by the machine; the change becomes a pull request for the owner.
  - limits: 1 self-change a day (IST), at most 3 files, nothing inside the 90 minutes before a slot.
  - kill switches STOP_AUTONOMY / STOP_QUEUE / STOP_POSTER / STOP_REFILL always win.

Nothing here writes to RULES.json, RULES.sha256, guard.py or a kill switch. `seal` is a command for the OWNER to run by hand.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RULES_PATH = ROOT / "autonomy" / "RULES.json"
SEAL_PATH = ROOT / "autonomy" / "RULES.sha256"
LEDGER = "autonomy/changes.jsonl"
IST = timezone(timedelta(hours=5, minutes=30))   # India has no daylight saving


class RulesTampered(Exception):
    """RULES.json is missing, unreadable or does not match RULES.sha256. The machine must stop and raise an alert."""


# ---------------------------------------------------------------- the rule file
def _norm_bytes(b: bytes) -> bytes:
    return b.replace(b"\r\n", b"\n")


def digest(path: Path | None = None) -> str:
    return hashlib.sha256(_norm_bytes((path or RULES_PATH).read_bytes())).hexdigest()


def load_rules(rules_path: Path | None = None, seal_path: Path | None = None) -> dict:
    """The rules, only when they match the seal. Raises RulesTampered otherwise (never returns a guess)."""
    rules_path, seal_path = rules_path or RULES_PATH, seal_path or SEAL_PATH
    try:
        want = seal_path.read_text(encoding="utf-8").split()[0].strip().lower()
        if digest(rules_path) != want:
            raise RulesTampered("RULES.json does not match RULES.sha256")
        return json.loads(rules_path.read_text(encoding="utf-8"))
    except RulesTampered:
        raise
    except Exception as e:
        raise RulesTampered(f"rule file unreadable: {type(e).__name__}") from e


def seal(rules_path: Path | None = None, seal_path: Path | None = None) -> str:
    """OWNER ONLY (run by hand). The machine never calls this."""
    rules_path, seal_path = rules_path or RULES_PATH, seal_path or SEAL_PATH
    d = digest(rules_path)
    seal_path.write_text(d + "  RULES.json\n", encoding="utf-8", newline="\n")
    return d


# ---------------------------------------------------------------- paths
def normalize(path: str) -> str | None:
    """A clean repo-relative posix path, or None when the path is unsafe (absolute, '..', drive, stream, empty)."""
    if not isinstance(path, str) or not path.strip():
        return None
    p = path.replace("\\", "/").strip()
    if p.startswith("/") or re.match(r"^[A-Za-z]:", p) or ":" in p or "\x00" in p:
        return None
    parts = []
    for seg in p.split("/"):
        seg = seg.rstrip(" .") if seg not in (".", "..") else seg   # Windows ignores trailing dots/spaces
        if seg in ("", "."):
            continue
        if seg == "..":
            return None
        parts.append(seg)
    return "/".join(parts) or None


def _glob_re(pattern: str) -> re.Pattern:
    out, i = "", 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out += "(?:.*/)?"; i += 3
        elif pattern.startswith("**", i):
            out += ".*"; i += 2
        elif pattern[i] == "*":
            out += "[^/]*"; i += 1
        elif pattern[i] == "?":
            out += "[^/]"; i += 1
        else:
            out += re.escape(pattern[i]); i += 1
    return re.compile("^" + out + "$", re.I)   # case-insensitive: Windows paths are


def _match(path: str, patterns: list[str]) -> bool:
    return any(_glob_re(p).match(path) for p in patterns)


def _allow_paths(rules: dict) -> list[str]:
    return sorted({p for k, v in rules.get("allow", {}).items() if isinstance(v, list) for p in v})


def _extraction_paths(rules: dict) -> list[str]:
    return sorted({p for k, v in rules.get("allow_after_owner_extraction", {}).items() if isinstance(v, list) for p in v})


def classify(path: str, rules: dict) -> tuple[str, str]:
    """('deny' | 'extract' | 'state' | 'allow', reason). DENY wins over everything; unknown paths are denied."""
    p = normalize(path)
    if p is None:
        return "deny", "unsafe path"
    if _match(p, rules["deny"]["paths"]):
        return "deny", "protected path"
    if _match(p, rules["state_files"]["paths"]):
        return "state", "machine notes"
    if _match(p, _allow_paths(rules)):
        return "allow", "allowed"
    if _match(p, _extraction_paths(rules)):
        return "extract", "code file that also holds safety checks; needs owner extraction first"
    return "deny", "not in the allow list (default deny)"


# ---------------------------------------------------------------- kill switches
SCOPES = {
    "all": ("STOP_AUTONOMY",),
    "self_change": ("STOP_AUTONOMY", "STOP_QUEUE"),
    "refill": ("STOP_AUTONOMY", "STOP_QUEUE", "STOP_REFILL"),
    "poster": ("STOP_AUTONOMY", "STOP_POSTER"),
    "trends": ("STOP_AUTONOMY",),
}


def halted(scope: str = "all", root: Path = ROOT) -> str | None:
    """The name of the kill switch that stops this scope, or None. Looks in the repo root and in reelfactory/."""
    for name in SCOPES.get(scope, SCOPES["all"]):
        if (root / name).exists() or (root / "reelfactory" / name).exists():
            return name
    return None


# ---------------------------------------------------------------- the ledger (one line per self-change)
def _read_ledger(root: Path) -> list[dict]:
    out = []
    try:
        for ln in (root / LEDGER).read_text(encoding="utf-8").splitlines():
            try:
                out.append(json.loads(ln))
            except Exception:
                continue
    except Exception:
        pass
    return out


def record_change(files: list[str], now: datetime | None = None, note: str = "", root: Path = ROOT) -> None:
    """Remember a self-change so the daily limit can count it. Writes only autonomy/changes.jsonl (a state file)."""
    now = (now or datetime.now(IST)).astimezone(IST)
    p = root / LEDGER
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps({"ts": now.isoformat(), "files": files, "note": note}, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------- the decision
@dataclass
class Decision:
    ok: bool
    reasons: list[str] = field(default_factory=list)
    needs_human: bool = False            # touches DENY / unknown: open a PR for the owner instead
    wait_until: datetime | None = None   # inside a blocked window: try again at this time
    state_only: bool = False


def _hm(s: str) -> tuple[int, int]:
    h, m = s.split(":")
    return int(h), int(m)


def blocked_until(now: datetime, rules: dict) -> tuple[datetime, str] | None:
    """If `now` (IST) is inside a blocked window return (when it ends, window name)."""
    now = now.astimezone(IST)
    for w in rules["limits"]["blocked_windows_ist"]:
        a = now.replace(hour=_hm(w["from"])[0], minute=_hm(w["from"])[1], second=0, microsecond=0)
        b = now.replace(hour=_hm(w["to"])[0], minute=_hm(w["to"])[1], second=0, microsecond=0)
        if a <= now <= b:                       # both ends are blocked
            return b + timedelta(minutes=1), w["name"]
    return None


def check_change(paths: list[str], now: datetime | None = None, root: Path = ROOT,
                 rules: dict | None = None) -> Decision:
    """May the machine change these files right now? Never raises: a broken rule file is a refusal."""
    try:
        rules = rules or load_rules()
    except RulesTampered as e:
        return Decision(False, [f"RULES TAMPERED: {e}. Machine stopped."], needs_human=True)
    now = (now or datetime.now(IST)).astimezone(IST)
    stop = halted("self_change", root)
    if stop:
        return Decision(False, [f"kill switch {stop} is on"])
    if not paths:
        return Decision(False, ["no files given"])
    kinds = [(p, *classify(p, rules)) for p in paths]
    bad = [(p, why) for p, k, why in kinds if k in ("deny", "extract")]
    if bad:
        return Decision(False, [f"{p}: {why}" for p, why in bad], needs_human=True)
    real = [p for p, k, _ in kinds if k == "allow"]
    if not real:                                 # only machine notes: always fine, no limits
        return Decision(True, ["machine notes only"], state_only=True)
    reasons: list[str] = []
    if len(real) > rules["limits"]["max_files_per_change"]:
        reasons.append(f"{len(real)} files, the limit is {rules['limits']['max_files_per_change']} per change")
    today = now.date().isoformat()
    done = [e for e in _read_ledger(root) if str(e.get("ts", ""))[:10] == today]
    if len(done) >= rules["limits"]["max_self_changes_per_day"]:
        reasons.append(f"already {len(done)} self-change today (IST), the limit is {rules['limits']['max_self_changes_per_day']}")
    if reasons:
        return Decision(False, reasons)
    win = blocked_until(now, rules)
    if win:
        return Decision(False, [f"inside the blocked window before {win[1]}"], wait_until=win[0])
    return Decision(True, ["allowed"])


if __name__ == "__main__":
    if sys.argv[1:] == ["seal"]:
        print("sealed:", seal())          # OWNER ONLY
    elif sys.argv[1:] == ["verify"]:
        try:
            load_rules(); print("rules OK")
        except RulesTampered as e:
            print("TAMPERED:", e); sys.exit(1)
    else:
        print("usage: python autonomy/guard.py seal | verify")
