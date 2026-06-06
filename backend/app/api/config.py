from typing import Optional
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, HTTPException
from app.database import get_db
from app.models import UserConfig, Layout

router = APIRouter(prefix="/api/config", tags=["config"])


class ConfigResponse(BaseModel):
    latitude: float
    longitude: float
    distance_unit: str
    altitude_unit: str
    speed_unit: str
    cycle_interval_sec: int
    display_mode: str
    active_layout_id: Optional[int]
    idle_layout_id: Optional[int]
    onboarding_complete: bool
    wifi_ssid: Optional[str]
    auto_update: bool
    night_mode: bool
    night_mode_start: Optional[str]
    night_mode_end: Optional[str]

    class Config:
        from_attributes = True


class ConfigUpdate(BaseModel):
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    distance_unit: Optional[str] = None
    altitude_unit: Optional[str] = None
    speed_unit: Optional[str] = None
    cycle_interval_sec: Optional[int] = None
    display_mode: Optional[str] = None
    active_layout_id: Optional[int] = None
    idle_layout_id: Optional[int] = None
    onboarding_complete: Optional[bool] = None
    wifi_ssid: Optional[str] = None
    wifi_password: Optional[str] = None
    auto_update: Optional[bool] = None
    night_mode: Optional[bool] = None
    night_mode_start: Optional[str] = None
    night_mode_end: Optional[str] = None


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

    await session.commit()
    await session.refresh(config)

    # Refresh cache
    await refresh_config_cache(session)

    # Notify receiver of location change
    if "latitude" in update_data or "longitude" in update_data:
        from app.services.adsb_receiver import receiver
        receiver.set_user_location(config.latitude, config.longitude)

    # Notify display engine of config change
    if "active_layout_id" in update_data or "idle_layout_id" in update_data:
        from app.services.display_engine import engine
        from app.database import AsyncSessionLocal
        from sqlalchemy.orm import selectinload
        async with AsyncSessionLocal() as s:
            layout = None
            idle = None
            if config.active_layout_id:
                r = await s.execute(select(Layout).where(Layout.id == config.active_layout_id).options(selectinload(Layout.elements)))
                layout = r.scalar_one_or_none()
            if config.idle_layout_id:
                r = await s.execute(select(Layout).where(Layout.id == config.idle_layout_id).options(selectinload(Layout.elements)))
                idle = r.scalar_one_or_none()
            engine.set_layout(layout, idle)

    return ConfigResponse.model_validate(config)
