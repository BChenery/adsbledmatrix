#!/usr/bin/env python3
"""Import flight routes into the ADS-B LED Matrix database.

Usage:
    python scripts/import_routes.py data/routes.csv
    python scripts/import_routes.py --from-dict
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.services.route_service import route_service
from app.database import init_db


SAMPLE_ROUTES = {
    "QFA123": ("SYD", "LAX"),
    "UAL97": ("BNE", "SFO"),
    "BAW15": ("LHR", "SIN"),
    "AAL73": ("LAX", "SYD"),
    "DLT41": ("ATL", "JNB"),
    "UAE434": ("DXB", "BNE"),
    "CPA103": ("HKG", "MEL"),
    "SIA221": ("SIN", "SYD"),
    "ANZ101": ("AKL", "SYD"),
    "JST456": ("OOL", "MEL"),
}


async def main():
    parser = argparse.ArgumentParser(description="Import flight routes")
    parser.add_argument("csv_path", nargs="?", help="Path to CSV file with columns: callsign,origin,destination")
    parser.add_argument("--from-dict", action="store_true", help="Import sample hardcoded routes for testing")
    args = parser.parse_args()

    await init_db()

    if args.from_dict:
        count = await route_service.import_from_dict(SAMPLE_ROUTES)
        print(f"Imported {count} sample routes")
    elif args.csv_path:
        path = Path(args.csv_path)
        count = await route_service.import_from_csv(path)
        print(f"Imported {count} routes from {path}")
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
