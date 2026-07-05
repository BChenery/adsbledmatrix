import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.api.system import trigger_update


@pytest.mark.asyncio
async def test_post_update_returns_status():
    result = await trigger_update()
    assert result == {
        "status": "manual updates are applied by systemd; check status with GET /api/system/update"
    }


@pytest.mark.asyncio
async def test_status_includes_receiver_info(monkeypatch):
    from app.api import config as config_module

    class DummyConfig:
        receiver_source = "local"

    monkeypatch.setattr(config_module, "get_user_config_sync", lambda: DummyConfig())

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/system/status")

    assert response.status_code == 200
    data = response.json()
    assert "receiver_source" in data
    assert "receiver_connected" in data
    assert "readsb_host" in data
    assert "readsb_port" in data
    assert data["receiver_source"] == "local"
