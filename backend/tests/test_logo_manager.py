import pytest
from io import BytesIO
from pathlib import Path

from PIL import Image

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


def test_fd_callsign_vh_registration_uses_rfds_logo(fake_logos_dir):
    """FD-prefixed callsigns on Australian-registered aircraft are RFDS."""
    _make_logo(fake_logos_dir, "RFDS")
    _make_logo(fake_logos_dir, "AIQ")

    path = logo_manager.logo_path_for_aircraft("AIQ", "FD511", "VH-SZS")

    assert path == fake_logos_dir / "RFDS.png"


def test_fd_callsign_hs_registration_uses_thai_airasia_logo(fake_logos_dir):
    """FD-prefixed callsigns on Thai-registered aircraft remain Thai AirAsia."""
    _make_logo(fake_logos_dir, "RFDS")
    _make_logo(fake_logos_dir, "AIQ")

    path = logo_manager.logo_path_for_aircraft("AIQ", "FD511", "HS-ABC")

    assert path == fake_logos_dir / "AIQ.png"


def test_vh_registration_with_foreign_operator_uses_unknown(fake_logos_dir):
    """VH- registered aircraft with bad foreign operator data show a type silhouette."""
    _make_logo(fake_logos_dir, "SAS")
    _make_logo(fake_logos_dir, "UNKNOWN")

    path = logo_manager.logo_path_for_aircraft("SAS", None, "VH-SZS")

    assert path == fake_logos_dir / "UNKNOWN.png"


def test_vh_registration_foreign_operator_r44_uses_heli_fallback(fake_logos_dir):
    """An R44 with bad foreign operator data should show the helicopter silhouette."""
    _make_logo(fake_logos_dir, "SAS")
    _make_logo(fake_logos_dir, "UNKNOWN")
    _make_logo(fake_logos_dir, "UNKNOWN_HELI")

    path = logo_manager.logo_path_for_aircraft(
        "SAS", None, "VH-HEL", type_code="R44", type_name="Robinson R44"
    )

    assert path == fake_logos_dir / "UNKNOWN_HELI.png"


def test_ga_without_airline_logo_uses_prop_fallback(fake_logos_dir):
    """Private Cessna with no operator logo should show the prop silhouette."""
    _make_logo(fake_logos_dir, "UNKNOWN_PROP")
    _make_logo(fake_logos_dir, "UNKNOWN")

    path = logo_manager.logo_path_for_aircraft(
        None, None, "VH-ABC", type_code="C172", type_name="Cessna 172"
    )

    assert path == fake_logos_dir / "UNKNOWN_PROP.png"


def test_bizjet_without_airline_logo_uses_bizjet_fallback(fake_logos_dir):
    """Citation / Gulfstream with no brand logo should show the bizjet silhouette."""
    _make_logo(fake_logos_dir, "UNKNOWN_BIZJET")
    _make_logo(fake_logos_dir, "UNKNOWN")

    path = logo_manager.logo_path_for_aircraft(
        None, None, "VH-JET", type_code="C25A", type_name="Cessna Citation CJ2"
    )
    assert path == fake_logos_dir / "UNKNOWN_BIZJET.png"

    path = logo_manager.logo_path_for_aircraft(
        None, None, "VH-GSF", type_code="GLF5", type_name="Gulfstream G500"
    )
    assert path == fake_logos_dir / "UNKNOWN_BIZJET.png"


def test_airline_logo_still_preferred_over_type_fallback(fake_logos_dir):
    """A real airline brand must win even when type would pick a silhouette."""
    _make_logo(fake_logos_dir, "QFA")
    _make_logo(fake_logos_dir, "UNKNOWN_BIZJET")

    path = logo_manager.logo_path_for_aircraft(
        "QFA", "QFA123", "VH-OQI", type_code="C25A"
    )

    assert path == fake_logos_dir / "QFA.png"


def test_vh_registration_with_australian_operator_uses_logo(fake_logos_dir):
    """VH- registered aircraft with a valid Australian operator show that logo."""
    _make_logo(fake_logos_dir, "QFA")

    path = logo_manager.logo_path_for_aircraft("QFA", None, "VH-OQI")

    assert path == fake_logos_dir / "QFA.png"


def test_vh_registration_operator_icao_override_is_allowed(fake_logos_dir):
    """VH- aircraft with a wrong-code operator_icao should map to the real Australian ICAO."""
    _make_logo(fake_logos_dir, "VOZ")

    path = logo_manager.logo_path_for_aircraft("VA", None, "VH-VZZ")

    assert path == fake_logos_dir / "VOZ.png"


def test_jst_logo_recolors_black_wordmark_to_silver():
    """Jetstar's black 'Jet' wordmark should become silver for LED visibility."""
    img = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    # Black wordmark pixels
    for x in range(0, 8):
        for y in range(4, 12):
            img.putpixel((x, y), (0, 0, 0, 255))
    # Orange star pixels (must stay orange)
    for x in range(8, 16):
        for y in range(4, 12):
            img.putpixel((x, y), (248, 88, 16, 255))

    buf = BytesIO()
    img.save(buf, format="PNG")
    out = logo_manager._resize_image(buf.getvalue(), icao="JST")
    assert out is not None

    result = Image.open(BytesIO(out)).convert("RGBA")
    # Input is 16x16; resize targets 96x96. Sample scaled centers of each half.
    silver_px = result.getpixel((24, 48))
    assert silver_px[0] >= 180 and silver_px[1] >= 180 and silver_px[2] >= 180
    assert silver_px[3] == 255
    # Orange preserved
    orange_px = result.getpixel((72, 48))
    assert orange_px[0] > 200 and orange_px[1] < 120 and orange_px[2] < 80


def test_airline_display_name_prefers_callsign_over_operator():
    """QLK callsign on Alliance metal should show QantasLink, not Alliance."""
    name = logo_manager.airline_display_name(
        operator_icao="UTY",
        callsign="QLK2341",
        registration="VH-XUE",
        operator_name="Alliance Airlines Pty Limited",
    )
    assert name == "QantasLink"


def test_airline_display_name_qantas_from_callsign():
    name = logo_manager.airline_display_name(
        operator_icao="QFA",
        callsign="QFA123",
        operator_name="Qantas Airways Pty Ltd",
    )
    assert name == "Qantas"


def test_airline_display_name_shortens_legal_operator_when_no_callsign():
    name = logo_manager.airline_display_name(
        operator_icao=None,
        callsign=None,
        operator_name="Qantas Airways Pty Ltd",
    )
    assert name == "Qantas Airways"


def test_airline_display_name_voz_wet_lease():
    """Virgin callsign on Alliance aircraft → Virgin Australia brand name."""
    name = logo_manager.airline_display_name(
        operator_icao="UTY",
        callsign="VOZ456",
        operator_name="Alliance Airlines Pty Limited",
    )
    assert name == "Virgin Australia"


def test_resolve_airline_icao_keeps_qlk_for_names_but_aliases_for_logos():
    assert logo_manager.resolve_airline_icao("UTY", "QLK1", for_logo=False) == "QLK"
    assert logo_manager.resolve_airline_icao("UTY", "QLK1", for_logo=True) == "QFA"
