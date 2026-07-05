import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

from app.services import readsb_service_manager as manager


@pytest.fixture
def mock_receiver(monkeypatch):
    recv = MagicMock()
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


def test_resolve_local_config():
    c = fake_config("local")
    assert manager._resolve_receiver_config(c) == ("127.0.0.1", 30003)


def test_resolve_network_config():
    c = fake_config("network", "10.0.0.158", 30003)
    assert manager._resolve_receiver_config(c) == ("10.0.0.158", 30003)


def test_resolve_network_config_without_host_falls_back():
    c = fake_config("network", None, 30003)
    assert manager._resolve_receiver_config(c) == ("127.0.0.1", 30003)


def test_set_network_flag_creates_and_removes_file(clear_flag_file):
    assert not clear_flag_file.exists()
    manager.set_network_flag(True)
    assert clear_flag_file.exists()
    manager.set_network_flag(False)
    assert not clear_flag_file.exists()


def test_apply_local_config_starts_service_and_clears_flag(mock_receiver, clear_flag_file):
    c = fake_config("local")
    with patch.object(manager, "start_readsb") as mock_start, \
         patch.object(manager, "stop_readsb") as mock_stop:
        manager.apply_receiver_source(c)

    mock_receiver.set_endpoint.assert_called_once_with("127.0.0.1", 30003)
    mock_start.assert_called_once()
    mock_stop.assert_not_called()
    assert not clear_flag_file.exists()


def test_apply_network_config_stops_service_and_sets_flag(mock_receiver, clear_flag_file):
    c = fake_config("network", "10.0.0.158", 30003)
    with patch.object(manager, "start_readsb") as mock_start, \
         patch.object(manager, "stop_readsb") as mock_stop:
        manager.apply_receiver_source(c)

    mock_receiver.set_endpoint.assert_called_once_with("10.0.0.158", 30003)
    mock_stop.assert_called_once()
    mock_start.assert_not_called()
    assert clear_flag_file.exists()
