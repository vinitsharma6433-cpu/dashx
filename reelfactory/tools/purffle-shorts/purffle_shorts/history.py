"""Memory of earlier stories, kept in a plain markdown file (stories/used.md) instead of purffle's
SQLite database (which also tracked uploads and view counts: removed).

used.md lines look like:   - 2026-10-29 | gali-umpire | Title | one-line plot
"""

from __future__ import annotations

from pathlib import Path


class History:
    def __init__(self, used_md: str | Path):
        self.path = Path(used_md)
        self._ideas: list[dict] = []

    def _rows(self) -> list[list[str]]:
        if not self.path.exists():
            return []
        rows = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("- ") and line.count("|") >= 2:
                rows.append([c.strip() for c in line[2:].split("|")])
        return rows

    def recent_titles(self, limit: int = 40) -> list[str]:
        """Titles of the last ``limit`` stories, newest last."""
        return [r[2] for r in self._rows() if len(r) > 2 and r[2]][-limit:]

    def ideas(self, status: str | None = "pending", limit: int = 200) -> list[dict]:
        return self._ideas[:limit]

    def add_idea(self, subject: str, style: str = "", notes: str = "") -> int:
        self._ideas.append({"id": len(self._ideas) + 1, "subject": subject, "style": style, "notes": notes})
        return len(self._ideas)

    def closings(self) -> list[str]:
        """Closing lines of earlier stories (5th column of used.md), so no two endings repeat."""
        return [r[4] for r in self._rows() if len(r) > 4 and r[4]]

    def add_used(self, date: str, name: str, title: str, plot: str, closing: str = "") -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        clean = lambda t: " ".join(str(t).replace("|", "/").split())
        line = f"- {date} | {clean(name)} | {clean(title)} | {clean(plot)}" + (f" | {clean(closing)}" if closing else "") + "\n"
        head = "" if self.path.exists() else "# Stories already made (newest last)\n\n"
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(head + line)
