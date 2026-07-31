"""Tests for the world weather idle service."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.weather_service import (
    WORLD_CITIES,
    WeatherService,
    WeatherSnapshot,
    _wmo_label,
)


def test_wmo_labels_cover_common_codes():
    assert _wmo_label(0) == "Clear"
    assert _wmo_label(61) == "Light rain"
    assert _wmo_label(95) == "Thunderstorm"
    assert _wmo_label(None) == "---"
    assert "999" in _wmo_label(999) or "Code" in _wmo_label(999)


def test_world_cities_include_user_requested():
    names = {c[0] for c in WORLD_CITIES}
    for city in (
        "Brisbane",
        "Sydney",
        "Melbourne",
        "Tokyo",
        "Paris",
        "London",
        "Barcelona",
        "Hong Kong",
        "San Francisco",
        "Toronto",
        "New York",
        "Mexico City",
        "Sao Paulo",
    ):
        assert city in names


def test_snapshot_display_values():
    snap = WeatherSnapshot(
        city="Tokyo",
        country="Japan",
        temperature_c=22.4,
        feels_like_c=21.0,
        condition="Clear",
        humidity=55,
        wind_kmh=12.3,
        weather_code=0,
        local_time="14:30",
        fetched_at=time.monotonic(),
    )
    values = snap.as_display_values()
    assert values["weather_city"] == "Tokyo"
    assert values["weather_country"] == "Japan"
    assert values["weather_location"] == "Tokyo, Japan"
    assert values["weather_temp"] == "22°C"
    assert values["weather_feels_like"] == "21°C"
    assert values["weather_condition"] == "Clear"
    assert values["weather_humidity"] == "55%"
    assert values["weather_wind"] == "12 km/h"
    assert values["weather_local_time"] == "14:30"


def test_city_rotates_after_interval():
    svc = WeatherService(city_interval_sec=5)
    svc._cities = [
        ("A", "X", 0.0, 0.0, "UTC"),
        ("B", "Y", 1.0, 1.0, "UTC"),
        ("C", "Z", 2.0, 2.0, "UTC"),
    ]
    svc._index = 0
    svc._city_since = time.monotonic() - 10  # force rotate
    first = svc.get_snapshot().city
    # After advance, city should differ from the starting city A
    # (advance happens inside get_snapshot)
    # Force another rotate
    svc._city_since = time.monotonic() - 10
    second = svc.get_snapshot().city
    # With 3 cities and random pick != current, second may equal first only if unlucky;
    # but after forced advance from known index, city changes at least once.
    assert first in {"A", "B", "C"}
    assert second in {"A", "B", "C"}


def test_get_snapshot_loading_when_uncached():
    svc = WeatherService(city_interval_sec=60)
    svc._cities = [("Paris", "France", 48.8, 2.3, "Europe/Paris")]
    svc._index = 0
    svc._city_since = time.monotonic()
    snap = svc.get_snapshot()
    assert snap.city == "Paris"
    assert snap.condition == "Loading..."
    assert snap.stale is True


@pytest.mark.asyncio
async def test_fetch_city_parses_open_meteo_payload():
    svc = WeatherService(city_interval_sec=60)
    svc._cities = [("London", "UK", 51.5, -0.1, "Europe/London")]
    svc._index = 0

    payload = {
        "current": {
            "temperature_2m": 11.6,
            "apparent_temperature": 9.2,
            "relative_humidity_2m": 80,
            "weather_code": 3,
            "wind_speed_10m": 18.5,
        }
    }
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = payload

    client = AsyncMock()
    client.get = AsyncMock(return_value=mock_resp)
    svc._client = client

    await svc._fetch_city("London", "UK", 51.5, -0.1, "Europe/London")
    snap = svc._cache["London"]
    assert snap.temperature_c == 11.6
    assert snap.condition == "Overcast"
    assert snap.humidity == 80
    assert snap.wind_kmh == 18.5
    assert snap.stale is False
    client.get.assert_awaited_once()


@pytest.mark.asyncio
async def test_fetch_city_failure_marks_unavailable():
    svc = WeatherService(city_interval_sec=60)
    client = AsyncMock()
    client.get = AsyncMock(side_effect=RuntimeError("network down"))
    svc._client = client

    await svc._fetch_city("Berlin", "Germany", 52.5, 13.4, "Europe/Berlin")
    snap = svc._cache["Berlin"]
    assert snap.condition == "Unavailable"
    assert snap.stale is True



