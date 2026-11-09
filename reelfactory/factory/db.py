"""Persistent production database (SQLite, factory/data/factory.db). It remembers stories, jobs, stage timings,
failures, repairs, scores, SEO, uploads and feedback. Past results feed back into the next run
(character balance, template failure rates) but nothing here ever changes production CODE."""

from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager

from .config import DATA

DB_FILE = DATA / "factory.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs(id INTEGER PRIMARY KEY, day TEXT, requested INTEGER, source TEXT, started TEXT,
  finished TEXT, status TEXT, note TEXT);
CREATE TABLE IF NOT EXISTS jobs(id INTEGER PRIMARY KEY, run_id INTEGER, name TEXT, day TEXT, status TEXT, stage TEXT,
  title TEXT, plot TEXT, source TEXT, cast_json TEXT, category TEXT, story_score REAL, qc_score REAL, seo_score REAL,
  duration_s REAL, repairs INTEGER DEFAULT 0, error TEXT, started TEXT, finished TEXT, seconds REAL);
CREATE TABLE IF NOT EXISTS stages(id INTEGER PRIMARY KEY, job_id INTEGER, stage TEXT, status TEXT, seconds REAL, detail TEXT, ts TEXT);
CREATE TABLE IF NOT EXISTS stories(id INTEGER PRIMARY KEY, name TEXT UNIQUE, title TEXT, plot TEXT, closing TEXT,
  category TEXT, cast_json TEXT, templates TEXT, score REAL, approved INTEGER, source TEXT, created TEXT);
CREATE TABLE IF NOT EXISTS failures(id INTEGER PRIMARY KEY, job_id INTEGER, check_id TEXT, stage TEXT, detail TEXT, ts TEXT);
CREATE TABLE IF NOT EXISTS repairs(id INTEGER PRIMARY KEY, job_id INTEGER, attempt INTEGER, action TEXT, result TEXT, ts TEXT);
CREATE TABLE IF NOT EXISTS uploads(id INTEGER PRIMARY KEY, job_id INTEGER, video_id TEXT, status TEXT, scheduled_at TEXT, detail TEXT, ts TEXT);
CREATE TABLE IF NOT EXISTS feedback(id INTEGER PRIMARY KEY, job_id INTEGER, rating INTEGER, note TEXT, ts TEXT);
"""


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


@contextmanager
def conn():
    DATA.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB_FILE, timeout=30)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.executescript(SCHEMA)
    try:
        yield c
        c.commit()
    finally:
        c.close()


SNAPSHOTS = DATA / "snapshots"


def integrity() -> tuple[bool, str]:
    """PRAGMA integrity_check on the live database. A missing file is fine (it will be created)."""
    if not DB_FILE.exists():
        return True, "no database yet"
    try:
        c = sqlite3.connect(DB_FILE, timeout=30)
        try:
            row = c.execute("PRAGMA integrity_check").fetchone()
        finally:
            c.close()
        return (row[0] == "ok"), str(row[0])
    except sqlite3.DatabaseError as e:
        return False, f"{type(e).__name__}: {e}"


def snapshot(keep: int = 7) -> Path | None:
    """Consistent copy of the database (SQLite backup API, safe while WAL is active). Old snapshots are rotated."""
    if not DB_FILE.exists():
        return None
    SNAPSHOTS.mkdir(parents=True, exist_ok=True)
    out = SNAPSHOTS / f"factory-{time.strftime('%Y%m%d-%H%M%S')}.db"
    src, dst = sqlite3.connect(DB_FILE, timeout=30), sqlite3.connect(out)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    for old in sorted(SNAPSHOTS.glob("factory-*.db"))[:-keep]:
        old.unlink()
    return out


def ensure_healthy() -> dict:
    """Detect a damaged database. The damaged file is KEPT (renamed *.corrupt-<time>), the newest healthy snapshot is restored;
    with no usable snapshot a fresh empty database is started. Returns what happened."""
    ok, msg = integrity()
    if ok:
        return {"status": "ok"}
    stamp = time.strftime("%Y%m%d-%H%M%S")
    bad = DB_FILE.with_name(f"{DB_FILE.name}.corrupt-{stamp}")
    for suffix in ("", "-wal", "-shm"):
        f = DB_FILE.with_name(DB_FILE.name + suffix)
        if f.exists():
            f.replace(bad.with_name(bad.name + suffix))
    for snap in sorted(SNAPSHOTS.glob("factory-*.db"), reverse=True):
        try:
            c = sqlite3.connect(snap)
            good = c.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            c.close()
        except sqlite3.DatabaseError:
            continue
        if good:
            import shutil
            shutil.copy2(snap, DB_FILE)
            return {"status": "restored", "from": snap.name, "damaged_kept_as": bad.name, "problem": msg}
    return {"status": "fresh", "damaged_kept_as": bad.name, "problem": msg}


def q(sql: str, args: tuple = ()) -> list[dict]:
    with conn() as c:
        return [dict(r) for r in c.execute(sql, args).fetchall()]


def x(sql: str, args: tuple = ()) -> int:
    with conn() as c:
        return c.execute(sql, args).lastrowid


# ---- runs and jobs -------------------------------------------------------------------------------
def start_run(day: str, requested: int, source: str) -> int:
    return x("INSERT INTO runs(day,requested,source,started,status) VALUES(?,?,?,?,?)", (day, requested, source, now(), "running"))


def finish_run(run_id: int, status: str, note: str = "") -> None:
    x("UPDATE runs SET finished=?, status=?, note=? WHERE id=?", (now(), status, note, run_id))


def create_job(run_id: int, name: str, day: str, source: str) -> int:
    return x("INSERT INTO jobs(run_id,name,day,status,stage,source,started) VALUES(?,?,?,?,?,?,?)",
             (run_id, name, day, "running", "created", source, now()))


def update_job(job_id: int, **fields) -> None:
    if not fields:
        return
    cols = ", ".join(f"{k}=?" for k in fields)
    x(f"UPDATE jobs SET {cols} WHERE id=?", (*fields.values(), job_id))


def log_stage(job_id: int, stage: str, status: str, seconds: float = 0.0, detail: str = "") -> None:
    x("INSERT INTO stages(job_id,stage,status,seconds,detail,ts) VALUES(?,?,?,?,?,?)", (job_id, stage, status, round(seconds, 2), detail[:500], now()))
    update_job(job_id, stage=stage)


def add_failure(job_id: int, check_id: str, stage: str, detail: str) -> None:
    x("INSERT INTO failures(job_id,check_id,stage,detail,ts) VALUES(?,?,?,?,?)", (job_id, check_id, stage, detail[:500], now()))


def add_repair(job_id: int, attempt: int, action: str, result: str) -> None:
    x("INSERT INTO repairs(job_id,attempt,action,result,ts) VALUES(?,?,?,?,?)", (job_id, attempt, action, result[:300], now()))


def save_story(s: dict) -> None:
    x("""INSERT OR REPLACE INTO stories(name,title,plot,closing,category,cast_json,templates,score,approved,source,created)
         VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
      (s["name"], s["title"], s["plot"], s["closing"], s["category"], json.dumps(s["cast"]), ",".join(s["templates"]),
       s["score"], int(s["approved"]), s["source"], now()))


def set_upload(job_id: int, status: str, video_id: str = "", scheduled_at: str = "", detail: str = "") -> None:
    x("INSERT INTO uploads(job_id,video_id,status,scheduled_at,detail,ts) VALUES(?,?,?,?,?,?)", (job_id, video_id, status, scheduled_at, detail[:300], now()))


def add_feedback(job_id: int, rating: int, note: str) -> None:
    x("INSERT INTO feedback(job_id,rating,note,ts) VALUES(?,?,?,?)", (job_id, rating, note, now()))


# ---- learning queries (used to guide the next run) -------------------------------------------------
def character_usage(last_n: int = 30) -> dict[str, int]:
    use: dict[str, int] = {}
    for r in q("SELECT cast_json FROM jobs WHERE status='ready' AND cast_json IS NOT NULL ORDER BY id DESC LIMIT ?", (last_n,)):
        for c in json.loads(r["cast_json"]):
            use[c] = use.get(c, 0) + 1
    return use


def template_failure_rates() -> dict[str, float]:
    """Share of failed checks per stage, from the failure log (what tends to break)."""
    rows = q("SELECT stage, COUNT(*) n FROM failures GROUP BY stage")
    total = sum(r["n"] for r in rows) or 1
    return {r["stage"]: round(r["n"] / total, 2) for r in rows}


def passed_today(day: str) -> int:
    return q("SELECT COUNT(*) n FROM jobs WHERE day=? AND status='ready'", (day,))[0]["n"]


def stats() -> dict:
    t = q("SELECT COUNT(*) total, SUM(status='ready') ready, SUM(status='failed') failed, AVG(qc_score) qc, AVG(seo_score) seo, AVG(seconds) secs FROM jobs")[0]
    return {k: (round(v, 1) if isinstance(v, float) else (v or 0)) for k, v in t.items()}
