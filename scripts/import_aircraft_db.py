#!/usr/bin/env python3
"""Import aircraft database from CSV to SQLite."""

import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.database import init_db
from app.services.aircraft_db import db


async def main():
    csv_path = Path(__file__).resolve().parent.parent / "data" / "aircraft_db.csv"
    if len(sys.argv) > 1:
        csv_path = Path(sys.argv[1])

    if not csv_path.exists():
        print(f"CSV file not found: {csv_path}")
        print("Usage: python import_aircraft_db.py [path/to/aircraft_db.csv]")
        sys.exit(1)

    print("Initializing database...")
    await init_db()

    print(f"Importing from {csv_path}...")
    count = await db.import_csv(csv_path)
    print(f"Imported {count} aircraft records.")


if __name__ == "__main__":
    asyncio.run(main())
