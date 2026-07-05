import pytest
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport
from app.api.system import router as system_router, trigger_update


@pytest.fixture
def app():
    app = FastAPI()
    app.include_router(system_router)
    return app


@pytest.mark.asyncio
async def test_post_update_returns_status():
    result = await trigger_update()
    assert result == {
        "status": "manual updates are applied by systemd; check status with GET /api/system/update"
    }


@pytest.mark.asyncio
async def test_status_includes_receiver_info(app, monkeypatch):
    import app.api.system as system_module
    import app.services.adsb_receiver as receiver_module

    class DummyConfig:
        receiver_source = "network"

    monkeypatch.setattr(system_module, "get_user_config_sync", lambda: DummyConfig())
    monkeypatch.setattr(
        receiver_module.ADSBReceiver, "endpoint", property(lambda self: ("10.0.0.158", 30003))
    )
    monkeypatch.setattr(receiver_module.ADSBReceiver, "connected", property(lambda self: True))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/system/status")

    assert response.status_code == 200
    data = response.json()
    assert data["receiver_source"] == "network"
    assert data["receiver_connected"] is True
    assert data["readsb_host"] == "10.0.0.158"
    assert data["readsb_port"] == 30003
