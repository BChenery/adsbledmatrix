"""Local per-hex sighting history for interesting-aircraft alerts.

Stores one row per ICAO hex (visit-level), prunes after 60 days, and keeps an
in-memory cache so the display render path never hits SQLite.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional

from sqlalchemy import delete, func, select

from app.database import AsyncSessionLocal
from app.models import SeenAircraftHistory
from app.services.aircraft_interest import HistorySnapshot, SiteBaseline

logger = logging.getLogger(__name__)

RETENTION_DAYS = 60
MAX_ROWS = 20_000
VISIT_GAP = timedelta(minutes=30)
UPDATE_THROTTLE = timedelta(seconds=60)
LOOP_INTERVAL_SEC = 20
DEFAULT_RECORD_RANGE_KM = 50.0


class SightingHistoryService:
    def __init__(self) -> None:
        self._cache: Dict[str, HistorySnapshot] = {}
        self._baseline = SiteBaseline()
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._last_write_at: Dict[str, datetime] = {}
        self._record_range_km = DEFAULT_RECORD_RANGE_KM
        self._loaded = False
        self._ticks_since_prune = 0

    @property
    def baseline(self) -> SiteBaseline:
        return self._baseline

    def get_snapshot(self, hex_code: str) -> Optional[HistorySnapshot]:
        return self._cache.get((hex_code or "").upper())

    def set_record_range_km(self, km: float) -> None:
        self._record_range_km = max(1.0, float(km))

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        await self.load_cache()
        self._task = asyncio.create_task(self._loop())
        logger.info("Sighting history service started (%d hexes cached)", len(self._cache))

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("Sighting history service stopped")

    async def load_cache(self) -> None:
        """Load retained history into memory."""
        async with AsyncSessionLocal() as session:
            cutoff = datetime.utcnow() - timedelta(days=RETENTION_DAYS)
            result = await session.execute(
                select(SeenAircraftHistory).where(
                    SeenAircraftHistory.last_seen >= cutoff
                )
            )
            rows = result.scalars().all()
            cache: Dict[str, HistorySnapshot] = {}
            earliest: Optional[datetime] = None
            for row in rows:
                hex_code = (row.hex_code or "").upper()
                if not hex_code:
                    continue
                first_seen = row.first_seen
                if first_seen and (earliest is None or first_seen < earliest):
                    earliest = first_seen
                cache[hex_code] = HistorySnapshot(
                    hex_code=hex_code,
                    sightings=int(row.sightings or 1),
                    first_seen=row.first_seen,
                    last_seen=row.last_seen,
                    last_visit_start=row.last_visit_start or row.first_seen,
                    prior_gap_days=0.0,
                )
            self._cache = cache
            self._baseline = SiteBaseline(
                earliest_first_seen=earliest,
                unique_hexes=len(cache),
            )
            self._loaded = True

    async def _loop(self) -> None:
        while self._running:
            try:
                await self.tick()
            except Exception as exc:
                logger.exception("Sighting history tick failed: %s", exc)
            await asyncio.sleep(LOOP_INTERVAL_SEC)

    async def tick(self) -> None:
        """Process live aircraft into visit history (throttled)."""
        from app.api.config import get_user_config_sync
        from app.services.adsb_receiver import receiver

        config = get_user_config_sync()
        if config is not None:
            range_km = getattr(config, "interesting_record_range_km", None)
            if range_km is not None:
                self.set_record_range_km(float(range_km))

        now = datetime.utcnow()
        live = list(receiver.aircraft.values())
        to_upsert: list[dict] = []

        for ac in live:
            if ac.is_stale():
                continue
            dist = ac.distance_km
            if dist is None or dist > self._record_range_km:
                continue
            hex_code = (ac.hex_code or "").upper()
            if not hex_code:
                continue

            last_write = self._last_write_at.get(hex_code)
            existing = self._cache.get(hex_code)
            new_visit = False
            prior_gap_days = existing.prior_gap_days if existing else 0.0

            if existing is None:
                new_visit = True
                sightings = 1
                first_seen = now
                last_visit_start = now
                prior_gap_days = 0.0
            else:
                first_seen = existing.first_seen or now
                last_seen_prev = existing.last_seen or existing.last_visit_start or now
                gap = now - last_seen_prev
                if gap >= VISIT_GAP:
                    new_visit = True
                    prior_gap_days = gap.total_seconds() / 86400.0
                    sightings = int(existing.sightings or 1) + 1
                    last_visit_start = now
                else:
                    sightings = int(existing.sightings or 1)
                    last_visit_start = existing.last_visit_start or first_seen
                    # Throttle same-visit last_seen updates.
                    if last_write and (now - last_write) < UPDATE_THROTTLE:
                        # Still refresh min distance in cache lightly.
                        continue

            min_distance = dist
            max_distance = dist
            # Preserve extrema from cache when possible.
            if existing and existing.last_seen is not None:
                # min/max not stored on snapshot fully — re-read on write from DB row
                pass

            snapshot = HistorySnapshot(
                hex_code=hex_code,
                sightings=sightings,
                first_seen=first_seen,
                last_seen=now,
                last_visit_start=last_visit_start,
                prior_gap_days=prior_gap_days,
            )
            self._cache[hex_code] = snapshot
            self._last_write_at[hex_code] = now

            to_upsert.append(
                {
                    "hex_code": hex_code,
                    "callsign": ac.callsign,
                    "distance_km": dist,
                    "sightings": sightings,
                    "first_seen": first_seen,
                    "last_seen": now,
                    "last_visit_start": last_visit_start,
                    "new_visit": new_visit,
                }
            )

        if to_upsert:
            await self._persist(to_upsert)
            self._recompute_baseline()

        self._ticks_since_prune += 1
        # Prune roughly every ~15 minutes of ticks (20s * 45).
        if self._ticks_since_prune >= 45:
            self._ticks_since_prune = 0
            await self.prune()

    def _recompute_baseline(self) -> None:
        earliest: Optional[datetime] = None
        for snap in self._cache.values():
            if snap.first_seen and (earliest is None or snap.first_seen < earliest):
                earliest = snap.first_seen
        self._baseline = SiteBaseline(
            earliest_first_seen=earliest,
            unique_hexes=len(self._cache),
        )

    async def _persist(self, rows: list[dict]) -> None:
        async with AsyncSessionLocal() as session:
            for item in rows:
                hex_code = item["hex_code"]
                result = await session.execute(
                    select(SeenAircraftHistory).where(
                        SeenAircraftHistory.hex_code == hex_code
                    )
                )
                row = result.scalar_one_or_none()
                dist = item["distance_km"]
                if row is None:
                    row = SeenAircraftHistory(
                        hex_code=hex_code,
                        callsign=item.get("callsign"),
                        first_seen=item["first_seen"],
                        last_seen=item["last_seen"],
                        last_visit_start=item["last_visit_start"],
                        sightings=item["sightings"],
                        min_distance=dist,
                        max_distance=dist,
                    )
                    session.add(row)
                else:
                    row.callsign = item.get("callsign") or row.callsign
                    row.last_seen = item["last_seen"]
                    row.sightings = item["sightings"]
                    row.last_visit_start = item["last_visit_start"]
                    if row.min_distance is None or dist < row.min_distance:
                        row.min_distance = dist
                    if row.max_distance is None or dist > row.max_distance:
                        row.max_distance = dist
            await session.commit()

    async def prune(self) -> int:
        """Delete rows older than retention; enforce max row cap. Returns deleted count."""
        cutoff = datetime.utcnow() - timedelta(days=RETENTION_DAYS)
        deleted = 0
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                delete(SeenAircraftHistory).where(
                    SeenAircraftHistory.last_seen < cutoff
                )
            )
            deleted += result.rowcount or 0

            count_result = await session.execute(
                select(func.count()).select_from(SeenAircraftHistory)
            )
            total = int(count_result.scalar() or 0)
            if total > MAX_ROWS:
                overflow = total - MAX_ROWS
                # Delete oldest by last_seen
                old = await session.execute(
                    select(SeenAircraftHistory.id)
                    .order_by(SeenAircraftHistory.last_seen.asc())
                    .limit(overflow)
                )
                ids = [r[0] for r in old.all()]
                if ids:
                    result = await session.execute(
                        delete(SeenAircraftHistory).where(
                            SeenAircraftHistory.id.in_(ids)
                        )
                    )
                    deleted += result.rowcount or 0

            await session.commit()

        # Drop expired from cache
        now = datetime.utcnow()
        expired = [
            h
            for h, snap in self._cache.items()
            if snap.last_seen and (now - snap.last_seen) > timedelta(days=RETENTION_DAYS)
        ]
        for h in expired:
            self._cache.pop(h, None)
            self._last_write_at.pop(h, None)
        if expired or deleted:
            self._recompute_baseline()
            logger.info(
                "Sighting history prune: deleted=%d cache_expired=%d remaining=%d",
                deleted,
                len(expired),
                len(self._cache),
            )
        return deleted

    def stats(self) -> dict:
        return {
            "tracked_hexes": len(self._cache),
            "earliest_first_seen": (
                self._baseline.earliest_first_seen.isoformat()
                if self._baseline.earliest_first_seen
                else None
            ),
            "record_range_km": self._record_range_km,
        }


# Process-wide singleton used by lifespan + display engine.
sighting_history = SightingHistoryService()
