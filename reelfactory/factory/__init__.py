"""DASHX Autonomous Reel Factory: an orchestration layer on top of the existing DASHX Reel Machine.

The existing pipeline (revideo animation, Kokoro Hindi voice, subtitle fitting, story bank, QC) is kept and
re-used. This package adds the database, agents, orchestrator, QC scoring, auto-repair, thumbnail, SEO,
optional YouTube publishing, scheduler and dashboard around it. Standard library only (plus numpy, which
the Kokoro install already brought into .venv).
"""

__version__ = "1.0.0"

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def find_tool(name: str) -> str:
    """ffmpeg / ffprobe: the Windows binary in node_modules when it exists, else the one on PATH (Linux, GitHub Actions)."""
    pkg = {"ffmpeg": "@ffmpeg-installer", "ffprobe": "@ffprobe-installer"}[name]
    win = ROOT / "node_modules" / pkg / "win32-x64" / f"{name}.exe"
    return str(win) if win.exists() else (shutil.which(name) or str(win))
