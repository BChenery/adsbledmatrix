import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config import settings
from app.services.adsb_receiver import ADSBReceiver


@pytest.fixture
def receiver():
    return ADSBReceiver()


def test_initial_endpoint_from_settings(receiver):
    assert receiver.endpoint == (settings.readsb_host, settings.readsb_port)


@pytest.mark.asyncio
async def test_set_endpoint_updates_values(receiver):
    await receiver.set_endpoint("10.0.0.158", 30004)
    assert receiver.endpoint == ("10.0.0.158", 30004)


@pytest.mark.asyncio
async def test_set_endpoint_does_nothing_when_unchanged(receiver):
    await receiver.set_endpoint("127.0.0.1", 30003)
    assert receiver.endpoint == ("127.0.0.1", 30003)


@pytest.mark.asyncio
async def test_set_endpoint_restarts_running_loop(receiver):
    receiver._running = True
    task = asyncio.create_task(asyncio.sleep(10))
    receiver._task = task
    await receiver.set_endpoint("10.0.0.158", 30003)
    assert receiver.endpoint == ("10.0.0.158", 30003)
    with pytest.raises(asyncio.CancelledError):
        await task
    # A new task should have been created by restart
    assert receiver._task is not None
    assert receiver._task is not task
    # Clean up the restarted loop
    receiver._running = False
    receiver._task.cancel()
    try:
        await receiver._task
    except asyncio.CancelledError:
        pass


@pytest.mark.asyncio
async def test_stop_swallows_connection_reset_from_wait_closed(receiver):
    """SBS peers often RST on close; stop must not raise so config save works."""
    reader = AsyncMock()
    writer = MagicMock()
    writer.wait_closed = AsyncMock(side_effect=ConnectionResetError(104, "Connection reset by peer"))
    hold = asyncio.Event()

    async def blocking_read(*args, **kwargs):
        await hold.wait()
        return b""

    reader.read.side_effect = blocking_read

    with patch("app.services.adsb_receiver.asyncio.open_connection", new_callable=AsyncMock) as mock_open:
        mock_open.return_value = (reader, writer)
        await receiver.start()
        # Let the loop connect
        for _ in range(50):
            if receiver.connected:
                break
            await asyncio.sleep(0.02)
        assert receiver.connected is True

        await receiver.stop()

    assert receiver.connected is False
    assert receiver._task is None
    assert receiver._running is False
    writer.close.assert_called()
    writer.wait_closed.assert_awaited()


@pytest.mark.asyncio
async def test_set_endpoint_recovers_dead_task_without_endpoint_change(receiver):
    """After a failed stop leaves a done task, re-applying the same endpoint restarts."""

    async def already_failed():
        raise ConnectionResetError(104, "Connection reset by peer")

    dead = asyncio.create_task(already_failed())
    with pytest.raises(ConnectionResetError):
        await dead

    receiver._task = dead
    receiver._running = False
    receiver._readsb_host = "10.0.0.158"
    receiver._readsb_port = 30003

    with patch.object(receiver, "start", new_callable=AsyncMock) as mock_start, \
         patch.object(receiver, "stop", new_callable=AsyncMock) as mock_stop:
        await receiver.set_endpoint("10.0.0.158", 30003)
        mock_stop.assert_awaited_once()
        mock_start.assert_awaited_once()


@pytest.mark.asyncio
async def test_read_loop_sets_connected_true(receiver):
    reader = AsyncMock()
    writer = MagicMock()
    writer.wait_closed = AsyncMock()
    read_started = asyncio.Event()

    async def slow_read(*args, **kwargs):
        read_started.set()
        await asyncio.sleep(0.5)
        return b""

    reader.read.side_effect = slow_read

    with patch("app.services.adsb_receiver.asyncio.open_connection", new_callable=AsyncMock) as mock_open:
        mock_open.return_value = (reader, writer)
        receiver._running = True
        task = asyncio.create_task(receiver._read_loop())
        await read_started.wait()
        assert receiver._connected is True
        receiver._running = False
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    assert receiver._connected is False
    writer.close.assert_called_once()
    writer.wait_closed.assert_awaited_once()
    mock_open.assert_called_once_with("127.0.0.1", 30003)
