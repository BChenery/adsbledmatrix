#!/usr/bin/env python3
"""Bulk import airline logos for the ADS-B LED Matrix.

Usage:
    python scripts/import_airline_logos.py --all
    python scripts/import_airline_logos.py --from-db
    python scripts/import_airline_logos.py --limit 100
    python scripts/import_airline_logos.py --icao AAL BAW QFA
"""

import argparse
import asyncio
import csv
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.config import settings
from app.database import init_db
from app.services.logo_manager import logo_manager


def get_airlines_from_csv(csv_path: Path) -> list[dict]:
    """Read airlines from the OpenFlights-derived CSV."""
    airlines = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            icao = row.get("icao", "").strip().upper()
            if icao:
                airlines.append({
                    "icao": icao,
                    "iata": row.get("iata", "").strip().upper(),
                    "name": row.get("name", "").strip(),
                })
    return airlines


def get_airlines_from_aircraft_db() -> list[dict]:
    """Extract unique operator_icao codes from the aircraft database."""
    csv_path = settings.data_dir / "aircraft_db.csv"
    if not csv_path.exists():
        print(f"Aircraft DB not found: {csv_path}")
        return []

    icaos = set()
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            icao = row.get("operator_icao", "").strip().upper()
            if icao:
                icaos.add(icao)

    return [{"icao": icao, "iata": "", "name": ""} for icao in sorted(icaos)]


async def download_logos(airlines: list[dict], dry_run: bool = False) -> dict:
    """Download logos for a list of airlines."""
    stats = {"total": len(airlines), "success": 0, "failed": 0, "skipped": 0}

    for i, airline in enumerate(airlines, 1):
        icao = airline["icao"]
        name = airline.get("name", "")
        prefix = f"[{i}/{len(airlines)}]"

        path = settings.logos_dir / f"{icao}.png"
        if path.exists() and not dry_run:
            print(f"{prefix} {icao} ({name}) — already exists, skipping")
            stats["skipped"] += 1
            continue

        if dry_run:
            print(f"{prefix} {icao} ({name}) — would download")
            continue

        try:
            result = await logo_manager.get_logo(icao)
            if result and result.name != "UNKNOWN.png":
                print(f"{prefix} {icao} ({name}) — downloaded ✓")
                stats["success"] += 1
            else:
                print(f"{prefix} {icao} ({name}) — not found, will use fallback")
                stats["failed"] += 1
        except Exception as e:
            print(f"{prefix} {icao} ({name}) — error: {e}")
            stats["failed"] += 1

    return stats


async def main():
    parser = argparse.ArgumentParser(description="Bulk import airline logos")
    parser.add_argument("--all", action="store_true", help="Download logos for all airlines in airlines.csv")
    parser.add_argument("--from-db", action="store_true", help="Download logos for airlines in aircraft_db.csv")
    parser.add_argument("--limit", type=int, default=0, help="Limit to top N airlines")
    parser.add_argument("--icao", nargs="+", help="Specific ICAO codes to download")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be downloaded without downloading")
    args = parser.parse_args()

    await init_db()

    if args.icao:
        airlines = [{"icao": c.upper(), "iata": "", "name": ""} for c in args.icao]
    elif args.from_db:
        airlines = get_airlines_from_aircraft_db()
    elif args.all:
        csv_path = settings.data_dir / "airlines.csv"
        airlines = get_airlines_from_csv(csv_path)
    else:
        parser.print_help()
        sys.exit(1)

    if args.limit > 0:
        airlines = airlines[:args.limit]

    print(f"Preparing to download logos for {len(airlines)} airlines...")
    print(f"Target directory: {settings.logos_dir}")
    print(f"Target size: 96×96 PNG with transparency")
    print()

    stats = await download_logos(airlines, dry_run=args.dry_run)

    print()
    print("=" * 40)
    print(f"Total:   {stats['total']}")
    print(f"Success: {stats['success']}")
    print(f"Skipped: {stats['skipped']}")
    print(f"Failed:  {stats['failed']}")

    await logo_manager.close()


if __name__ == "__main__":
    asyncio.run(main())
