"""Load layouts from the DB and apply them to the display engine."""
from __future__ import annotations

from typing import Any, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Layout, UserConfig
from app.services.display_selection import resolve_playlist_ids


async def load_layouts_for_config(
    session: AsyncSession,
    config: UserConfig,
) -> tuple[Optional[Any], Optional[Any], Optional[Any], List[Any], bool, Optional[Any]]:
    """Return (active, idle, focus, playlist, rotation_enabled, interesting) for a config row."""
    active = None
    idle = None
    focus = None
    interesting = None
    playlist: List[Any] = []

    if config.active_layout_id:
        result = await session.execute(
            select(Layout)
            .where(Layout.id == config.active_layout_id)
            .options(selectinload(Layout.elements))
        )
        active = result.scalar_one_or_none()

    if config.idle_layout_id:
        result = await session.execute(
            select(Layout)
            .where(Layout.id == config.idle_layout_id)
            .options(selectinload(Layout.elements))
        )
        idle = result.scalar_one_or_none()

    if config.proximity_focus_layout_id:
        result = await session.execute(
            select(Layout)
            .where(Layout.id == config.proximity_focus_layout_id)
            .options(selectinload(Layout.elements))
        )
        focus = result.scalar_one_or_none()

    interesting_layout_id = getattr(config, "interesting_layout_id", None)
    if interesting_layout_id:
        result = await session.execute(
            select(Layout)
            .where(Layout.id == interesting_layout_id)
            .options(selectinload(Layout.elements))
        )
        interesting = result.scalar_one_or_none()

    playlist_ids = resolve_playlist_ids(config.layout_playlist_ids, config.active_layout_id)
    if playlist_ids:
        result = await session.execute(
            select(Layout)
            .where(Layout.id.in_(playlist_ids))
            .options(selectinload(Layout.elements))
        )
        by_id = {lay.id: lay for lay in result.scalars().all()}
        playlist = [by_id[i] for i in playlist_ids if i in by_id]

    return active, idle, focus, playlist, bool(config.layout_rotation_enabled), interesting


async def apply_engine_layouts(config: UserConfig, session: Optional[AsyncSession] = None) -> None:
    """Reload layouts for config and push them to the display engine."""
    from app.database import AsyncSessionLocal
    from app.services.display_engine import engine

    if session is not None:
        active, idle, focus, playlist, rotation, interesting = await load_layouts_for_config(
            session, config
        )
        engine.set_layout(
            active,
            idle,
            focus_layout=focus,
            playlist=playlist,
            rotation_enabled=rotation,
            interesting_layout=interesting,
        )
        return

    async with AsyncSessionLocal() as refresh_session:
        active, idle, focus, playlist, rotation, interesting = await load_layouts_for_config(
            refresh_session, config
        )
        engine.set_layout(
            active,
            idle,
            focus_layout=focus,
            playlist=playlist,
            rotation_enabled=rotation,
            interesting_layout=interesting,
        )
