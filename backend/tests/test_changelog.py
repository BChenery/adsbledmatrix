from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.system import router as system_router
from app.services.changelog import parse_changelog, load_changelog, changelog_payload


SAMPLE = """# Changelog

Intro text that should be ignored.

## [0.1.40] - 2026-07-15

### Added
- Apply vs Save in the designer
- Text clips like the LED matrix

### Fixed
- Something minor

## [0.1.39] - 2026-07-14

### Fixed
- Pause yellow flashes

## Earlier

### Added
- Real-time ADS-B
"""


def test_parse_changelog_entries_and_sections():
    entries = parse_changelog(SAMPLE)
    assert len(entries) == 3
    assert entries[0].version == "0.1.40"
    assert entries[0].date == "2026-07-15"
    assert [s.title for s in entries[0].sections] == ["Added", "Fixed"]
    assert entries[0].sections[0].items == [
        "Apply vs Save in the designer",
        "Text clips like the LED matrix",
    ]
    assert entries[1].version == "0.1.39"
    assert entries[2].version == "Earlier"
    assert entries[2].date is None
    assert entries[2].sections[0].items == ["Real-time ADS-B"]


def test_parse_changelog_skips_empty_sections():
    text = """## [1.0.0]

### Added

### Fixed
- one fix
"""
    entries = parse_changelog(text)
    assert len(entries) == 1
    assert [s.title for s in entries[0].sections] == ["Fixed"]


def test_load_changelog_missing_file(tmp_path: Path):
    assert load_changelog(tmp_path / "nope.md") == []


def test_load_changelog_reads_file(tmp_path: Path):
    path = tmp_path / "CHANGELOG.md"
    path.write_text(SAMPLE, encoding="utf-8")
    entries = load_changelog(path)
    assert entries[0].version == "0.1.40"


def test_changelog_payload_structure(tmp_path: Path, monkeypatch):
    from app.config import settings

    path = tmp_path / "CHANGELOG.md"
    path.write_text(SAMPLE, encoding="utf-8")
    monkeypatch.setattr(settings, "version", "0.1.40")
    payload = changelog_payload(path)
    assert payload["current_version"] == "0.1.40"
    assert payload["entries"][0]["version"] == "0.1.40"
    assert payload["entries"][0]["sections"][0]["title"] == "Added"


@pytest.fixture
def app():
    app = FastAPI()
    app.include_router(system_router)
    return app


@pytest.mark.asyncio
async def test_get_changelog_endpoint(app, tmp_path: Path, monkeypatch):
    path = tmp_path / "CHANGELOG.md"
    path.write_text(SAMPLE, encoding="utf-8")
    monkeypatch.setattr("app.services.changelog.changelog_path", lambda: path)
    monkeypatch.setattr("app.api.system.changelog_payload", lambda: changelog_payload(path))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/system/changelog")

    assert response.status_code == 200
    data = response.json()
    assert "current_version" in data
    assert data["entries"][0]["version"] == "0.1.40"
    assert data["entries"][0]["sections"][0]["items"][0] == "Apply vs Save in the designer"
