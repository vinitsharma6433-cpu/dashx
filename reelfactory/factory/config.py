"""Configuration. Priority (highest first): environment variables, factory.env (KEY=VALUE per line),
factory/data/settings.json (written by the dashboard, never holds secrets), built-in defaults.

Secrets (YouTube OAuth client file and token file) are only ever PATHS taken from environment variables or
factory.env; their contents are never read into the config, logged or put in the dashboard.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, fields

from . import ROOT

DATA = ROOT / "factory" / "data"
SETTINGS_FILE = DATA / "settings.json"
ENV_FILE = ROOT / "factory.env"

TRUE = {"1", "true", "yes", "on"}


@dataclass
class Config:
    DAILY_REEL_LIMIT: int = 5
    AUTO_GENERATE: bool = True
    AUTO_QC: bool = True
    AUTO_REPAIR: bool = True
    AUTO_THUMBNAIL: bool = True
    AUTO_SEO: bool = True
    AUTO_UPLOAD: bool = False          # stays OFF until you configure credentials and turn it on yourself
    SOURCE: str = "auto"               # auto | bank | gemma
    RUN_TIME: str = "09:00"            # local time the scheduler starts the daily run
    MIN_QC_SCORE: int = 90             # a reel below this is never marked ready
    MIN_STORY_SCORE: int = 70          # a story below this is rejected
    MAX_REPAIRS: int = 3               # automatic repair attempts per reel
    ALLOW_NARRATION: bool = False      # False = only dialogue stories (stories/dialogue_bank.md); True also allows the older narrated bank and Gemma
    GEMMA_SLOTS_PER_RUN: int = 1       # Gemma gets this many tries per run (its Hindi is weak), then the bank is used
    MIN_FREE_GB: float = 5.0           # the run stops below this much free disk
    YOUTUBE_PRIVACY: str = "private"   # private | unlisted | public (scheduled videos must start private)
    YOUTUBE_PUBLISH_DELAY_MIN: int = 60
    YOUTUBE_DAILY_QUOTA: int = 10000   # API units per day (an upload costs about 1650)

    def public(self) -> dict:
        return asdict(self)


# secrets are paths only, from the environment
def secret_paths() -> dict:
    return {
        "client_secret_file": os.environ.get("YOUTUBE_CLIENT_SECRET_FILE") or _env_file().get("YOUTUBE_CLIENT_SECRET_FILE", ""),
        "token_file": os.environ.get("YOUTUBE_TOKEN_FILE") or _env_file().get("YOUTUBE_TOKEN_FILE") or str(ROOT / "secrets" / "youtube_token.json"),
    }


def _env_file() -> dict:
    out: dict = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def _convert(name: str, kind: type, raw):
    if kind is bool:
        return str(raw).strip().lower() in TRUE
    return kind(raw)


def load(overrides: dict | None = None) -> Config:
    values: dict = {}
    if SETTINGS_FILE.exists():
        try:
            values.update(json.loads(SETTINGS_FILE.read_text(encoding="utf-8")))
        except Exception:
            pass
    values.update({k: v for k, v in _env_file().items() if k in Config.__dataclass_fields__})
    values.update({k: v for k, v in os.environ.items() if k in Config.__dataclass_fields__})
    values.update(overrides or {})
    cfg = Config()
    for f in fields(Config):
        if f.name in values:
            try:
                setattr(cfg, f.name, _convert(f.name, type(getattr(cfg, f.name)), values[f.name]))
            except (TypeError, ValueError):
                pass  # a bad value falls back to the default
    if cfg.SOURCE not in ("auto", "bank", "gemma"):
        cfg.SOURCE = "auto"
    cfg.DAILY_REEL_LIMIT = max(1, min(50, cfg.DAILY_REEL_LIMIT))
    cfg.MAX_REPAIRS = max(0, min(5, cfg.MAX_REPAIRS))
    return cfg


def save_settings(changes: dict) -> Config:
    """Dashboard: persist non-secret settings. Unknown keys are ignored."""
    DATA.mkdir(parents=True, exist_ok=True)
    cur = {}
    if SETTINGS_FILE.exists():
        cur = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    cur.update({k: v for k, v in changes.items() if k in Config.__dataclass_fields__})
    SETTINGS_FILE.write_text(json.dumps(cur, indent=1), encoding="utf-8")
    return load()
