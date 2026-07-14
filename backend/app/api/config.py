import asyncio
import json
from typing import Optional
import httpx
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, HTTPException, Query
from app.database import get_db
from app.models import UserConfig
from app.services.readsb_service_manager import apply_receiver_source
from app.services.timezone import timezone_for_location

router = APIRouter(prefix="/api/config", tags=["config"])


class ConfigResponse(BaseModel):
    latitude: float
    longitude: float
    distance_unit: str
    altitude_unit: str
    speed_unit: str
    cycle_interval_sec: int
    display_mode: str
    cycle_count: int = 3
    proximity_focus_enabled: bool = False
    proximity_focus_km: float = 3.0
    proximity_focus_layout_id: Optional[int] = None
    layout_rotation_enabled: bool = False
    layout_playlist_ids: list = Field(default_factory=list)
    layout_rotation_interval_sec: int = 30
    interesting_alerts_enabled: bool = True
    interesting_record_range_km: float = 50.0
    interesting_rare_sightings: int = 3
    interesting_absent_days: int = 30
    interesting_warmup_days: int = 7
    interesting_layout_id: Optional[int] = None
    interesting_hold_sec: int = 8
    active_layout_id: Optional[int]
    idle_layout_id: Optional[int]
    onboarding_complete: bool
    wifi_ssid: Optional[str]
    auto_update: bool
    night_mode: bool
    night_mode_start: Optional[str]
    night_mode_end: Optional[str]
    sleep_mode: bool
    sleep_mode_start: Optional[str]
    sleep_mode_end: Optional[str]
    timezone: Optional[str]
    led_matrix_brightness: int
    receiver_source: str
    network_readsb_host: Optional[str]
    network_readsb_port: int

    model_config = ConfigDict(from_attributes=True)


class ConfigUpdate(BaseModel):
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    distance_unit: Optional[str] = None
    altitude_unit: Optional[str] = None
    speed_unit: Optional[str] = None
    cycle_interval_sec: Optional[int] = None
    display_mode: Optional[str] = None
    cycle_count: Optional[int] = None
    proximity_focus_enabled: Optional[bool] = None
    proximity_focus_km: Optional[float] = None
    proximity_focus_layout_id: Optional[int] = None
    layout_rotation_enabled: Optional[bool] = None
    layout_playlist_ids: Optional[list] = None
    layout_rotation_interval_sec: Optional[int] = None
    interesting_alerts_enabled: Optional[bool] = None
    interesting_record_range_km: Optional[float] = None
    interesting_rare_sightings: Optional[int] = None
    interesting_absent_days: Optional[int] = None
    interesting_warmup_days: Optional[int] = None
    interesting_layout_id: Optional[int] = None
    interesting_hold_sec: Optional[int] = None
    active_layout_id: Optional[int] = None
    idle_layout_id: Optional[int] = None
    onboarding_complete: Optional[bool] = None
    wifi_ssid: Optional[str] = None
    wifi_password: Optional[str] = None
    auto_update: Optional[bool] = None
    night_mode: Optional[bool] = None
    night_mode_start: Optional[str] = None
    night_mode_end: Optional[str] = None
    sleep_mode: Optional[bool] = None
    sleep_mode_start: Optional[str] = None
    sleep_mode_end: Optional[str] = None
    timezone: Optional[str] = None
    led_matrix_brightness: Optional[int] = None
    receiver_source: Optional[str] = None
    network_readsb_host: Optional[str] = None
    network_readsb_port: Optional[int] = None

    @field_validator("receiver_source")
    @classmethod
    def validate_receiver_source(cls, v):
        if v is not None and v not in ("local", "network"):
            raise ValueError("receiver_source must be 'local' or 'network'")
        return v

    @field_validator("network_readsb_port")
    @classmethod
    def validate_port(cls, v):
        if v is not None and not (1 <= v <= 65535):
            raise ValueError("network_readsb_port must be between 1 and 65535")
        return v

    @field_validator("display_mode")
    @classmethod
    def validate_display_mode(cls, v):
        if v is not None and v not in ("closest", "cycle", "cycle3", "list"):
            raise ValueError("display_mode must be 'closest', 'cycle', 'cycle3', or 'list'")
        return v

    @field_validator("cycle_count")
    @classmethod
    def validate_cycle_count(cls, v):
        if v is not None and not (1 <= v <= 10):
            raise ValueError("cycle_count must be between 1 and 10")
        return v

    @field_validator("proximity_focus_km")
    @classmethod
    def validate_proximity_focus_km(cls, v):
        if v is not None and not (0.1 <= v <= 50):
            raise ValueError("proximity_focus_km must be between 0.1 and 50")
        return v

    @field_validator("layout_rotation_interval_sec")
    @classmethod
    def validate_layout_rotation_interval(cls, v):
        if v is not None and not (5 <= v <= 600):
            raise ValueError("layout_rotation_interval_sec must be between 5 and 600")
        return v

    @field_validator("layout_playlist_ids")
    @classmethod
    def validate_layout_playlist_ids(cls, v):
        from app.services.display_selection import MAX_PLAYLIST_SIZE

        if v is None:
            return v
        if not isinstance(v, list):
            raise ValueError("layout_playlist_ids must be a list")
        if len(v) > MAX_PLAYLIST_SIZE:
            raise ValueError(f"layout_playlist_ids must have at most {MAX_PLAYLIST_SIZE} items")
        cleaned = []
        seen = set()
        for item in v:
            if not isinstance(item, int) or isinstance(item, bool) or item <= 0:
                raise ValueError("layout_playlist_ids must contain positive integers")
            if item in seen:
                continue
            seen.add(item)
            cleaned.append(item)
        return cleaned

    @field_validator("interesting_record_range_km")
    @classmethod
    def validate_interesting_record_range(cls, v):
        if v is not None and not (1.0 <= v <= 200.0):
            raise ValueError("interesting_record_range_km must be between 1 and 200")
        return v

    @field_validator("interesting_rare_sightings")
    @classmethod
    def validate_interesting_rare_sightings(cls, v):
        if v is not None and not (1 <= v <= 20):
            raise ValueError("interesting_rare_sightings must be between 1 and 20")
        return v

    @field_validator("interesting_absent_days")
    @classmethod
    def validate_interesting_absent_days(cls, v):
        if v is not None and not (1 <= v <= 60):
            raise ValueError("interesting_absent_days must be between 1 and 60")
        return v

    @field_validator("interesting_warmup_days")
    @classmethod
    def validate_interesting_warmup_days(cls, v):
        if v is not None and not (0 <= v <= 60):
            raise ValueError("interesting_warmup_days must be between 0 and 60")
        return v

    @field_validator("interesting_hold_sec")
    @classmethod
    def validate_interesting_hold_sec(cls, v):
        if v is not None and not (1 <= v <= 120):
            raise ValueError("interesting_hold_sec must be between 1 and 120")
        return v


class GeocodeResponse(BaseModel):
    display_name: str
    latitude: float
    longitude: float


class ProbeReceiverRequest(BaseModel):
    host: str
    port: int

    @field_validator("host")
    @classmethod
    def validate_host(cls, v):
        if v is None or not v.strip():
            raise ValueError("host must not be empty")
        return v

    @field_validator("port")
    @classmethod
    def validate_port(cls, v):
        if not (1 <= v <= 65535):
            raise ValueError("port must be between 1 and 65535")
        return v


class ProbeReceiverResponse(BaseModel):
    reachable: bool
    message: str


async def get_or_create_config(session: AsyncSession) -> UserConfig:
    result = await session.execute(select(UserConfig).where(UserConfig.id == 1))
    config = result.scalar_one_or_none()
    if not config:
        config = UserConfig(id=1)
        session.add(config)
        await session.commit()
        await session.refresh(config)
    return config


# In-memory config cache for synchronous access by display engine
_config_cache: Optional[UserConfig] = None

def get_user_config_sync() -> Optional[UserConfig]:
    """Synchronous helper for display engine."""
    return _config_cache

async def refresh_config_cache(session: AsyncSession) -> None:
    """Refresh the in-memory config cache."""
    global _config_cache
    result = await session.execute(select(UserConfig).where(UserConfig.id == 1))
    _config_cache = result.scalar_one_or_none()


@router.get("", response_model=ConfigResponse)
async def get_config(session: AsyncSession = Depends(get_db)):
    config = await get_or_create_config(session)
    return ConfigResponse.model_validate(config)


@router.put("", response_model=ConfigResponse)
async def update_config(update: ConfigUpdate, session: AsyncSession = Depends(get_db)):
    config = await get_or_create_config(session)
    update_data = update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(config, field, value)

    # UI shows default times for enabled modes; ensure they are persisted so the
    # display engine does not treat empty start/end as "never in window".
    if config.night_mode:
        if not config.night_mode_start:
            config.night_mode_start = "22:00"
        if not config.night_mode_end:
            config.night_mode_end = "06:00"
    if config.sleep_mode:
        if not config.sleep_mode_start:
            config.sleep_mode_start = "23:00"
        if not config.sleep_mode_end:
            config.sleep_mode_end = "06:00"

    if config.receiver_source == "network" and (not config.network_readsb_host or not config.network_readsb_host.strip()):
        raise HTTPException(
            status_code=422,
            detail="network_readsb_host is required when receiver_source is 'network'",
        )

    await session.commit()
    await session.refresh(config)

    # Auto-detect timezone from lat/long if it changed or timezone is missing
    if "latitude" in update_data or "longitude" in update_data or not config.timezone:
        detected = timezone_for_location(config.latitude, config.longitude)
        if detected and detected != config.timezone:
            config.timezone = detected
            await session.commit()
            await session.refresh(config)

    # Refresh cache
    await refresh_config_cache(session)

    # Notify receiver of location change
    if "latitude" in update_data or "longitude" in update_data:
        from app.services.adsb_receiver import receiver
        receiver.set_user_location(config.latitude, config.longitude)

    # Notify display engine of config change
    layout_fields = {
        "active_layout_id",
        "idle_layout_id",
        "proximity_focus_layout_id",
        "interesting_layout_id",
        "layout_playlist_ids",
        "layout_rotation_enabled",
    }
    if layout_fields & set(update_data.keys()):
        from app.services.layout_loader import apply_engine_layouts

        await apply_engine_layouts(config, session)

    if "led_matrix_brightness" in update_data:
        from app.services.display_engine import engine
        engine.set_brightness(config.led_matrix_brightness)

    if "interesting_record_range_km" in update_data:
        from app.services.sighting_history import sighting_history

        sighting_history.set_record_range_km(float(config.interesting_record_range_km))

    # Apply receiver source changes
    receiver_fields = {"receiver_source", "network_readsb_host", "network_readsb_port"}
    if receiver_fields & set(update_data.keys()):
        await apply_receiver_source(config)

    return ConfigResponse.model_validate(config)


NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_USER_AGENT = "ADS-B LED Display / https://github.com/BChenery/adsbledmatrix"


@router.get("/geocode", response_model=GeocodeResponse)
async def geocode_address(q: str = Query(..., min_length=1, max_length=200)):
    """Proxy a geocoding request to Nominatim (OpenStreetMap)."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(
                NOMINATIM_URL,
                params={"q": q, "format": "json", "limit": 1},
                headers={"User-Agent": NOMINATIM_USER_AGENT},
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=502,
                detail=f"Geocoding service returned an error: {e.response.status_code}",
            )
        except httpx.RequestError:
            raise HTTPException(
                status_code=503,
                detail="Geocoding service is unreachable. Please enter coordinates manually.",
            )

    try:
        results = response.json()
        if not results:
            raise HTTPException(status_code=404, detail="Address not found.")

        result = results[0]
        return GeocodeResponse(
            display_name=result["display_name"],
            latitude=float(result["lat"]),
            longitude=float(result["lon"]),
        )
    except (KeyError, ValueError, TypeError, json.JSONDecodeError) as e:
        raise HTTPException(
            status_code=502,
            detail=f"Unexpected response from geocoding service: {e}",
        )


@router.post("/test-receiver", response_model=ProbeReceiverResponse)
async def test_receiver(req: ProbeReceiverRequest):
    """Open a TCP connection to the proposed network receiver and verify SBS data if available."""
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(req.host, req.port),
            timeout=5.0,
        )
    except (OSError, asyncio.TimeoutError) as e:
        return ProbeReceiverResponse(
            reachable=False,
            message=f"Cannot connect to {req.host}:{req.port}: {e}",
        )

    try:
        line = await asyncio.wait_for(reader.readline(), timeout=5.0)
        if line.startswith(b"MSG,"):
            return ProbeReceiverResponse(
                reachable=True,
                message="Connected and receiving SBS data.",
            )
        if line:
            return ProbeReceiverResponse(
                reachable=True,
                message="Connected — unexpected data format.",
            )
        return ProbeReceiverResponse(
            reachable=True,
            message="Connected — no data yet.",
        )
    except (OSError, asyncio.TimeoutError):
        return ProbeReceiverResponse(
            reachable=True,
            message="Connected — no data yet.",
        )
    finally:
        writer.close()
        await writer.wait_closed()
