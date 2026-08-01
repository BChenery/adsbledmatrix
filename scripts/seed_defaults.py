#!/usr/bin/env python3
"""Seed / merge default layouts and config into the database.

Safe for upgrades: only **adds** missing default layouts by name. Never
overwrites or deletes layouts users have created or edited.
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.database import init_db, AsyncSessionLocal
from app.models import UserConfig
from app.services.layout_seed import merge_default_layouts
from sqlalchemy import select


async def seed():
    await init_db()

    layouts_path = Path(__file__).resolve().parent.parent / "data" / "default_layouts.json"
    with open(layouts_path) as f:
        layouts = json.load(f)

    async with AsyncSessionLocal() as session:
        added, total, active_layout, idle_layout = await merge_default_layouts(
            session, layouts
        )

        # Ensure default config exists
        result = await session.execute(select(UserConfig).where(UserConfig.id == 1))
        config = result.scalar_one_or_none()
        if not config:
            config = UserConfig(id=1)
            session.add(config)
            await session.flush()

        if not config.active_layout_id and active_layout:
            config.active_layout_id = active_layout.id
        if not config.idle_layout_id and idle_layout:
            config.idle_layout_id = idle_layout.id

        await session.commit()
        print(
            f"Default layouts: {total} shipped, {added} newly added "
            f"(existing layouts left untouched)."
        )


if __name__ == "__main__":
    asyncio.run(seed())
