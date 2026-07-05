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
