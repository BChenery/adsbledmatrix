import csv
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from sqlalchemy import select, insert, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Aircraft, AirlineLogo
from app.database import AsyncSessionLocal
from app.config import settings


# Operators that should reuse another airline's logo when their own ICAO/logo
# isn't available. Key: operator name fragment (lowercase), Value: target ICAO.
_OPERATOR_LOGO_ALIASES: Dict[str, str] = {
    "qantaslink": "QFA",
    "sunstate": "QFA",
    "network aviation": "QFA",
    "national jet systems": "QFA",
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

    async def enrich(self, hex_code: str) -> Dict[str, Any]:
        """Return metadata dict for an aircraft hex code."""
        if hex_code in self._cache:
            return self._cache[hex_code]

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Aircraft).where(Aircraft.hex_code == hex_code.upper())
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
                self._cache[hex_code] = data
                return data
            return {}

    async def get_logo_path(self, icao_code: str) -> Optional[str]:
        """Return local path to airline logo if cached."""
        if not icao_code:
            return None
        icao = icao_code.upper()
        path = settings.logos_dir / f"{icao}.png"
        if path.exists():
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


# Global singleton
db = AircraftDatabase()
