#!/usr/bin/env python3
"""Import aircraft and route data from data/localadsb/ into the app database.

Sources:
  - flights.db -> aircraft_registry (31k+ aircraft)
  - flights.db -> route_cache (2k+ routes)
  - data/localadsb/aircraft_type_names.json (type code -> model name)
"""

import json
import logging
import sqlite3
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("import_localadsb")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
LOCALADSB_DIR = DATA_DIR / "localadsb"
DB_PATH = DATA_DIR / "aircraft_db.sqlite3"
FLIGHTS_DB = LOCALADSB_DIR / "flights.db"
TYPE_NAMES_PATH = LOCALADSB_DIR / "aircraft_type_names.json"


def _load_type_names() -> dict:
    try:
        with open(TYPE_NAMES_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning("Could not load type names: %s", e)
        return {}


def _manufacturer_from_model(model: str) -> str | None:
    """Best-effort manufacturer extraction from a model name."""
    if not model:
        return None
    model_lower = model.lower()
    prefixes = [
        ("airbus", "Airbus"),
        ("boeing", "Boeing"),
        ("embraer", "Embraer"),
        ("bombardier", "Bombardier"),
        ("cessna", "Cessna"),
        ("piper", "Piper"),
        ("beech", "Beechcraft"),
        ("raytheon", "Raytheon"),
        ("gulfstream", "Gulfstream"),
        ("dassault", "Dassault"),
        ("fokker", "Fokker"),
        ("atr", "ATR"),
        ("sukhoi", "Sukhoi"),
        ("antonov", "Antonov"),
        ("mil", "Mil"),
        ("bell", "Bell"),
        ("robinson", "Robinson"),
        ("agusta", "Agusta"),
        ("eurocopter", "Eurocopter"),
        ("air tractor", "Air Tractor"),
        ("pilatus", "Pilatus"),
        ("saab", "Saab"),
        ("british aerospace", "British Aerospace"),
        ("mitsubishi", "Mitsubishi"),
        ("honda", "Honda"),
        ("cirrus", "Cirrus"),
        ("diamond", "Diamond"),
        ("mooney", "Mooney"),
        ("learjet", "Learjet"),
        ("lockheed", "Lockheed"),
        ("mcdonnell", "McDonnell Douglas"),
        ("douglas", "Douglas"),
    ]
    for token, name in prefixes:
        if token in model_lower:
            return name
    return None


def _validate_source_db(conn: sqlite3.Connection) -> None:
    """Abort if the source flights.db is missing required tables."""
    required = {"aircraft_registry", "aero_fleet", "route_cache"}
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    found = {row[0] for row in cur.fetchall()}
    missing = required - found
    if missing:
        raise RuntimeError(f"flights.db missing required tables: {sorted(missing)}")


def import_aircraft() -> int:
    if not FLIGHTS_DB.exists():
        logger.error("flights.db not found at %s", FLIGHTS_DB)
        return 0

    type_names = _load_type_names()

    src = sqlite3.connect(FLIGHTS_DB)
    src.row_factory = sqlite3.Row
    _validate_source_db(src)

    dst = sqlite3.connect(DB_PATH)
    dst.row_factory = sqlite3.Row

    # Ensure target table exists with the expected schema
    dst.execute(
        """
        CREATE TABLE IF NOT EXISTS aircraft (
            hex_code TEXT PRIMARY KEY,
            registration TEXT,
            manufacturer TEXT,
            model TEXT,
            type_code TEXT,
            operator TEXT,
            operator_icao TEXT
        )
        """
    )

    # Build operator_icao lookup from aero_fleet
    operator_icao: dict[str, str] = {}
    for row in src.execute("SELECT hex_id, airline_icao FROM aero_fleet WHERE airline_icao IS NOT NULL"):
        if row["hex_id"] and row["airline_icao"]:
            operator_icao[row["hex_id"].upper()] = row["airline_icao"].upper()

    count = 0
    for row in src.execute(
        "SELECT hex_id, registration, aircraft_type, operator FROM aircraft_registry"
    ):
        hex_code = (row["hex_id"] or "").strip().upper()
        if not hex_code:
            continue

        type_code = (row["aircraft_type"] or "").strip().upper() or None
        model = type_names.get(type_code) if type_code else None
        manufacturer = _manufacturer_from_model(model) if model else None

        dst.execute(
            """
            INSERT INTO aircraft (hex_code, registration, manufacturer, model, type_code, operator, operator_icao)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(hex_code) DO UPDATE SET
                registration=excluded.registration,
                manufacturer=COALESCE(excluded.manufacturer, aircraft.manufacturer),
                model=COALESCE(excluded.model, aircraft.model),
                type_code=COALESCE(excluded.type_code, aircraft.type_code),
                operator=COALESCE(excluded.operator, aircraft.operator),
                operator_icao=COALESCE(excluded.operator_icao, aircraft.operator_icao)
            """,
            (
                hex_code,
                (row["registration"] or "").strip() or None,
                manufacturer,
                model,
                type_code,
                (row["operator"] or "").strip() or None,
                operator_icao.get(hex_code),
            ),
        )
        count += 1
        if count % 1000 == 0:
            dst.commit()
            logger.info("Imported %d aircraft...", count)

    dst.commit()
    src.close()
    dst.close()
    logger.info("Aircraft import complete: %d records", count)
    return count


def import_routes() -> int:
    if not FLIGHTS_DB.exists():
        logger.error("flights.db not found at %s", FLIGHTS_DB)
        return 0

    src = sqlite3.connect(FLIGHTS_DB)
    dst = sqlite3.connect(DB_PATH)

    dst.execute(
        """
        CREATE TABLE IF NOT EXISTS routes (
            callsign TEXT PRIMARY KEY,
            origin TEXT NOT NULL,
            destination TEXT NOT NULL
        )
        """
    )

    count = 0
    for row in src.execute("SELECT callsign, origin, destination FROM route_cache"):
        callsign = (row[0] or "").strip().upper()
        origin = (row[1] or "").strip().upper()
        destination = (row[2] or "").strip().upper()
        if not callsign or not origin or not destination:
            continue

        dst.execute(
            """
            INSERT INTO routes (callsign, origin, destination)
            VALUES (?, ?, ?)
            ON CONFLICT(callsign) DO UPDATE SET
                origin=excluded.origin,
                destination=excluded.destination
            """,
            (callsign, origin, destination),
        )
        count += 1

    dst.commit()
    src.close()
    dst.close()
    logger.info("Route import complete: %d records", count)
    return count


def main():
    if not LOCALADSB_DIR.exists():
        logger.error("localadsb data directory not found: %s", LOCALADSB_DIR)
        sys.exit(1)

    logger.info("Importing localadsb data into %s", DB_PATH)
    aircraft_count = import_aircraft()
    routes_count = import_routes()
    logger.info("Done. Aircraft: %d, Routes: %d", aircraft_count, routes_count)


if __name__ == "__main__":
    main()
