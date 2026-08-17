import csv
import json
import logging
import re
from pathlib import Path
from typing import Optional, Dict, Any
from sqlalchemy import select, insert, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Aircraft, AirlineLogo
from app.database import AsyncSessionLocal
from app.config import settings
from app.services.logo_manager import logo_manager


# Operators that should reuse another airline's logo when their own ICAO/logo
# isn't available. Key: operator name fragment (lowercase), Value: target ICAO.
_OPERATOR_LOGO_ALIASES: Dict[str, str] = {
    "qantas": "QFA",
    "qantaslink": "QFA",
    "sunstate": "QFA",
    "network aviation": "QFA",
    "national jet systems": "QFA",
    "virgin australia": "VA",
    "virgin blue": "VA",
    "jetstar": "JQ",
    "tigerair": "TGW",
    "rex": "RXA",
    "regional express": "RXA",
    "air new zealand": "ANZ",
    "alliance": "UTY",
    "fiji airways": "FJI",
    "singapore airlines": "SIA",
    "emirates": "UAE",
    "cathay pacific": "CPA",
    "malaysia airlines": "MAS",
    "british airways": "BAW",
    "united airlines": "UAL",
    "delta air lines": "DAL",
    "american airlines": "AAL",
    "lufthansa": "DLH",
    "air canada": "ACA",
}


def _load_operator_to_icao() -> Dict[str, str]:
    """Build a case-insensitive operator-name -> ICAO lookup from airlines.csv."""
    mapping: Dict[str, str] = {}
    csv_path = settings.data_dir / "airlines.csv"
    if not csv_path.exists():
        return mapping
    try:
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                icao = row.get("icao", "").strip().upper()
                name = row.get("name", "").strip()
                if icao and name:
                    mapping[name.lower()] = icao
    except Exception as e:
        logging.warning(f"Failed to load airline codes for operator lookup: {e}")
    return mapping

logger = logging.getLogger(__name__)

# Prefer the richer localadsb lookup table, fall back to project root.
_TYPE_NAMES_PATHS = [
    Path(__file__).resolve().parents[3] / "data" / "localadsb" / "aircraft_type_names.json",
    Path(__file__).resolve().parents[3] / "aircraft_type_names.json",
]


def _load_type_names() -> Dict[str, str]:
    for path in _TYPE_NAMES_PATHS:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            continue
    logger.warning("Could not load aircraft type names from any known path")
    return {}


class AircraftDatabase:
    """Manages aircraft metadata lookup and database imports."""

    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._type_names: Dict[str, str] = _load_type_names()
        self._operator_to_icao: Dict[str, str] = _load_operator_to_icao()
        self._casa_registry: Optional[Dict[str, Dict[str, Any]]] = None

    async def enrich(
        self, hex_code: str, callsign: Optional[str] = None
    ) -> Dict[str, Any]:
        """Return metadata dict for an aircraft hex code."""
        hex_code = (hex_code or "").strip().upper()
        cached = self._cache.get(hex_code)
        # Incomplete hex-only rows (no registration) can be upgraded once a
        # callsign arrives, e.g. 7C00D2 + AF4 → CASA VH-AF4.
        if cached and (cached.get("registration") or not callsign):
            return cached

        data: Dict[str, Any] = {}
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Aircraft).where(Aircraft.hex_code == hex_code)
            )
            aircraft = result.scalar_one_or_none()
            if aircraft:
                type_code = aircraft.type_code
                operator = aircraft.operator
                operator_icao = aircraft.operator_icao
                # If the aircraft DB is missing operator_icao, try to infer it
                # from the operator name using the airline codes CSV or known aliases.
                if not operator_icao and operator:
                    op_lower = operator.strip().lower()
                    operator_icao = self._operator_to_icao.get(op_lower)
                    if not operator_icao:
                        for fragment, icao in _OPERATOR_LOGO_ALIASES.items():
                            if fragment in op_lower:
                                operator_icao = icao
                                break
                data = {
                    "registration": aircraft.registration,
                    "manufacturer": aircraft.manufacturer,
                    "model": aircraft.model,
                    "type_code": type_code,
                    "type_name": self._type_names.get(type_code) if type_code else None,
                    "operator": operator,
                    "operator_icao": operator_icao,
                }

        if not data.get("registration") and callsign:
            casa = self._casa_from_callsign(hex_code, callsign)
            if casa:
                data = {**data, **casa}
                await self._persist_enrichment(hex_code, casa)

        if data:
            self._cache[hex_code] = data
        return data

    async def get_logo_path(self, icao_code: str) -> Optional[str]:
        """Return local path to airline logo if cached."""
        if not icao_code:
            return None
        path = logo_manager.logo_path_for_icao(icao_code)
        if path and path.exists():
            return str(path)
        return None

    async def import_csv(self, csv_path: Path) -> int:
        """Import aircraft data from CSV into SQLite."""
        count = 0
        async with AsyncSessionLocal() as session:
            with open(csv_path, "r", encoding="utf-8", errors="ignore") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    hex_code = row.get("hex_code", "").strip().upper()
                    if not hex_code:
                        continue

                    data = {
                        "registration": row.get("registration", "").strip() or None,
                        "manufacturer": row.get("manufacturer", "").strip() or None,
                        "model": row.get("model", "").strip() or None,
                        "type_code": row.get("type_code", "").strip().upper() or None,
                        "operator": row.get("operator", "").strip() or None,
                        "operator_icao": row.get("operator_icao", "").strip().upper() or None,
                    }

                    result = await session.execute(
                        select(Aircraft).where(Aircraft.hex_code == hex_code)
                    )
                    existing = result.scalar_one_or_none()
                    if existing:
                        await session.execute(
                            update(Aircraft)
                            .where(Aircraft.hex_code == hex_code)
                            .values(**data)
                        )
                    else:
                        await session.execute(
                            insert(Aircraft).values(hex_code=hex_code, **data)
                        )
                    count += 1

                    if count % 1000 == 0:
                        await session.commit()
                        logger.info(f"Imported {count} aircraft records...")

            await session.commit()
        logger.info(f"Aircraft database import complete: {count} records")
        return count


    def _casa_from_callsign(
        self, hex_code: str, callsign: str
    ) -> Optional[Dict[str, Any]]:
        """Fill missing hex metadata from the CASA register using the tail.

        Australian Mode-S hexes are 7Cxxxx. GA boxes often squawk the
        registration mark (AF4 for VH-AF4). Do not apply this to foreign
        hexes — Air France AF4 must not become the Angel Flight Cessna.
        """
        if not hex_code.upper().startswith("7C"):
            return None
        registry = self._casa_by_reg()
        if not registry:
            return None
        for key in self._casa_registration_keys(callsign):
            row = registry.get(key)
            if row:
                return row
        return None

    @staticmethod
    def _casa_registration_keys(callsign: str) -> list[str]:
        cs = re.sub(r"[^A-Z0-9]", "", (callsign or "").strip().upper())
        if not cs:
            return []
        keys: list[str] = []
        if cs.startswith("VH") and len(cs) == 5:
            keys.append(cs)
        if len(cs) == 3:
            keys.append(f"VH{cs}")
        return keys

    def _casa_by_reg(self) -> Dict[str, Dict[str, Any]]:
        if self._casa_registry is not None:
            return self._casa_registry
        self._casa_registry = {}
        path = settings.data_dir / "localadsb" / "aircraft_routes.db"
        if not path.exists():
            return self._casa_registry
        try:
            import sqlite3

            conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
            conn.row_factory = sqlite3.Row
            try:
                rows = conn.execute(
                    "SELECT registration, manufacturer, model, "
                    "icao_type_designator, operator_name "
                    "FROM australian_registry"
                )
                for row in rows:
                    key = re.sub(
                        r"[^A-Z0-9]", "", (row["registration"] or "").strip().upper()
                    )
                    if not key:
                        continue
                    type_code = (row["icao_type_designator"] or "").strip().upper() or None
                    operator = (row["operator_name"] or "").strip() or None
                    if operator:
                        operator = operator.title()
                    manufacturer = (row["manufacturer"] or "").strip() or None
                    if manufacturer:
                        manufacturer = manufacturer.title()
                    self._casa_registry[key] = {
                        "registration": (row["registration"] or "").strip() or None,
                        "manufacturer": manufacturer,
                        "model": (row["model"] or "").strip() or None,
                        "type_code": type_code,
                        "type_name": self._type_names.get(type_code) if type_code else None,
                        "operator": operator,
                    }
            finally:
                conn.close()
        except Exception as e:
            logger.warning("Failed to load CASA registry for enrichment: %s", e)
        return self._casa_registry

    async def _persist_enrichment(self, hex_code: str, data: Dict[str, Any]) -> None:
        """Write a CASA-derived hex→registration row so later lookups work."""
        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(Aircraft).where(Aircraft.hex_code == hex_code)
                )
                existing = result.scalar_one_or_none()
                values = {
                    "registration": data.get("registration"),
                    "manufacturer": data.get("manufacturer"),
                    "model": data.get("model"),
                    "type_code": data.get("type_code"),
                    "operator": data.get("operator"),
                }
                if existing:
                    await session.execute(
                        update(Aircraft)
                        .where(Aircraft.hex_code == hex_code)
                        .values(**values)
                    )
                else:
                    await session.execute(
                        insert(Aircraft).values(hex_code=hex_code, **values)
                    )
                await session.commit()
        except Exception as e:
            logger.debug("Failed to persist CASA enrichment for %s: %s", hex_code, e)


# Global singleton
db = AircraftDatabase()
