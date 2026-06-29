import pytest
from pathlib import Path
from app.config import settings
from app.services.logo_manager import logo_manager


@pytest.fixture
def fake_logos_dir(tmp_path, monkeypatch):
    """Provide an isolated logo directory and point settings at it."""
    logos_dir = tmp_path / "airline_logos"
    logos_dir.mkdir()
    monkeypatch.setattr(settings, "logos_dir", logos_dir)
    return logos_dir


def _make_logo(logos_dir: Path, code: str) -> Path:
    path = logos_dir / f"{code}.png"
    path.write_bytes(b"fake-png")
    return path


def test_voz_callsign_overrides_alliance_operator_icao(fake_logos_dir):
    """A VOZ flight on an Alliance-registered aircraft should show the Virgin logo."""
    _make_logo(fake_logos_dir, "VOZ")
    _make_logo(fake_logos_dir, "UTY")

    path = logo_manager.logo_path_for_aircraft("UTY", "VOZ123")

    assert path == fake_logos_dir / "VOZ.png"


def test_qlk_callsign_uses_qantas_logo(fake_logos_dir):
    """QantasLink flights (callsign prefix QLK) should display the Qantas logo."""
    _make_logo(fake_logos_dir, "QFA")

    path = logo_manager.logo_path_for_aircraft("QLK", "QLK123")

    assert path == fake_logos_dir / "QFA.png"


def test_qlk_operator_uses_qantas_logo_even_when_qlk_logo_exists(fake_logos_dir):
    """QantasLink-registered aircraft with no callsign should still show Qantas."""
    _make_logo(fake_logos_dir, "QLK")
    _make_logo(fake_logos_dir, "QFA")

    path = logo_manager.logo_path_for_aircraft("QLK", None)

    assert path == fake_logos_dir / "QFA.png"


def test_iata_prefix_maps_to_icao_logo(fake_logos_dir):
    """A two-letter IATA prefix like QF should resolve to the Qantas ICAO logo."""
    _make_logo(fake_logos_dir, "QFA")

    path = logo_manager.logo_path_for_aircraft(None, "QF12")

    assert path == fake_logos_dir / "QFA.png"


def test_no_callsign_falls_back_to_operator_icao(fake_logos_dir):
    """Without a callsign we should still use the aircraft operator's logo."""
    _make_logo(fake_logos_dir, "UTY")

    path = logo_manager.logo_path_for_aircraft("UTY", None)

    assert path == fake_logos_dir / "UTY.png"


def test_unknown_callsign_prefix_falls_back_to_operator_icao(fake_logos_dir):
    """An unrecognised callsign prefix should fall back to the operator ICAO logo."""
    _make_logo(fake_logos_dir, "UTY")

    path = logo_manager.logo_path_for_aircraft("UTY", "XYZ987")

    assert path == fake_logos_dir / "UTY.png"
