"""Bridge to the existing DASHX scripts (scripts/*.py and the vendored purffle-shorts). The factory re-uses
them instead of rewriting them: voice, fitting, story builders and rules stay exactly as they were."""

from __future__ import annotations

import sys
from pathlib import Path

from . import ROOT

for _p in (ROOT / "scripts", ROOT / "tools" / "purffle-shorts"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import daily  # noqa: E402,F401  (story builders, rules, ready-folder helpers)
import fit_reel  # noqa: E402,F401
import make_stories  # noqa: E402,F401
import story_rules  # noqa: E402,F401
from fit_reel import measure_subtitles  # noqa: E402,F401

PY = ROOT / ".venv" / "Scripts" / "python.exe"
if not PY.exists():  # Linux / GitHub Actions: the interpreter that runs the factory
    PY = Path(sys.executable)
