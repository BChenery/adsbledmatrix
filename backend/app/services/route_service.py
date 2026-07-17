import csv
import logging
from pathlib import Path
from typing import Optional, Dict
from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from app.database import AsyncSessionLocal
from app.models import Route

logger = logging.getLogger(__name__)


class RouteService:
    """Lookup and import flight route data."""

    def __init__(self):
        self._cache: Dict[str, Optional[Route]] = {}

    async def lookup(self, callsign: str) -> Optional[Route]:
        if not callsign:
            return None
        callsign = callsign.strip().upper()
        if not callsign:
            return None
        if callsign in self._cache:
            return self._cache[callsign]
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Route).where(Route.callsign == callsign)
            )
            route = result.scalar_one_or_none()
            # Only cache hits. Misses must re-query so a later data import
            # (install/sync) can fill routes without requiring a process restart.
            if route is not None:
                self._cache[callsign] = route
            return route

    async def import_from_csv(self, path: Path) -> int:
        """Import routes from a CSV file. Returns number of rows imported."""
        if not path.exists():
            raise FileNotFoundError(f"CSV not found: {path}")

        count = 0
        async with AsyncSessionLocal() as session:
            with open(path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    callsign = row.get("callsign", "").strip().upper()
                    origin = row.get("origin", "").strip().upper()
                    destination = row.get("destination", "").strip().upper()
                    if not callsign or not origin or not destination:
                        continue

                    stmt = sqlite_insert(Route).values(
                        callsign=callsign, origin=origin, destination=destination
                    )
                    stmt = stmt.on_conflict_do_update(
                        index_elements=["callsign"],
                        set_={"origin": origin, "destination": destination},
                    )
                    await session.execute(stmt)
                    count += 1

            await session.commit()
        self._cache.clear()
        logger.info(f"Imported {count} routes from {path}")
        return count

    async def import_from_dict(self, data: Dict[str, tuple]) -> int:
        """Import routes from a Python dict: {'CALLSIGN': ('ORIGIN', 'DEST'), ...}"""
        count = 0
        async with AsyncSessionLocal() as session:
            for callsign, (origin, destination) in data.items():
                callsign = callsign.strip().upper()
                origin = origin.strip().upper()
                destination = destination.strip().upper()
                if not callsign or not origin or not destination:
                    continue

                stmt = sqlite_insert(Route).values(
                    callsign=callsign, origin=origin, destination=destination
                )
                stmt = stmt.on_conflict_do_update(
                    index_elements=["callsign"],
                    set_={"origin": origin, "destination": destination},
                )
                await session.execute(stmt)
                count += 1

            await session.commit()
        self._cache.clear()
        logger.info(f"Imported {count} routes from dict")
        return count


# Global singleton
route_service = RouteService()
