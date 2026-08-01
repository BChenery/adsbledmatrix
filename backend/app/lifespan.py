import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.database import init_db, migrate_db
from app.services.adsb_receiver import receiver
from app.services.display_engine import engine
from app.services.readsb_service_manager import apply_receiver_source
from app.services.updater import updater
from app.api.websocket import broadcast_aircraft
from app.config import settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting ADS-B LED Display...")
    await init_db()
    await migrate_db()

    # Load user config and set receiver location
    from app.database import AsyncSessionLocal
    import json

    async with AsyncSessionLocal() as session:
        from app.api.config import get_or_create_config, refresh_config_cache
        from app.services.timezone import timezone_for_location
        config = await get_or_create_config(session)
        if not config.timezone:
            detected = timezone_for_location(config.latitude, config.longitude)
            if detected:
                config.timezone = detected
                await session.commit()
                await session.refresh(config)
        await refresh_config_cache(session)
        receiver.set_user_location(config.latitude, config.longitude)
        await apply_receiver_source(config)

        # Additive merge: insert any new shipped defaults by name.
        # Never overwrite or delete layouts users already have.
        from app.services.layout_seed import merge_default_layouts

        with open(settings.default_layouts_path) as f:
            layouts_data = json.load(f)

        added, total, active_layout, idle_layout = await merge_default_layouts(
            session, layouts_data
        )

        if not config.active_layout_id and active_layout:
            config.active_layout_id = active_layout.id
        if not config.idle_layout_id and idle_layout:
            config.idle_layout_id = idle_layout.id
        await session.commit()
        logger.info(
            "Default layouts: %d shipped, %d newly added (existing user layouts kept)",
            total,
            added,
        )

        from app.services.layout_loader import apply_engine_layouts

        await apply_engine_layouts(config, session)
        engine.set_brightness(config.led_matrix_brightness)
        needs_onboarding = not config.onboarding_complete

    await receiver.start()
    await engine.start()

    from app.services.weather_service import weather_service

    await weather_service.start()

    # While onboarding is incomplete the matrix itself shows how to connect.
    if needs_onboarding:
        from app.services.onboarding_display import show_setup_screen

        show_setup_screen()

    from app.api.config import get_user_config_sync
    from app.services.sighting_history import sighting_history

    cached = get_user_config_sync()
    if cached is not None:
        range_km = getattr(cached, "interesting_record_range_km", None)
        if range_km is not None:
            sighting_history.set_record_range_km(float(range_km))
    await sighting_history.start()

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

    await sighting_history.stop()
    await weather_service.stop()
    await receiver.stop()
    await engine.stop()
    await updater.close()
