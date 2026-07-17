import pytest
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, MagicMock
from app.api.system import router as system_router, trigger_update


@pytest.fixture
def app():
    app = FastAPI()
    app.include_router(system_router)
    return app


@pytest.mark.asyncio
async def test_post_update_starts_service_when_not_running(tmp_path, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "data_dir", tmp_path)
    with patch("app.api.system.subprocess.run") as mock_run, \
         patch("app.api.system.write_update_progress") as mock_write:
        mock_run.side_effect = [
            MagicMock(returncode=3, stdout="inactive\n", stderr=""),  # is-active
            MagicMock(returncode=0, stdout="", stderr=""),  # sudo systemctl start
        ]
        result = await trigger_update()

    assert result["status"] == "started"
    assert "Progress will appear" in result["message"]
    assert "started_at" in result
    assert mock_run.call_count == 2
    start_cmd = mock_run.call_args_list[1].args[0]
    assert start_cmd[:3] == ["sudo", "-n", "systemctl"]
    assert "adsbledmatrix-update.service" in start_cmd
    mock_write.assert_called_once()
    assert mock_write.call_args.kwargs["status"] == "checking"
    assert mock_write.call_args.kwargs["progress"] == 0
    assert (tmp_path / ".force_update").exists()


@pytest.mark.asyncio
async def test_post_update_reports_already_running():
    with patch("app.api.system.subprocess.run") as mock_run, \
         patch("app.api.system.write_update_progress") as mock_write:
        mock_run.return_value = MagicMock(returncode=0, stdout="activating\n", stderr="")
        result = await trigger_update()

    assert result["status"] == "already_running"
    mock_run.assert_called_once()
    mock_write.assert_not_called()


@pytest.mark.asyncio
async def test_post_update_reports_error_when_systemctl_fails(tmp_path, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "data_dir", tmp_path)
    with patch("app.api.system.subprocess.run") as mock_run, \
         patch("app.api.system.write_update_progress") as mock_write:
        mock_run.side_effect = [
            MagicMock(returncode=3, stdout="inactive\n", stderr=""),
            MagicMock(returncode=1, stdout="", stderr="Interactive authentication required."),
        ]
        result = await trigger_update()

    assert result["status"] == "error"
    assert "Interactive authentication required" in result["message"]
    assert mock_write.call_count == 2
    assert mock_write.call_args_list[-1].kwargs["status"] == "failed"
    assert not (tmp_path / ".force_update").exists()


@pytest.mark.asyncio
async def test_get_update_progress_returns_idle_by_default(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/system/update-progress")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "idle"
    assert data["progress"] == 0


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



@pytest.mark.asyncio
async def test_wifi_scan_returns_networks(app):
    payload = '{"networks": [{"ssid": "HomeNet", "signal": 82, "secured": true}]}'
    with patch("app.api.system.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=payload, stderr="")
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/system/wifi/networks")

    assert response.status_code == 200
    data = response.json()
    assert data["networks"] == [{"ssid": "HomeNet", "signal": 82, "secured": True}]
    assert data["error"] is None
    cmd = mock_run.call_args.args[0]
    assert cmd[:2] == ["sudo", "-n"]
    assert cmd[-1] == "scan"


@pytest.mark.asyncio
async def test_wifi_scan_command_missing_returns_empty_networks(app):
    with patch("app.api.system.subprocess.run", side_effect=FileNotFoundError("sudo")):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/system/wifi/networks")

    assert response.status_code == 200
    data = response.json()
    assert data["networks"] == []
    assert data["error"] == "scan_unavailable"


@pytest.mark.asyncio
async def test_wifi_scan_timeout_returns_empty_networks(app):
    import subprocess as sp

    with patch(
        "app.api.system.subprocess.run",
        side_effect=sp.TimeoutExpired(cmd="scan", timeout=15),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/system/wifi/networks")

    assert response.status_code == 200
    assert response.json()["networks"] == []
    assert response.json()["error"] == "scan_unavailable"


@pytest.mark.asyncio
async def test_wifi_scan_unparseable_output_returns_empty_networks(app):
    with patch("app.api.system.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stdout="not json", stderr="boom")
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/system/wifi/networks")

    assert response.status_code == 200
    assert response.json()["networks"] == []
    assert response.json()["error"] == "scan_unavailable"


@pytest.mark.asyncio
async def test_wifi_scan_propagates_manager_error_field(app):
    payload = '{"networks": [], "error": "iw scan failed"}'
    with patch("app.api.system.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=payload, stderr="")
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/system/wifi/networks")

    assert response.status_code == 200
    data = response.json()
    assert data["networks"] == []
    assert data["error"] == "iw scan failed"
