from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.services.route_service import RouteService, callsign_lookup_keys, select_route


@pytest.mark.asyncio
async def test_lookup_skips_scheduled_route_for_vh_af4_tail():
    """AF4 in the route cache is Air France CDG-JFK, not Angel Flight VH-AF4."""
    svc = RouteService()
    svc._cache["AF4"] = SimpleNamespace(origin="LFPG", destination="KJFK")

    assert await svc.lookup("AF4", registration="VH-AF4", hex_code="7C00D2") is None
    assert await svc.lookup("AF4", hex_code="7C00D2") is None


@pytest.mark.asyncio
async def test_lookup_keeps_real_air_france_af4():
    svc = RouteService()
    route = SimpleNamespace(origin="LFPG", destination="KJFK")
    svc._cache["AF4"] = route

    assert await svc.lookup("AF4", registration="F-GSQB", hex_code="394C19") is route
    assert await svc.lookup("AF4") is route


def test_callsign_lookup_keys_expand_leading_zeros_only():
    assert callsign_lookup_keys("voz045") == ["VOZ045", "VOZ45", "VOZ0045"]
    assert callsign_lookup_keys("VOZ45") == ["VOZ45", "VOZ045", "VOZ0045"]
    assert "VOZ45" not in callsign_lookup_keys("VOZ450")
    assert callsign_lookup_keys("VOZ450") == ["VOZ450", "VOZ0450"]
    assert callsign_lookup_keys("VH-AF4") == ["VH-AF4"]
    assert callsign_lookup_keys("  ") == []


def test_select_route_prefers_exact_callsign():
    padded = SimpleNamespace(callsign="VOZ045", origin="AAAA", destination="BBBB")
    stored = SimpleNamespace(callsign="VOZ45", origin="YBBN", destination="WADD")
    keys = callsign_lookup_keys("VOZ045")

    assert select_route(keys, [stored, padded]) is padded
    assert select_route(keys, [stored]) is stored
    assert select_route(keys, []) is None


@pytest.mark.asyncio
async def test_lookup_matches_unpadded_stored_callsign():
    svc = RouteService()
    stored = SimpleNamespace(callsign="VOZ45", origin="YBBN", destination="WADD")

    class _Result:
        def scalars(self):
            return self

        def all(self):
            return [stored]

    class _Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def execute(self, stmt):
            return _Result()

    with patch("app.services.route_service.AsyncSessionLocal", return_value=_Session()):
        found = await svc.lookup("VOZ045")

    assert found is stored
    assert svc._cache["VOZ045"] is stored
