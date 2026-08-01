"""Additive default-layout merge must never clobber user layouts."""

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import selectinload

from app.models import Base, Layout, LayoutElement
from app.services.layout_seed import merge_default_layouts


@pytest_asyncio.fixture
async def db_session():
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    SessionLocal = async_sessionmaker(test_engine, expire_on_commit=False)
    async with SessionLocal() as session:
        yield session

    await test_engine.dispose()


@pytest.mark.asyncio
async def test_merge_adds_missing_defaults_only(db_session):
    custom = Layout(
        name="My Custom Board",
        description="user made this",
        width=256,
        height=128,
        is_default=False,
    )
    existing_default = Layout(
        name="Aviation Enthusiast",
        description="user edited this description",
        width=256,
        height=128,
        is_default=True,
    )
    db_session.add_all([custom, existing_default])
    await db_session.flush()
    db_session.add(
        LayoutElement(
            layout_id=existing_default.id,
            element_type="text",
            x=0,
            y=0,
            z_index=0,
            format_str="KEEP ME",
        )
    )
    await db_session.commit()

    defaults = [
        {
            "name": "Aviation Enthusiast",
            "description": "SHIPPED description should not win",
            "width": 256,
            "height": 128,
            "is_default": True,
            "elements": [
                {
                    "element_type": "text",
                    "x": 1,
                    "y": 1,
                    "z_index": 0,
                    "format_str": "OVERWRITE ME",
                }
            ],
        },
        {
            "name": "Brand New Layout",
            "description": "fresh from the repo",
            "width": 256,
            "height": 128,
            "is_default": False,
            "elements": [
                {
                    "element_type": "text",
                    "x": 2,
                    "y": 2,
                    "z_index": 0,
                    "format_str": "NEW",
                }
            ],
        },
    ]

    added, total, active, idle = await merge_default_layouts(db_session, defaults)
    await db_session.commit()

    assert total == 2
    assert added == 1
    assert active is not None
    assert active.name == "Aviation Enthusiast"
    assert idle is None

    result = await db_session.execute(
        select(Layout).options(selectinload(Layout.elements)).order_by(Layout.name)
    )
    layouts = {l.name: l for l in result.scalars().all()}

    assert set(layouts) == {
        "My Custom Board",
        "Aviation Enthusiast",
        "Brand New Layout",
    }

    # User custom layout untouched.
    assert layouts["My Custom Board"].description == "user made this"

    # Existing default not overwritten.
    ae = layouts["Aviation Enthusiast"]
    assert ae.description == "user edited this description"
    assert len(ae.elements) == 1
    assert ae.elements[0].format_str == "KEEP ME"

    # New default inserted with its elements.
    brand = layouts["Brand New Layout"]
    assert brand.description == "fresh from the repo"
    assert len(brand.elements) == 1
    assert brand.elements[0].format_str == "NEW"


@pytest.mark.asyncio
async def test_merge_is_idempotent(db_session):
    defaults = [
        {
            "name": "Only Once",
            "description": "first",
            "width": 256,
            "height": 128,
            "is_default": False,
            "elements": [],
        }
    ]
    added1, _, _, _ = await merge_default_layouts(db_session, defaults)
    await db_session.commit()
    added2, _, _, _ = await merge_default_layouts(db_session, defaults)
    await db_session.commit()

    assert added1 == 1
    assert added2 == 0

    result = await db_session.execute(select(Layout).where(Layout.name == "Only Once"))
    assert len(result.scalars().all()) == 1


def test_default_layouts_json_has_no_pilot_view():
    import json
    from pathlib import Path

    path = Path(__file__).resolve().parents[2] / "data" / "default_layouts.json"
    layouts = json.loads(path.read_text())
    names = [l["name"] for l in layouts]
    assert "Pilot View" not in names
    assert "Aviation Enthusiast" in names
    assert len(names) == len(set(names)), "duplicate layout names in defaults"


def test_default_world_weather_includes_weather_icon():
    import json
    from pathlib import Path

    path = Path(__file__).resolve().parents[2] / "data" / "default_layouts.json"
    layouts = {l["name"]: l for l in json.loads(path.read_text())}
    weather = layouts["World Weather"]
    types = [e["element_type"] for e in weather["elements"]]
    assert "weather_icon" in types


@pytest.mark.asyncio
async def test_merge_appends_weather_icon_to_existing_world_weather(db_session):
    layout = Layout(
        name="World Weather",
        description="existing",
        width=256,
        height=128,
        is_default=False,
    )
    db_session.add(layout)
    await db_session.flush()
    db_session.add(
        LayoutElement(
            layout_id=layout.id,
            element_type="text",
            x=0,
            y=0,
            z_index=0,
            format_str="WORLD WEATHER",
        )
    )
    await db_session.commit()

    await merge_default_layouts(db_session, [])
    await db_session.commit()

    result = await db_session.execute(
        select(Layout)
        .where(Layout.name == "World Weather")
        .options(selectinload(Layout.elements))
    )
    loaded = result.scalar_one()
    types = [e.element_type for e in loaded.elements]
    assert "weather_icon" in types
    assert types.count("weather_icon") == 1

    # Idempotent — second merge does not duplicate.
    await merge_default_layouts(db_session, [])
    await db_session.commit()
    result = await db_session.execute(
        select(Layout)
        .where(Layout.name == "World Weather")
        .options(selectinload(Layout.elements))
    )
    loaded = result.scalar_one()
    assert [e.element_type for e in loaded.elements].count("weather_icon") == 1
