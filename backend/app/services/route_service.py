import csv
import logging
import re
from pathlib import Path
from typing import Optional, Dict, Sequence
from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from app.database import AsyncSessionLocal
from app.models import Route

logger = logging.getLogger(__name__)

# 3-letter ICAO airline code plus a numeric flight number. Leading zeros are
# padding, not a different flight: VOZ045 and VOZ45 are the same number.
_FLIGHT_CALLSIGN = re.compile(r"^([A-Z]{3})0*(\d+)$")


def callsign_lookup_keys(callsign: str) -> list[str]:
    """Callsign plus zero-padding variants for a 3-letter flight number.

    VOZ045 matches a stored VOZ45, VOZ045, or VOZ0045. VOZ45 and VOZ450 stay
    distinct because only leading zeros are removed. Other callsigns stay exact.
    """
    cs = (callsign or "").strip().upper()
    if not cs:
        return []
    keys = [cs]
    match = _FLIGHT_CALLSIGN.match(cs)
    if match:
        prefix, number = match.group(1), str(int(match.group(2)))
        keys.append(f"{prefix}{number}")
        keys.append(f"{prefix}{number.zfill(3)}")
        keys.append(f"{prefix}{number.zfill(4)}")
    seen: set[str] = set()
    unique: list[str] = []
    for key in keys:
        if key not in seen:
            seen.add(key)
            unique.append(key)
    return unique


def select_route(keys: Sequence[str], routes: Sequence[Route]) -> Optional[Route]:
    """Pick the route whose callsign appears earliest in keys.

    keys[0] is the live callsign, so an exact row wins over a padding variant.
    """
    by_callsign = {
        (route.callsign or "").strip().upper(): route
        for route in routes
        if (route.callsign or "").strip()
    }
    for key in keys:
        route = by_callsign.get(key)
        if route is not None:
            return route
    return None


class RouteService:
    """Lookup and import flight route data."""

    def __init__(self):
        self._cache: Dict[str, Optional[Route]] = {}

    async def lookup(
        self,
        callsign: str,
        registration: Optional[str] = None,
        hex_code: Optional[str] = None,
    ) -> Optional[Route]:
        if not callsign:
            return None
        callsign = callsign.strip().upper()
        if not callsign:
            return None
        # Import locally to avoid a module-level cycle with logo_manager.
        from app.services.logo_manager import logo_manager

        if logo_manager.should_skip_scheduled_route(
            callsign, registration=registration, hex_code=hex_code
        ):
            return None
        if callsign in self._cache:
            return self._cache[callsign]
        keys = callsign_lookup_keys(callsign)
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Route).where(Route.callsign.in_(keys))
            )
            route = select_route(keys, result.scalars().all())
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
