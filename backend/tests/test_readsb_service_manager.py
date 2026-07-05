import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

from app.services import readsb_service_manager as manager


@pytest.fixture
def mock_receiver(monkeypatch):
    recv = MagicMock()
    recv.set_endpoint = AsyncMock()
    monkeypatch.setattr(manager, "receiver", recv)
    return recv


@pytest.fixture
def clear_flag_file(monkeypatch, tmp_path):
    flag = tmp_path / ".network_receiver_enabled"
    monkeypatch.setattr(manager, "NETWORK_FLAG_FILE", flag)
    yield flag


def fake_config(source="local", host=None, port=30003):
    c = MagicMock()
    c.receiver_source = source
    c.network_readsb_host = host
    c.network_readsb_port = port
    return c


def test_resolve_local_config(monkeypatch):
    monkeypatch.setattr(manager.settings, "readsb_host", "127.0.0.1")
    monkeypatch.setattr(manager.settings, "readsb_port", 30003)
    c = fake_config("local")
    assert manager._resolve_receiver_config(c) == ("127.0.0.1", 30003)


def test_resolve_network_config():
    c = fake_config("network", "10.0.0.158", 30003)
    assert manager._resolve_receiver_config(c) == ("10.0.0.158", 30003)


def test_resolve_network_config_without_host_falls_back(monkeypatch):
    monkeypatch.setattr(manager.settings, "readsb_host", "127.0.0.1")
    monkeypatch.setattr(manager.settings, "readsb_port", 30003)
    c = fake_config("network", None, 30003)
    assert manager._resolve_receiver_config(c) == ("127.0.0.1", 30003)


def test_set_network_flag_creates_and_removes_file(clear_flag_file):
    assert not clear_flag_file.exists()
    manager.set_network_flag(True)
    assert clear_flag_file.exists()
    manager.set_network_flag(False)
    assert not clear_flag_file.exists()


def test_set_network_flag_touch_failure_does_not_raise(monkeypatch, caplog):
    mock_flag = MagicMock()
    mock_flag.touch.side_effect = OSError("permission denied")
    monkeypatch.setattr(manager, "NETWORK_FLAG_FILE", mock_flag)
    manager.set_network_flag(True)
    mock_flag.touch.assert_called_once_with(exist_ok=True)
    assert "Failed to update network receiver flag file" in caplog.text


def test_set_network_flag_unlink_failure_does_not_raise(monkeypatch, caplog):
    mock_flag = MagicMock()
    mock_flag.unlink.side_effect = OSError("read-only filesystem")
    monkeypatch.setattr(manager, "NETWORK_FLAG_FILE", mock_flag)
    manager.set_network_flag(False)
    mock_flag.unlink.assert_called_once_with(missing_ok=True)
    assert "Failed to update network receiver flag file" in caplog.text


def test_start_readsb_subprocess_oserror_does_not_raise(caplog):
    with patch.object(manager, "_run_systemctl") as mock_run:
        mock_run.side_effect = [MagicMock(returncode=0), OSError("permission denied")]
        manager.start_readsb()
    assert "Failed to run systemctl start readsb.service" in caplog.text


def test_stop_readsb_subprocess_oserror_does_not_raise(caplog):
    with patch.object(manager, "_run_systemctl") as mock_run:
        mock_run.side_effect = [MagicMock(returncode=0), OSError("permission denied")]
        manager.stop_readsb()
    assert "Failed to run systemctl stop readsb.service" in caplog.text


def test_is_readsb_available_subprocess_permission_error_returns_false(caplog):
    with patch.object(manager, "_run_systemctl") as mock_run:
        mock_run.side_effect = PermissionError("permission denied")
        assert manager.is_readsb_available() is False


@pytest.mark.asyncio
async def test_apply_local_config_starts_service_and_clears_flag(mock_receiver, clear_flag_file):
    c = fake_config("local")
    with patch.object(manager, "start_readsb") as mock_start, \
         patch.object(manager, "stop_readsb") as mock_stop:
        await manager.apply_receiver_source(c)

    mock_receiver.set_endpoint.assert_awaited_once_with("127.0.0.1", 30003)
    mock_start.assert_called_once()
    mock_stop.assert_not_called()
    assert not clear_flag_file.exists()


@pytest.mark.asyncio
async def test_apply_network_config_stops_service_and_sets_flag(mock_receiver, clear_flag_file):
    c = fake_config("network", "10.0.0.158", 30003)
    with patch.object(manager, "start_readsb") as mock_start, \
         patch.object(manager, "stop_readsb") as mock_stop:
        await manager.apply_receiver_source(c)

    mock_receiver.set_endpoint.assert_awaited_once_with("10.0.0.158", 30003)
    mock_stop.assert_called_once()
    mock_start.assert_not_called()
    assert clear_flag_file.exists()
