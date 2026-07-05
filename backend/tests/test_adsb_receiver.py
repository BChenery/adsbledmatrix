import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.adsb_receiver import ADSBReceiver


@pytest.fixture
def receiver():
    return ADSBReceiver()


def test_initial_endpoint_from_settings(receiver):
    assert receiver.endpoint == ("127.0.0.1", 30003)


def test_set_endpoint_updates_values(receiver):
    receiver.set_endpoint("10.0.0.158", 30004)
    assert receiver.endpoint == ("10.0.0.158", 30004)


def test_set_endpoint_does_nothing_when_unchanged(receiver):
    receiver.set_endpoint("127.0.0.1", 30003)
    assert receiver.endpoint == ("127.0.0.1", 30003)


@pytest.mark.asyncio
async def test_set_endpoint_cancels_running_loop(receiver):
    receiver._running = True
    task = asyncio.create_task(asyncio.sleep(10))
    receiver._task = task
    receiver.set_endpoint("10.0.0.158", 30003)
    assert receiver.endpoint == ("10.0.0.158", 30003)
    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_read_loop_sets_connected_true(receiver):
    reader = AsyncMock()
    writer = MagicMock()
    reader.read.side_effect = [b"MSG,1,1,1,406A86,1,2024/01/15,12:34:56.789,2024/01/15,12:34:56.789,BAW123,\n", asyncio.CancelledError()]

    with patch("app.services.adsb_receiver.asyncio.open_connection", new_callable=AsyncMock) as mock_open:
        mock_open.return_value = (reader, writer)
        receiver._running = True
        task = asyncio.create_task(receiver._read_loop())
        await asyncio.sleep(0.1)
        receiver._running = False
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    assert receiver._connected is False
    mock_open.assert_called_once_with("127.0.0.1", 30003)
