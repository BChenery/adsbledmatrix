"""Tests for designer apply/clear display endpoints."""
import pytest
from httpx import ASGITransport, AsyncClient
from fastapi import FastAPI

from app.api import display
from app.services.display_engine import engine


@pytest.fixture(autouse=True)
def clear_preview():
    engine.set_preview_layout(None)
    yield
    engine.set_preview_layout(None)


@pytest.fixture
def app():
    test_app = FastAPI()
    test_app.include_router(display.router)
    return test_app


@pytest.mark.asyncio
async def test_apply_layout_sets_preview_without_db(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/display/apply-layout",
            json={
                "name": "Draft",
                "width": 256,
                "height": 128,
                "elements": [
                    {
                        "element_type": "text",
                        "x": 4,
                        "y": 4,
                        "width": 100,
                        "height": 20,
                        "z_index": 0,
                        "format_str": "HELLO",
                        "font_size": 16,
                        "color": "#ffffff",
                    }
                ],
            },
        )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["preview_active"] is True
    assert data["element_count"] == 1

    preview = engine.get_preview_layout()
    assert preview is not None
    assert preview.width == 256
    assert preview.height == 128
    assert len(preview.elements) == 1
    assert preview.elements[0].format_str == "HELLO"


@pytest.mark.asyncio
async def test_clear_apply_removes_preview(app):
    from types import SimpleNamespace

    engine.set_preview_layout(SimpleNamespace(name="x", width=1, height=1, elements=[]))
    assert engine.get_preview_layout() is not None

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/display/clear-apply")

    assert response.status_code == 200
    assert response.json()["preview_active"] is False
    assert engine.get_preview_layout() is None


@pytest.mark.asyncio
async def test_status_reports_preview_active(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        before = await client.get("/api/display/status")
        assert before.json()["preview_active"] is False

        await client.post(
            "/api/display/apply-layout",
            json={"width": 64, "height": 32, "elements": []},
        )
        after = await client.get("/api/display/status")
        assert after.json()["preview_active"] is True
