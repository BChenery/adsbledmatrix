import asyncio
import json
import math
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.api import websocket as websocket_mod
from app.services.adsb_receiver import LiveAircraft


@pytest.fixture
def sample_aircraft():
    return LiveAircraft(
        hex_code="7C78A8",
        callsign="QLK1516",
        latitude=-27.33,
        longitude=153.16,
        altitude=650,
        ground_speed=125,
        heading=207.0,
        vertical_rate=-704,
        distance_km=25.45,
        bearing=44.0,
        messages=10,
        last_seen=datetime(2026, 8, 14, 21, 36, 6),
    )


@pytest.mark.asyncio
async def test_serialize_live_aircraft_includes_route_fields(monkeypatch, sample_aircraft):
    monkeypatch.setattr(websocket_mod.receiver, "get_recent", lambda n=20: [sample_aircraft])
    monkeypatch.setattr(
        websocket_mod.db,
        "enrich",
        AsyncMock(
            return_value={
                "registration": "VH-X4A",
                "model": "BD-500-1A11",
                "operator": "NATIONAL JET SYSTEMS PTY LTD",
                "operator_icao": "QFA",
                "type_code": "BCS3",
                "type_name": "Airbus A220-300",
            }
        ),
    )
    monkeypatch.setattr(
        websocket_mod.route_service,
        "lookup",
        AsyncMock(return_value=SimpleNamespace(origin="YBBN", destination="YSSY")),
    )
    monkeypatch.setattr(
        websocket_mod.airport_service,
        "display_values_for_route",
        lambda origin, dest: {
            "origin_iata": "BNE",
            "destination_iata": "SYD",
            "origin_city": "Brisbane",
            "destination_city": "Sydney",
        },
    )
    monkeypatch.setattr(
        websocket_mod.logo_manager,
        "airline_display_name",
        lambda **kwargs: "QantasLink",
    )

    data = await websocket_mod.serialize_live_aircraft()

    assert len(data) == 1
    row = data[0]
    assert row["hex_code"] == "7C78A8"
    assert row["callsign"] == "QLK1516"
    assert row["distance_display"] == "25.4 km"
    assert row["airline"] == "QantasLink"
    assert row["route"] == "YBBN-YSSY"
    assert row["origin_city"] == "Brisbane"
    assert row["destination_iata"] == "SYD"


@pytest.mark.asyncio
async def test_serialize_survives_enrichment_errors(monkeypatch, sample_aircraft):
    monkeypatch.setattr(websocket_mod.receiver, "get_recent", lambda n=20: [sample_aircraft])
    monkeypatch.setattr(websocket_mod.db, "enrich", AsyncMock(side_effect=RuntimeError("db down")))
    monkeypatch.setattr(websocket_mod.route_service, "lookup", AsyncMock(side_effect=RuntimeError("route down")))
    monkeypatch.setattr(
        websocket_mod.airport_service,
        "display_values_for_route",
        lambda origin, dest: {},
    )
    monkeypatch.setattr(
        websocket_mod.logo_manager,
        "airline_display_name",
        lambda **kwargs: None,
    )

    data = await websocket_mod.serialize_live_aircraft()

    assert data[0]["hex_code"] == "7C78A8"
    assert data[0]["registration"] is None
    assert data[0]["route"] is None


def test_json_safe_strips_nan():
    assert websocket_mod._json_safe(math.nan) is None
    assert websocket_mod._json_safe(math.inf) is None
    assert websocket_mod._json_safe(12.5) == 12.5


@pytest.mark.asyncio
async def test_aircraft_message_is_strict_json(monkeypatch, sample_aircraft):
    sample_aircraft.bearing = float("nan")
    monkeypatch.setattr(websocket_mod.receiver, "get_recent", lambda n=20: [sample_aircraft])
    monkeypatch.setattr(websocket_mod.db, "enrich", AsyncMock(return_value={}))
    monkeypatch.setattr(websocket_mod.route_service, "lookup", AsyncMock(return_value=None))
    monkeypatch.setattr(
        websocket_mod.airport_service,
        "display_values_for_route",
        lambda origin, dest: {},
    )
    monkeypatch.setattr(
        websocket_mod.logo_manager,
        "airline_display_name",
        lambda **kwargs: None,
    )

    raw = await websocket_mod.aircraft_message()
    parsed = json.loads(raw)
    assert parsed["type"] == "aircraft"
    assert parsed["data"][0]["bearing"] is None


@pytest.mark.asyncio
async def test_broadcast_skips_hung_clients_and_keeps_running(monkeypatch):
    hung = MagicMock()
    hung.send_text = AsyncMock(side_effect=asyncio.TimeoutError())
    healthy = MagicMock()
    healthy.send_text = AsyncMock()

    websocket_mod.connected_clients.clear()
    websocket_mod.connected_clients.add(hung)
    websocket_mod.connected_clients.add(healthy)
    monkeypatch.setattr(websocket_mod, "aircraft_message", AsyncMock(return_value='{"type":"aircraft","data":[]}'))
    monkeypatch.setattr(websocket_mod, "_SEND_TIMEOUT_SECONDS", 0.05)

    task = asyncio.create_task(websocket_mod.broadcast_aircraft())
    await asyncio.sleep(1.2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    healthy.send_text.assert_awaited()
    assert hung not in websocket_mod.connected_clients
    assert healthy in websocket_mod.connected_clients
    websocket_mod.connected_clients.clear()
