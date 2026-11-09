"""Autonomous daily scheduler. `python -m factory schedule` keeps running and starts the daily production at
RUN_TIME (default 09:00) once per day; `--once` checks one time and exits (use it from Windows Task Scheduler).
It never starts a second run while one is active (lock), resumes interrupted jobs, and respects AUTO_GENERATE.
A STOP flag (dashboard Stop button) ends the loop."""

from __future__ import annotations

import time

from . import db, log, ops
from .config import load
from .pipeline import ProductionManager


def due(cfg, now: time.struct_time | None = None) -> bool:
    now = now or time.localtime()
    hh, mm = (int(x) for x in cfg.RUN_TIME.split(":"))
    day = time.strftime("%Y-%m-%d", now)
    already = db.q("SELECT 1 FROM runs WHERE day=? AND status IN ('done','partial')", (day,))
    interrupted = db.q("SELECT 1 FROM jobs WHERE status='running'")
    reached = (now.tm_hour, now.tm_min) >= (hh, mm)
    return cfg.AUTO_GENERATE and ((reached and not already) or bool(interrupted)) and db.passed_today(day) < cfg.DAILY_REEL_LIMIT


def check_once() -> dict | None:
    cfg = load()
    if not due(cfg):
        return None
    log.info("scheduler: starting the daily production")
    return ProductionManager(cfg).run_day()


def loop(poll_seconds: int = 30) -> None:
    log.info("scheduler started", stage="scheduler")
    while not ops.stop_requested():
        try:
            check_once()
        except Exception as e:  # the scheduler itself must survive any error
            log.error(f"scheduler error: {e}")
        time.sleep(poll_seconds)
    log.info("scheduler stopped (STOP flag)")
