"""Additive merge of shipped default layouts into the local database.

Policy (important for field upgrades):
- New layouts in default_layouts.json are **inserted** when missing by name.
- Existing layouts (including user-created and user-edited defaults) are
  **never** updated or deleted by this path.
- Removing a layout from the JSON only stops shipping it to new installs; it
  does not purge that name from devices that already have it.
"""
from __future__ import annotations

import logging
from copy import deepcopy
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Layout, LayoutElement

logger = logging.getLogger(__name__)


async def merge_default_layouts(
    session: AsyncSession,
    layouts_data: List[Dict[str, Any]],
) -> Tuple[int, int, Optional[Layout], Optional[Layout]]:
    """Insert any default layouts that are not already present by name.

    Returns:
        (added_count, total_defaults, preferred_active, preferred_idle)
        preferred_active / preferred_idle are Layout rows to use only when
        the user config has not already chosen active/idle layouts.
    """
    existing_result = await session.execute(select(Layout))
    existing_layouts = {l.name: l for l in existing_result.scalars().all()}

    added = 0
    active_layout: Optional[Layout] = None
    idle_layout: Optional[Layout] = None

    for raw in layouts_data:
        # Deep copy so callers can reuse the loaded JSON without mutation.
        layout_data = deepcopy(raw)
        elements = layout_data.pop("elements", []) or []
        name = layout_data.get("name")
        if not name:
            logger.warning("Skipping default layout entry with no name")
            continue

        if name in existing_layouts:
            # Keep the user's copy exactly as-is (custom edits, renames of
            # content under the same name, etc.).
            layout = existing_layouts[name]
        else:
            logger.info("Seeding new default layout: %s", name)
            layout = Layout(**layout_data)
            session.add(layout)
            await session.flush()
            for elem_data in elements:
                session.add(LayoutElement(layout_id=layout.id, **elem_data))
            existing_layouts[name] = layout
            added += 1

        if layout.name == "Idle / Scanning":
            idle_layout = layout
        elif layout_data.get("is_default") or raw.get("is_default"):
            active_layout = layout
        elif active_layout is None:
            active_layout = layout

    return added, len(layouts_data), active_layout, idle_layout
