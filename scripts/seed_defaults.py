#!/usr/bin/env python3
"""Seed default layouts and config into the database."""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.database import init_db, AsyncSessionLocal
from app.models import Layout, LayoutElement, UserConfig
from sqlalchemy import select


async def seed():
    await init_db()

    async with AsyncSessionLocal() as session:
        # Check if layouts already exist
        result = await session.execute(select(Layout))
        if result.scalars().first():
            print("Layouts already seeded.")
            return

        # Load default layouts
        layouts_path = Path(__file__).resolve().parent.parent / "data" / "default_layouts.json"
        with open(layouts_path) as f:
            layouts = json.load(f)

        for layout_data in layouts:
            elements = layout_data.pop("elements", [])
            layout = Layout(**layout_data)
            session.add(layout)
            await session.flush()

            for elem_data in elements:
                elem = LayoutElement(layout_id=layout.id, **elem_data)
                session.add(elem)

        # Ensure default config exists
        result = await session.execute(select(UserConfig).where(UserConfig.id == 1))
        if not result.scalar_one_or_none():
            config = UserConfig(id=1)
            session.add(config)

        await session.commit()
        print(f"Seeded {len(layouts)} default layouts.")


if __name__ == "__main__":
    asyncio.run(seed())
