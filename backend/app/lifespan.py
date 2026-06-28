import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.database import init_db
from app.services.adsb_receiver import receiver
from app.services.display_engine import engine
from app.services.updater import updater
from app.api.websocket import broadcast_aircraft
from app.config import settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting ADS-B LED Display...")
    await init_db()

    # Load user config and set receiver location
    from app.database import AsyncSessionLocal
    from sqlalchemy import select, delete
    from sqlalchemy.orm import selectinload
    from app.models import Layout, LayoutElement, UserConfig
    import json

    async with AsyncSessionLocal() as session:
        from app.api.config import get_or_create_config, refresh_config_cache
        config = await get_or_create_config(session)
        await refresh_config_cache(session)
        receiver.set_user_location(config.latitude, config.longitude)

        # Seed / merge default layouts
        with open(settings.default_layouts_path) as f:
            layouts_data = json.load(f)

        existing_result = await session.execute(select(Layout))
        existing_layouts = {l.name: l for l in existing_result.scalars().all()}
        active_layout = None
        idle_layout = None

        for layout_data in layouts_data:
            elements = layout_data.pop("elements", [])
            name = layout_data.get("name")

            if name in existing_layouts:
                layout = existing_layouts[name]
                # Update metadata
                for key, value in layout_data.items():
                    if key != "id":
                        setattr(layout, key, value)
                # Replace existing elements with the current defaults so that
                # layout dimension changes are reflected on existing installs.
                await session.execute(
                    delete(LayoutElement).where(LayoutElement.layout_id == layout.id)
                )
                await session.flush()
                for elem_data in elements:
                    elem = LayoutElement(layout_id=layout.id, **elem_data)
                    session.add(elem)
            else:
                logger.info(f"Seeding new default layout: {name}")
                layout = Layout(**layout_data)
                session.add(layout)
                await session.flush()
                for elem_data in elements:
                    elem = LayoutElement(layout_id=layout.id, **elem_data)
                    session.add(elem)

            if layout.name == "Idle / Scanning":
                idle_layout = layout
            elif active_layout is None:
                active_layout = layout

        if not config.active_layout_id and active_layout:
            config.active_layout_id = active_layout.id
        if not config.idle_layout_id and idle_layout:
            config.idle_layout_id = idle_layout.id
        await session.commit()
        logger.info(f"Merged {len(layouts_data)} default layouts")

        # Load active layout
        if config.active_layout_id:
            result = await session.execute(select(Layout).where(Layout.id == config.active_layout_id).options(selectinload(Layout.elements)))
            layout = result.scalar_one_or_none()
        else:
            layout = None

        if config.idle_layout_id:
            result = await session.execute(select(Layout).where(Layout.id == config.idle_layout_id).options(selectinload(Layout.elements)))
            idle = result.scalar_one_or_none()
        else:
            idle = None

        engine.set_layout(layout, idle)

    await receiver.start()
    await engine.start()

    # Start websocket broadcaster
    broadcaster = asyncio.create_task(broadcast_aircraft())

    logger.info(f"ADS-B LED Display v{settings.version} ready")
    yield

    # Shutdown
    logger.info("Shutting down...")
    broadcaster.cancel()
    try:
        await broadcaster
    except asyncio.CancelledError:
        pass

    await receiver.stop()
    await engine.stop()
    await updater.close()
