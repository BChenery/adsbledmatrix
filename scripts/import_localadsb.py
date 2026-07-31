#!/usr/bin/env python3
"""Import aircraft and route data from data/localadsb/ into the app database.

Sources:
  - flights.db -> aircraft_registry (31k+ aircraft; seen traffic, sometimes stale type)
  - flights.db -> aero_fleet (curated fleet types — preferred when present)
  - flights.db -> australian_registry (CASA-style types for VH- regs)
  - flights.db -> route_cache (2k+ routes)
  - data/localadsb/aircraft_type_names.json (type code -> model name)

Type resolution priority (first hit wins):
  1. aero_fleet.aircraft_type
  2. australian_registry.icao_type_designator (matched by registration)
  3. aircraft_registry.variant mapped to an ICAO designator when possible
  4. aircraft_registry.aircraft_type (ADS-B / hexdb style — can be wrong after re-reg)
"""

import json
import logging
import re
import sqlite3
import sys
from pathlib import Path
from typing import Dict, Optional, Tuple

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


def _norm_reg(registration: Optional[str]) -> str:
    if not registration:
        return ""
    return re.sub(r"[^A-Z0-9]", "", registration.strip().upper())


def _icao_from_variant(variant: Optional[str], type_names: dict) -> Optional[str]:
    """Map a marketing/variant string (e.g. A321-251NX) to an ICAO type code."""
    if not variant:
        return None
    raw = variant.strip()
    if not raw:
        return None
    upper = raw.upper().replace(" ", "")
    # Already an ICAO designator we know
    if upper in type_names:
        return upper
    # Common Airbus neo family marketing codes
    if upper.startswith("A321") and ("NX" in upper or "NEO" in upper):
        return "A21N"
    if upper.startswith("A320") and ("NX" in upper or "NEO" in upper):
        return "A20N"
    if upper.startswith("A319") and ("NX" in upper or "NEO" in upper):
        return "A19N"
    if upper.startswith("A330") and ("NEO" in upper or "900" in upper or "N" == upper[-1:]):
        if "800" in upper:
            return "A338"
        return "A339"
    if upper.startswith("B737") or upper.startswith("737"):
        if "MAX8" in upper or "8-" in upper or upper.endswith("8"):
            return "B38M"
        if "MAX9" in upper or "9-" in upper:
            return "B39M"
        if "MAX10" in upper or "10" in upper:
            return "B3XM"
    # Bare "A321-251NX" style: take leading type token if it is known
    token = re.split(r"[-/]", upper)[0]
    if token in type_names:
        return token
    return None


def _resolve_type_and_model(
    *,
    registry_type: Optional[str],
    variant: Optional[str],
    fleet_type: Optional[str],
    au_type: Optional[str],
    au_model: Optional[str],
    au_manufacturer: Optional[str],
    type_names: dict,
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Return (type_code, model, manufacturer) using preferred sources first."""
    type_code = None
    for candidate in (fleet_type, au_type, _icao_from_variant(variant, type_names), registry_type):
        if candidate:
            cleaned = candidate.strip().upper()
            if cleaned:
                type_code = cleaned
                break

    model = None
    if au_model and au_model.strip():
        model = au_model.strip()
    elif type_code and type_code in type_names:
        model = type_names[type_code]
    elif variant and variant.strip():
        model = variant.strip()

    manufacturer = None
    if au_manufacturer and au_manufacturer.strip():
        manufacturer = au_manufacturer.strip().title()
        if manufacturer.upper() == "AIRBUS":
            manufacturer = "Airbus"
        elif manufacturer.upper() == "BOEING":
            manufacturer = "Boeing"
    if not manufacturer and model:
        manufacturer = _manufacturer_from_model(model)

    return type_code, model, manufacturer


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

    # Curated fleet types + airline ICAO (preferred over ADS-B-seen registry types)
    fleet_type: Dict[str, str] = {}
    operator_icao: Dict[str, str] = {}
    for row in src.execute(
        "SELECT hex_id, aircraft_type, airline_icao FROM aero_fleet"
    ):
        hex_id = (row["hex_id"] or "").strip().upper()
        if not hex_id:
            continue
        if row["aircraft_type"]:
            fleet_type[hex_id] = row["aircraft_type"].strip().upper()
        if row["airline_icao"]:
            operator_icao[hex_id] = row["airline_icao"].strip().upper()

    # Australian civil registry (authoritative for VH- types when present)
    au_by_reg: Dict[str, Tuple[Optional[str], Optional[str], Optional[str]]] = {}
    try:
        for row in src.execute(
            "SELECT registration, icao_type_designator, model, manufacturer "
            "FROM australian_registry"
        ):
            key = _norm_reg(row["registration"])
            if not key:
                continue
            au_by_reg[key] = (
                (row["icao_type_designator"] or "").strip().upper() or None,
                (row["model"] or "").strip() or None,
                (row["manufacturer"] or "").strip() or None,
            )
    except sqlite3.Error as exc:
        logger.warning("australian_registry unavailable: %s", exc)

    count = 0
    preferred_hits = 0
    for row in src.execute(
        "SELECT hex_id, registration, aircraft_type, operator, variant "
        "FROM aircraft_registry"
    ):
        hex_code = (row["hex_id"] or "").strip().upper()
        if not hex_code:
            continue

        registration = (row["registration"] or "").strip() or None
        registry_type = (row["aircraft_type"] or "").strip().upper() or None
        variant = (row["variant"] or "").strip() or None
        au = au_by_reg.get(_norm_reg(registration), (None, None, None))

        type_code, model, manufacturer = _resolve_type_and_model(
            registry_type=registry_type,
            variant=variant,
            fleet_type=fleet_type.get(hex_code),
            au_type=au[0],
            au_model=au[1],
            au_manufacturer=au[2],
            type_names=type_names,
        )
        if type_code and registry_type and type_code != registry_type:
            preferred_hits += 1

        dst.execute(
            """
            INSERT INTO aircraft (hex_code, registration, manufacturer, model, type_code, operator, operator_icao)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(hex_code) DO UPDATE SET
                registration=COALESCE(excluded.registration, aircraft.registration),
                manufacturer=COALESCE(excluded.manufacturer, aircraft.manufacturer),
                model=COALESCE(excluded.model, aircraft.model),
                type_code=COALESCE(excluded.type_code, aircraft.type_code),
                operator=COALESCE(excluded.operator, aircraft.operator),
                operator_icao=COALESCE(excluded.operator_icao, aircraft.operator_icao)
            """,
            (
                hex_code,
                registration,
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
    logger.info(
        "Aircraft import complete: %d records (%d types upgraded from fleet/AU/variant)",
        count,
        preferred_hits,
    )
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
