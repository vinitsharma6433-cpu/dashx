"""Structured logging: one JSON object per line in logs/factory-YYYYMMDD.jsonl, plus a readable console line.
Secrets are redacted (tokens, keys, client secrets) before anything is written."""

from __future__ import annotations

import json
import re
import sys
import time

from . import ROOT

LOGS = ROOT / "logs"
_SECRET = re.compile(r"(?i)(access_token|refresh_token|client_secret|api[_-]?key|authorization|password)([\"'=:\s]+)([^\s\"',}]+)")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def redact(text: str) -> str:
    return _SECRET.sub(lambda m: f"{m.group(1)}{m.group(2)}[REDACTED]", str(text))


def event(level: str, msg: str, **fields) -> None:
    LOGS.mkdir(exist_ok=True)
    rec = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "level": level, "event": redact(msg),
           **{k: (redact(v) if isinstance(v, str) else v) for k, v in fields.items()}}
    with open(LOGS / f"factory-{time.strftime('%Y%m%d')}.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    extra = " ".join(f"{k}={v}" for k, v in fields.items() if k in ("job", "stage", "score", "name"))
    print(f"[{rec['ts'][11:]}] {level:5} {rec['event']} {extra}".rstrip(), flush=True)


def info(msg: str, **f) -> None:
    event("INFO", msg, **f)


def warn(msg: str, **f) -> None:
    event("WARN", msg, **f)


def error(msg: str, **f) -> None:
    event("ERROR", msg, **f)
