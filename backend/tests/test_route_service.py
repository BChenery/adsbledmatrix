from types import SimpleNamespace

import pytest

from app.services.route_service import RouteService


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
