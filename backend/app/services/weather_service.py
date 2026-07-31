"""Live world-weather for idle display (Open-Meteo, no API key)."""

from __future__ import annotations

import asyncio
import logging
import random
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

import httpx

logger = logging.getLogger(__name__)

# Curated world cities: name, country label, lat, lon, IANA timezone
WORLD_CITIES: List[Tuple[str, str, float, float, str]] = [
    ("Brisbane", "Australia", -27.4698, 153.0251, "Australia/Brisbane"),
    ("Sydney", "Australia", -33.8688, 151.2093, "Australia/Sydney"),
    ("Melbourne", "Australia", -37.8136, 144.9631, "Australia/Melbourne"),
    ("Auckland", "New Zealand", -36.8509, 174.7645, "Pacific/Auckland"),
    ("Tokyo", "Japan", 35.6762, 139.6503, "Asia/Tokyo"),
    ("Seoul", "South Korea", 37.5665, 126.9780, "Asia/Seoul"),
    ("Hong Kong", "China", 22.3193, 114.1694, "Asia/Hong_Kong"),
    ("Singapore", "Singapore", 1.3521, 103.8198, "Asia/Singapore"),
    ("Bangkok", "Thailand", 13.7563, 100.5018, "Asia/Bangkok"),
    ("Mumbai", "India", 19.0760, 72.8777, "Asia/Kolkata"),
    ("Dubai", "UAE", 25.2048, 55.2708, "Asia/Dubai"),
    ("Cairo", "Egypt", 30.0444, 31.2357, "Africa/Cairo"),
    ("Cape Town", "South Africa", -33.9249, 18.4241, "Africa/Johannesburg"),
    ("Paris", "France", 48.8566, 2.3522, "Europe/Paris"),
    ("London", "UK", 51.5074, -0.1278, "Europe/London"),
    ("Barcelona", "Spain", 41.3874, 2.1686, "Europe/Madrid"),
    ("Berlin", "Germany", 52.5200, 13.4050, "Europe/Berlin"),
    ("Rome", "Italy", 41.9028, 12.4964, "Europe/Rome"),
    ("Reykjavik", "Iceland", 64.1466, -21.9426, "Atlantic/Reykjavik"),
    ("New York", "USA", 40.7128, -74.0060, "America/New_York"),
    ("San Francisco", "USA", 37.7749, -122.4194, "America/Los_Angeles"),
    ("Toronto", "Canada", 43.6532, -79.3832, "America/Toronto"),
    ("Mexico City", "Mexico", 19.4326, -99.1332, "America/Mexico_City"),
    ("Sao Paulo", "Brazil", -23.5505, -46.6333, "America/Sao_Paulo"),
    ("Buenos Aires", "Argentina", -34.6037, -58.3816, "America/Argentina/Buenos_Aires"),
]

# WMO weather interpretation codes → short LED-friendly label
_WMO_LABELS: Dict[int, str] = {
    0: "Clear",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Rime fog",
    51: "Light drizzle",
    53: "Drizzle",
    55: "Heavy drizzle",
    56: "Freezing drizzle",
    57: "Freezing drizzle",
    61: "Light rain",
    63: "Rain",
    65: "Heavy rain",
    66: "Freezing rain",
    67: "Freezing rain",
    71: "Light snow",
    73: "Snow",
    75: "Heavy snow",
    77: "Snow grains",
    80: "Rain showers",
    81: "Rain showers",
    82: "Heavy showers",
    85: "Snow showers",
    86: "Snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm",
    99: "Thunderstorm",
}

DEFAULT_CITY_INTERVAL_SEC = 10
CACHE_TTL_SEC = 15 * 60
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"


@dataclass(frozen=True)
class WeatherSnapshot:
    city: str
    country: str
    temperature_c: Optional[float]
    feels_like_c: Optional[float]
    condition: str
    humidity: Optional[int]
    wind_kmh: Optional[float]
    weather_code: Optional[int]
    local_time: str
    fetched_at: float
    stale: bool = False

    def as_display_values(self) -> Dict[str, str]:
        temp = f"{self.temperature_c:.0f}°C" if self.temperature_c is not None else "---"
        feels = f"{self.feels_like_c:.0f}°C" if self.feels_like_c is not None else "---"
        humidity = f"{self.humidity}%" if self.humidity is not None else "---"
        wind = f"{self.wind_kmh:.0f} km/h" if self.wind_kmh is not None else "---"
        return {
            "weather_city": self.city,
            "weather_country": self.country,
            "weather_location": f"{self.city}, {self.country}",
            "weather_temp": temp,
            "weather_feels_like": feels,
            "weather_condition": self.condition or "---",
            "weather_humidity": humidity,
            "weather_wind": wind,
            "weather_local_time": self.local_time or "---",
        }


def _wmo_label(code: Optional[int]) -> str:
    if code is None:
        return "---"
    return _WMO_LABELS.get(int(code), f"Code {code}")


def _local_time_str(tz_name: str) -> str:
    try:
        return datetime.now(ZoneInfo(tz_name)).strftime("%H:%M")
    except Exception:
        return datetime.utcnow().strftime("%H:%M")


class WeatherService:
    """Rotates through world cities and caches live Open-Meteo conditions."""

    def __init__(
        self,
        *,
        city_interval_sec: float = DEFAULT_CITY_INTERVAL_SEC,
        cache_ttl_sec: float = CACHE_TTL_SEC,
    ):
        self._city_interval = max(5.0, float(city_interval_sec))
        self._cache_ttl = max(60.0, float(cache_ttl_sec))
        self._cities = list(WORLD_CITIES)
        self._index = 0
        self._city_since = 0.0
        self._cache: Dict[str, WeatherSnapshot] = {}
        self._lock = asyncio.Lock()
        self._client: Optional[httpx.AsyncClient] = None
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._prefetch_tasks: Dict[str, asyncio.Task] = {}
        # Shuffle order once so restarts feel varied
        random.shuffle(self._cities)

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(10.0, connect=5.0),
            headers={"User-Agent": "adsbledmatrix-weather/1.0"},
        )
        self._city_since = time.monotonic()
        self._task = asyncio.create_task(self._background_loop())
        # Kick off first city immediately
        asyncio.create_task(self._ensure_current())
        logger.info(
            "Weather service started (%d cities, rotate every %.0fs)",
            len(self._cities),
            self._city_interval,
        )

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        for task in list(self._prefetch_tasks.values()):
            task.cancel()
        self._prefetch_tasks.clear()
        if self._client:
            await self._client.aclose()
            self._client = None
        logger.info("Weather service stopped")

    def get_snapshot(self) -> WeatherSnapshot:
        """Synchronous snapshot for the render path (uses cache only)."""
        self._advance_city_if_needed()
        city, country, lat, lon, tz = self._cities[self._index]
        cached = self._cache.get(city)
        if cached is not None:
            # Refresh local clock display without refetch
            return WeatherSnapshot(
                city=cached.city,
                country=cached.country,
                temperature_c=cached.temperature_c,
                feels_like_c=cached.feels_like_c,
                condition=cached.condition,
                humidity=cached.humidity,
                wind_kmh=cached.wind_kmh,
                weather_code=cached.weather_code,
                local_time=_local_time_str(tz),
                fetched_at=cached.fetched_at,
                stale=cached.stale or (time.monotonic() - cached.fetched_at) > self._cache_ttl,
            )
        return WeatherSnapshot(
            city=city,
            country=country,
            temperature_c=None,
            feels_like_c=None,
            condition="Loading...",
            humidity=None,
            wind_kmh=None,
            weather_code=None,
            local_time=_local_time_str(tz),
            fetched_at=0.0,
            stale=True,
        )

    def display_values(self) -> Dict[str, str]:
        return self.get_snapshot().as_display_values()

    def _advance_city_if_needed(self) -> None:
        now = time.monotonic()
        if self._city_since <= 0:
            self._city_since = now
            return
        if (now - self._city_since) < self._city_interval:
            return
        # Advance; pick a different random city than current
        if len(self._cities) > 1:
            nxt = self._index
            while nxt == self._index:
                nxt = random.randrange(len(self._cities))
            self._index = nxt
        self._city_since = now

    async def _background_loop(self) -> None:
        while self._running:
            try:
                await self._ensure_current()
                # Prefetch the next few cities so rotation is snappy
                await self._prefetch_neighbors()
            except Exception as exc:
                logger.debug("Weather background tick error: %s", exc)
            await asyncio.sleep(2.0)

    async def _ensure_current(self) -> None:
        self._advance_city_if_needed()
        city, country, lat, lon, tz = self._cities[self._index]
        await self._fetch_city(city, country, lat, lon, tz)

    async def _prefetch_neighbors(self) -> None:
        # Prefetch a small random sample so upcoming rotations are warm
        sample = random.sample(self._cities, k=min(3, len(self._cities)))
        for city, country, lat, lon, tz in sample:
            cached = self._cache.get(city)
            if cached and (time.monotonic() - cached.fetched_at) < self._cache_ttl:
                continue
            await self._fetch_city(city, country, lat, lon, tz)

    async def _fetch_city(
        self,
        city: str,
        country: str,
        lat: float,
        lon: float,
        tz: str,
    ) -> None:
        cached = self._cache.get(city)
        if cached and (time.monotonic() - cached.fetched_at) < self._cache_ttl:
            return
        if self._client is None:
            return

        async with self._lock:
            # Re-check under lock
            cached = self._cache.get(city)
            if cached and (time.monotonic() - cached.fetched_at) < self._cache_ttl:
                return
            try:
                resp = await self._client.get(
                    OPEN_METEO_URL,
                    params={
                        "latitude": lat,
                        "longitude": lon,
                        "current": (
                            "temperature_2m,relative_humidity_2m,"
                            "apparent_temperature,weather_code,wind_speed_10m"
                        ),
                        "timezone": "auto",
                        "wind_speed_unit": "kmh",
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                current = data.get("current") or {}
                code = current.get("weather_code")
                snap = WeatherSnapshot(
                    city=city,
                    country=country,
                    temperature_c=_as_float(current.get("temperature_2m")),
                    feels_like_c=_as_float(current.get("apparent_temperature")),
                    condition=_wmo_label(code if code is None else int(code)),
                    humidity=_as_int(current.get("relative_humidity_2m")),
                    wind_kmh=_as_float(current.get("wind_speed_10m")),
                    weather_code=int(code) if code is not None else None,
                    local_time=_local_time_str(tz),
                    fetched_at=time.monotonic(),
                    stale=False,
                )
                self._cache[city] = snap
            except Exception as exc:
                logger.warning("Weather fetch failed for %s: %s", city, exc)
                if cached is None:
                    self._cache[city] = WeatherSnapshot(
                        city=city,
                        country=country,
                        temperature_c=None,
                        feels_like_c=None,
                        condition="Unavailable",
                        humidity=None,
                        wind_kmh=None,
                        weather_code=None,
                        local_time=_local_time_str(tz),
                        fetched_at=time.monotonic(),
                        stale=True,
                    )


def _as_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


weather_service = WeatherService()
