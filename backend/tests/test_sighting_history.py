from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.aircraft_interest import HistorySnapshot
from app.services.sighting_history import (
    RETENTION_DAYS,
    VISIT_GAP,
    SightingHistoryService,
)


def test_get_snapshot_normalizes_hex():
    svc = SightingHistoryService()
    snap = HistorySnapshot(hex_code="ABC123", sightings=2)
    svc._cache["ABC123"] = snap
    assert svc.get_snapshot("abc123") is snap


@pytest.mark.asyncio
async def test_tick_creates_first_visit():
    svc = SightingHistoryService()
    svc._loaded = True
    ac = SimpleNamespace(
        hex_code="aa11bb",
        callsign="TEST123",
        distance_km=5.0,
        is_stale=lambda: False,
    )
    receiver = SimpleNamespace(aircraft={"aa11bb": ac})

    with patch("app.services.sighting_history.SightingHistoryService._persist", new_callable=AsyncMock) as persist:
        with patch("app.api.config.get_user_config_sync", return_value=None):
            with patch("app.services.adsb_receiver.receiver", receiver):
                await svc.tick()

    assert "AA11BB" in svc._cache
    assert svc._cache["AA11BB"].sightings == 1
    persist.assert_awaited()


@pytest.mark.asyncio
async def test_tick_same_visit_does_not_inflate_sightings():
    svc = SightingHistoryService()
    now = datetime.utcnow()
    svc._cache["AA11BB"] = HistorySnapshot(
        hex_code="AA11BB",
        sightings=1,
        first_seen=now - timedelta(minutes=5),
        last_seen=now - timedelta(seconds=10),
        last_visit_start=now - timedelta(minutes=5),
        prior_gap_days=0.0,
    )
    svc._last_write_at["AA11BB"] = now  # throttle active
    ac = SimpleNamespace(
        hex_code="AA11BB",
        callsign="TEST123",
        distance_km=4.0,
        is_stale=lambda: False,
    )
    receiver = SimpleNamespace(aircraft={"AA11BB": ac})

    with patch("app.services.sighting_history.SightingHistoryService._persist", new_callable=AsyncMock) as persist:
        with patch("app.api.config.get_user_config_sync", return_value=None):
            with patch("app.services.adsb_receiver.receiver", receiver):
                await svc.tick()

    assert svc._cache["AA11BB"].sightings == 1
    persist.assert_not_awaited()


@pytest.mark.asyncio
async def test_tick_new_visit_after_gap_increments_sightings():
    svc = SightingHistoryService()
    now = datetime.utcnow()
    prev_last = now - VISIT_GAP - timedelta(minutes=1)
    svc._cache["AA11BB"] = HistorySnapshot(
        hex_code="AA11BB",
        sightings=2,
        first_seen=now - timedelta(days=10),
        last_seen=prev_last,
        last_visit_start=prev_last - timedelta(minutes=20),
        prior_gap_days=0.0,
    )
    ac = SimpleNamespace(
        hex_code="AA11BB",
        callsign="TEST123",
        distance_km=4.0,
        is_stale=lambda: False,
    )
    receiver = SimpleNamespace(aircraft={"AA11BB": ac})

    with patch("app.services.sighting_history.SightingHistoryService._persist", new_callable=AsyncMock):
        with patch("app.api.config.get_user_config_sync", return_value=None):
            with patch("app.services.adsb_receiver.receiver", receiver):
                await svc.tick()

    assert svc._cache["AA11BB"].sightings == 3
    assert svc._cache["AA11BB"].prior_gap_days >= VISIT_GAP.total_seconds() / 86400.0


@pytest.mark.asyncio
async def test_tick_ignores_outside_record_range():
    svc = SightingHistoryService()
    svc.set_record_range_km(10.0)
    ac = SimpleNamespace(
        hex_code="FAR001",
        callsign="FAR1",
        distance_km=50.0,
        is_stale=lambda: False,
    )
    receiver = SimpleNamespace(aircraft={"FAR001": ac})

    with patch("app.services.sighting_history.SightingHistoryService._persist", new_callable=AsyncMock) as persist:
        with patch("app.api.config.get_user_config_sync", return_value=None):
            with patch("app.services.adsb_receiver.receiver", receiver):
                await svc.tick()

    assert "FAR001" not in svc._cache
    persist.assert_not_awaited()


@pytest.mark.asyncio
async def test_prune_removes_old_cache_entries():
    svc = SightingHistoryService()
    old = datetime.utcnow() - timedelta(days=RETENTION_DAYS + 1)
    recent = datetime.utcnow()
    svc._cache["OLD001"] = HistorySnapshot(
        hex_code="OLD001", sightings=1, last_seen=old, first_seen=old
    )
    svc._cache["NEW001"] = HistorySnapshot(
        hex_code="NEW001", sightings=1, last_seen=recent, first_seen=recent
    )

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    # delete + count queries
    mock_result = MagicMock()
    mock_result.rowcount = 1
    mock_result.scalar = MagicMock(return_value=1)
    mock_result.all = MagicMock(return_value=[])
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.commit = AsyncMock()

    with patch("app.services.sighting_history.AsyncSessionLocal", return_value=mock_session):
        await svc.prune()

    assert "OLD001" not in svc._cache
    assert "NEW001" in svc._cache
