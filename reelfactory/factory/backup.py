"""Backup and recovery. Backups hold everything small and irreplaceable (source, scripts, stories, reel
scripts, assets, fonts, docs, finished-video LISTs); big or re-creatable things are left out (node_modules,
.venv, models, dist, rendered videos). Finished videos are protected by a different rule: nothing in this
package ever deletes them.

    python -m factory backup [label]
    python -m factory backups                      list
    python -m factory restore <zip>                extracts into restore-<time>/ (never over live files)
"""

from __future__ import annotations

import time
import zipfile
from pathlib import Path

from . import ROOT, db

INCLUDE = ["src", "scripts", "reels", "stories", "assets", "fonts", "tools", "factory", "tests", "docs", "evidence",
           "package.json", "tsconfig.json", "README.md", "IDEAS.md", "CHANGELOG.md", "CONFIG.md",
           "ARCHITECTURE.md", "THIRD_PARTY_NOTICES.md", "TEST_REPORT.md", "factory.env.example"]
SKIP_DIRS = {"node_modules", ".venv", "models", "dist", "__pycache__", "backups", "logs", "public", ".git"}
SKIP_SUFFIX = {".mp4", ".wav", ".pyc"}
BACKUPS = ROOT / "backups"


def create(label: str = "manual") -> Path:
    BACKUPS.mkdir(exist_ok=True)
    out = BACKUPS / f"{label}-{time.strftime('%Y%m%d-%H%M%S')}.zip"
    n = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for item in INCLUDE:
            p = ROOT / item
            files = [p] if p.is_file() else [f for f in p.rglob("*") if f.is_file()] if p.is_dir() else []
            for f in files:
                rel = f.relative_to(ROOT)
                if set(rel.parts) & SKIP_DIRS:
                    continue
                if f.suffix.lower() in SKIP_SUFFIX and rel.parts[0] != "evidence":  # evidence keeps its videos
                    continue
                if rel.parts[:3] == ("factory", "data", "factory.db") or f.name.startswith("factory.db-"):
                    continue  # the live database is added below as a consistent snapshot
                z.write(f, rel.as_posix())
                n += 1
        snap = db.snapshot()
        if snap:
            z.write(snap, "factory/data/factory.db")
            n += 1
        # the LIST/manifest of every ready folder (not the videos themselves)
        for f in (ROOT / "output" / "ready").glob("*/*.md"):
            z.write(f, f.relative_to(ROOT).as_posix())
            n += 1
    return out


def listing() -> list[Path]:
    return sorted(BACKUPS.glob("*.zip")) if BACKUPS.exists() else []


def restore(zip_path: str | Path) -> Path:
    """Extract into a NEW folder next to the project. Live files are never overwritten; copy back by hand."""
    target = ROOT.parent / f"{ROOT.name}-restore-{time.strftime('%Y%m%d-%H%M%S')}"
    with zipfile.ZipFile(zip_path) as z:
        bad = z.testzip()
        if bad:
            raise RuntimeError(f"corrupt backup, first bad file: {bad}")
        z.extractall(target)
    return target


if __name__ == "__main__":
    print(create("pre-factory"))
