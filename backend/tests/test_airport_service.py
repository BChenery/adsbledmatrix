"""Tests for airport IATA / city resolution."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services.airport_service import AirportService
from app.services.display_engine import DisplayEngine, RenderContext


@pytest.fixture
def engine() -> DisplayEngine:
    return DisplayEngine()


@pytest.fixture
def airports_csv(tmp_path: Path) -> Path:
    path = tmp_path / "airports.csv"
    path.write_text(
        "icao,iata,city\n"
        "YBBN,BNE,Brisbane\n"
        "YMML,MEL,Melbourne\n"
        "YSSY,SYD,Sydney\n"
        "EGLL,LHR,London\n"
        "KLAX,LAX,Los Angeles\n"
        ",BNE,Brisbane\n",  # iata-only row should not clobber ICAO-backed
        encoding="utf-8",
    )
    return path


@pytest.fixture
def svc(airports_csv: Path) -> AirportService:
    return AirportService(csv_path=airports_csv)


def test_icao_to_iata_and_city(svc: AirportService):
    info = svc.lookup("YBBN")
    assert info is not None
    assert info.iata == "BNE"
    assert info.city == "Brisbane"
    assert svc.iata("YBBN") == "BNE"
    assert svc.city("YBBN") == "Brisbane"


def test_iata_lookup(svc: AirportService):
    assert svc.lookup("MEL").city == "Melbourne"
    assert svc.iata("MEL") == "MEL"
    assert svc.city("LAX") == "Los Angeles"


def test_display_values_for_route_icao(svc: AirportService):
    vals = svc.display_values_for_route("YBBN", "YMML")
    assert vals["origin_iata"] == "BNE"
    assert vals["destination_iata"] == "MEL"
    assert vals["origin_city"] == "Brisbane"
    assert vals["destination_city"] == "Melbourne"
    assert vals["from_city"] == "Brisbane"
    assert vals["to_iata"] == "MEL"


def test_display_values_for_route_iata(svc: AirportService):
    vals = svc.display_values_for_route("BNE", "SYD")
    assert vals["origin_iata"] == "BNE"
    assert vals["destination_city"] == "Sydney"


def test_display_values_missing(svc: AirportService):
    vals = svc.display_values_for_route(None, None)
    assert vals["origin_iata"] == "---"
    assert vals["destination_city"] == "---"


def test_display_engine_resolves_airport_fields(engine: DisplayEngine, monkeypatch, airports_csv: Path):
    from types import SimpleNamespace
    from app.services import airport_service as airport_mod

    svc = AirportService(csv_path=airports_csv)
    monkeypatch.setattr(airport_mod, "airport_service", svc)

    route = SimpleNamespace(origin="YBBN", destination="EGLL")
    ctx = RenderContext(is_idle=False, route=route, aircraft=SimpleNamespace(hex_code="ABC123"))
    # non-idle without aircraft returns --- early for most fields — set a minimal aircraft
    ac = SimpleNamespace(
        hex_code="7C4A55",
        callsign="JST800",
        altitude=None,
        ground_speed=None,
        heading=None,
        distance_km=None,
        vertical_rate=None,
        squawk=None,
        messages=1,
        last_seen=__import__("datetime").datetime.utcnow(),
    )
    ctx = RenderContext(aircraft=ac, route=route, is_idle=False)

    assert engine._resolve_data_field("origin_iata", "{origin_iata}", ctx) == "BNE"
    assert engine._resolve_data_field("destination_iata", "{destination_iata}", ctx) == "LHR"
    assert engine._resolve_data_field("origin_city", "{origin_city}", ctx) == "Brisbane"
    assert engine._resolve_data_field("destination_city", "{destination_city}", ctx) == "London"
