"""Additive merge of shipped default layouts into the local database.

Policy (important for field upgrades):
- New layouts in default_layouts.json are **inserted** when missing by name.
- Existing layouts (including user-created and user-edited defaults) are
  **never** bulk-replaced or deleted by this path.
- Removing a layout from the JSON only stops shipping it to new installs; it
  does not purge that name from devices that already have it.
- Narrow additive patches may append a missing system element (e.g. weather
  icon on World Weather) without touching other elements.
"""
from __future__ import annotations

import logging
from copy import deepcopy
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Layout, LayoutElement

logger = logging.getLogger(__name__)

# Elements that should be present on long-lived system layouts. Only appended
# when the element_type is missing — never overwrites user-arranged content.
_SYSTEM_ELEMENT_GUARANTEES: Dict[str, List[Dict[str, Any]]] = {
    "World Weather": [
        {
            "element_type": "weather_icon",
            "x": 200,
            "y": 28,
            "width": 48,
            "height": 48,
            "z_index": 1,
            "color": "#ffffff",
        },
    ],
}


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
    existing_result = await session.execute(
        select(Layout).options(selectinload(Layout.elements))
    )
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
            await _ensure_system_elements(session, layout)
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

    # Also patch system layouts that may exist even if not in this JSON pass.
    for layout_name in _SYSTEM_ELEMENT_GUARANTEES:
        layout = existing_layouts.get(layout_name)
        if layout is not None:
            await _ensure_system_elements(session, layout)

    return added, len(layouts_data), active_layout, idle_layout


async def _ensure_system_elements(session: AsyncSession, layout: Layout) -> None:
    """Append guaranteed system elements when their element_type is missing."""
    guarantees = _SYSTEM_ELEMENT_GUARANTEES.get(layout.name)
    if not guarantees:
        return

    # Must attach via the relationship collection — layouts use
    # cascade delete-orphan, so orphaned LayoutElement rows are dropped on flush.
    existing_types = {
        getattr(el, "element_type", None)
        for el in (layout.elements or [])
    }
    for elem_data in guarantees:
        etype = elem_data.get("element_type")
        if not etype or etype in existing_types:
            continue
        logger.info(
            "Adding system element %s to layout %s",
            etype,
            layout.name,
        )
        layout.elements.append(LayoutElement(**elem_data))
        existing_types.add(etype)
        session.add(layout.elements[-1])
