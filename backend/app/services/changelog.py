"""Parse the project CHANGELOG.md into structured release entries."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from app.config import PROJECT_ROOT, settings

# ## [1.2.3] - 2026-07-15   or   ## [1.2.3]   or   ## 1.2.3 - 2026-07-15
_VERSION_RE = re.compile(
    r"^##\s+(?:\[(?P<bracked>[^\]]+)\]|(?P<plain>[0-9]+\.[0-9]+(?:\.[0-9]+)?(?:[-+][\w.]+)?|Earlier|Unreleased))"
    r"(?:\s*[-–—]\s*(?P<date>\d{4}-\d{2}-\d{2}))?\s*$",
    re.IGNORECASE,
)
_SECTION_RE = re.compile(r"^###\s+(.+?)\s*$")
_ITEM_RE = re.compile(r"^[-*+]\s+(.+?)\s*$")


@dataclass
class ChangelogSection:
    title: str
    items: list[str] = field(default_factory=list)


@dataclass
class ChangelogEntry:
    version: str
    date: Optional[str] = None
    sections: list[ChangelogSection] = field(default_factory=list)


def changelog_path() -> Path:
    """Resolve CHANGELOG.md next to VERSION (project root)."""
    return PROJECT_ROOT / "CHANGELOG.md"


def parse_changelog(text: str) -> list[ChangelogEntry]:
    """Parse Keep a Changelog-style markdown into ordered entries (newest first)."""
    entries: list[ChangelogEntry] = []
    current: Optional[ChangelogEntry] = None
    section: Optional[ChangelogSection] = None

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            continue

        version_match = _VERSION_RE.match(line)
        if version_match:
            if current is not None:
                if section is not None and section.items:
                    current.sections.append(section)
                entries.append(current)
            version = (version_match.group("bracked") or version_match.group("plain") or "").strip()
            current = ChangelogEntry(version=version, date=version_match.group("date"))
            section = None
            continue

        if current is None:
            # Skip title / intro until first version heading.
            continue

        section_match = _SECTION_RE.match(line)
        if section_match:
            if section is not None and section.items:
                current.sections.append(section)
            section = ChangelogSection(title=section_match.group(1).strip())
            continue

        item_match = _ITEM_RE.match(line)
        if item_match:
            if section is None:
                section = ChangelogSection(title="Notes")
            section.items.append(item_match.group(1).strip())
            continue

    if current is not None:
        if section is not None and section.items:
            current.sections.append(section)
        entries.append(current)

    return entries


def load_changelog(path: Optional[Path] = None) -> list[ChangelogEntry]:
    """Read and parse CHANGELOG.md. Returns [] if missing or empty."""
    target = path or changelog_path()
    if not target.is_file():
        return []
    text = target.read_text(encoding="utf-8")
    return parse_changelog(text)


def changelog_payload(path: Optional[Path] = None) -> dict:
    """JSON-serializable payload for the API."""
    entries = load_changelog(path)
    return {
        "current_version": settings.version,
        "entries": [
            {
                "version": entry.version,
                "date": entry.date,
                "sections": [
                    {"title": sec.title, "items": list(sec.items)}
                    for sec in entry.sections
                ],
            }
            for entry in entries
        ],
    }
