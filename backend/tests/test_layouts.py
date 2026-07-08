import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.api import layouts
from app.api.layouts import router, get_db
from app.models import Base, Layout, UserConfig
from scripts.validate_layouts import validate


@pytest_asyncio.fixture
async def db_session():
    """Create a fresh in-memory SQLite database for each test."""
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    SessionLocal = async_sessionmaker(test_engine, expire_on_commit=False)
    async with SessionLocal() as session:
        yield session

    await test_engine.dispose()


@pytest_asyncio.fixture
async def app(db_session):
    """FastAPI app with the layouts router and an overridden DB dependency."""
    test_app = FastAPI()

    async def override_get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = override_get_db
    test_app.include_router(router)

    # Seed a user config and a layout so we can test the active-layout path.
    config = UserConfig(id=1)
    layout = Layout(name="Active", width=256, height=128)
    db_session.add(config)
    db_session.add(layout)
    await db_session.commit()
    await db_session.refresh(layout)

    config.active_layout_id = layout.id
    await db_session.commit()

    return test_app


@pytest.mark.asyncio
async def test_update_active_layout_triggers_engine_refresh(app, db_session, monkeypatch):
    """Saving the active layout should tell the display engine to reload it."""
    calls = []

    async def fake_apply(config, session=None):
        calls.append((config.active_layout_id, config.idle_layout_id))

    monkeypatch.setattr("app.services.layout_loader.apply_engine_layouts", fake_apply)

    result = await db_session.execute(select(Layout))
    layout = result.scalar_one()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.put(
            f"/api/layouts/{layout.id}",
            json={
                "elements": [
                    {"element_type": "text", "x": 0, "y": 0, "format_str": "Hello"}
                ]
            },
        )

    assert response.status_code == 200
    assert len(calls) == 1
    assert calls[0] == (layout.id, None)


@pytest.mark.asyncio
async def test_radar_element_settings_persist(app, db_session, monkeypatch):
    """Radar-specific fields should survive a save/load round trip."""
    async def fake_apply(config, session=None):
        pass

    monkeypatch.setattr("app.services.layout_loader.apply_engine_layouts", fake_apply)

    result = await db_session.execute(select(Layout))
    layout = result.scalar_one()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.put(
            f"/api/layouts/{layout.id}",
            json={
                "elements": [
                    {
                        "element_type": "radar",
                        "x": 10,
                        "y": 10,
                        "width": 80,
                        "height": 80,
                        "z_index": 0,
                        "range_km": 15,
                        "ring_color": "#444444",
                        "dot_color": "#00aaff",
                        "user_dot_color": "#ff00ff",
                        "show_rings": False,
                        "show_ticks": False,
                        "use_plane_symbol": True,
                    }
                ]
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert len(data["elements"]) == 1
    el = data["elements"][0]
    assert el["element_type"] == "radar"
    assert el["range_km"] == 15
    assert el["ring_color"] == "#444444"
    assert el["dot_color"] == "#00aaff"
    assert el["user_dot_color"] == "#ff00ff"
    assert el["show_rings"] is False
    assert el["show_ticks"] is False
    assert el["use_plane_symbol"] is True


def test_default_layouts_validate():
    """All layouts shipped in data/default_layouts.json must pass the design-system validator."""
    errors = validate()
    assert errors == [], "Default layouts failed validation: " + "; ".join(errors)
