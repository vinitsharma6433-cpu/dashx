"""Operations: single-instance lock, STOP flag, disk usage, and SAFE cleanup. Finished videos, reel scripts,
stories, assets, source and backups are protected: nothing in this package deletes them."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

from . import ROOT
from .config import DATA

LOCK = DATA / "run.lock"
STOP = DATA / "STOP"
PROTECTED = [ROOT / p for p in ("output", "reels", "stories", "assets", "fonts", "src", "scripts", "factory", "backups", "tools", "tests", "docs", "evidence")]
DELETABLE = [DATA / "tmp", ROOT / "public" / "_reel"]  # the only places cleanup may touch


def pid_alive(pid: int) -> bool:
    if pid == os.getpid():
        return True
    r = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True)
    return str(pid) in r.stdout


def acquire_lock(max_age_h: float = 8.0) -> bool:
    """Only one production run at a time. A lock left by a crashed run (dead PID or older than 8 h) is taken over."""
    DATA.mkdir(parents=True, exist_ok=True)
    if LOCK.exists():
        try:
            info = json.loads(LOCK.read_text(encoding="utf-8"))
            if pid_alive(int(info["pid"])) and time.time() - info["ts"] < max_age_h * 3600:
                return False
        except Exception:
            pass
    LOCK.write_text(json.dumps({"pid": os.getpid(), "ts": time.time()}), encoding="utf-8")
    return True


def release_lock() -> None:
    try:
        info = json.loads(LOCK.read_text(encoding="utf-8"))
        if info.get("pid") == os.getpid():
            LOCK.unlink()
    except Exception:
        pass


def lock_info() -> dict | None:
    try:
        info = json.loads(LOCK.read_text(encoding="utf-8"))
        return {"pid": info["pid"], "alive": pid_alive(int(info["pid"])), "age_min": round((time.time() - info["ts"]) / 60, 1)}
    except Exception:
        return None


def stop_requested() -> bool:
    return STOP.exists()


def set_stop(on: bool) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    if on:
        STOP.write_text(str(time.time()), encoding="utf-8")
    elif STOP.exists():
        STOP.unlink()


def dir_mb(p: Path) -> float:
    return round(sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) / 1e6, 1) if p.exists() else 0.0


def disk() -> dict:
    u = shutil.disk_usage(ROOT)
    return {"free_gb": round(u.free / 1e9, 1), "ready_mb": dir_mb(ROOT / "output" / "ready"), "reels_mb": dir_mb(ROOT / "reels"),
            "logs_mb": dir_mb(ROOT / "logs"), "backups_mb": dir_mb(ROOT / "backups"), "tmp_mb": dir_mb(DATA / "tmp")}


def is_protected(path: Path) -> bool:
    p = path.resolve()
    if any(p == d.resolve() or d.resolve() in p.parents for d in PROTECTED):
        return True
    return not any(d.resolve() in p.parents for d in DELETABLE)  # anything outside the deletable folders is off limits


def safe_delete(path: Path) -> bool:
    if is_protected(path) or not path.exists():
        return False
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()
    return True


def cleanup(older_than_days: float = 2.0) -> dict:
    """Remove old temporary files (thumbnail candidates, copied reel assets). Returns what was freed."""
    cutoff, freed, n = time.time() - older_than_days * 86400, 0, 0
    for root in DELETABLE:
        if not root.exists():
            continue
        for f in list(root.rglob("*")):
            if f.is_file() and f.stat().st_mtime < cutoff:
                size = f.stat().st_size
                if safe_delete(f):
                    freed += size
                    n += 1
    return {"files_deleted": n, "mb_freed": round(freed / 1e6, 2)}
