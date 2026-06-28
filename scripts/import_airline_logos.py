#!/usr/bin/env python3
"""Bulk import airline logos from https://github.com/Jxck-S/airline-logos."""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.services.logo_manager import logo_manager


async def main():
    parser = argparse.ArgumentParser(description="Bulk import airline logos")
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace existing logos so FlightAware is preferred over Radarbox",
    )
    args = parser.parse_args()

    result = await logo_manager.bulk_import_from_github(overwrite=args.overwrite)
    print(
        f"Import complete: {result['downloaded']} downloaded, "
        f"{result['skipped']} skipped, {result['failed']} failed"
    )
    await logo_manager.close()


if __name__ == "__main__":
    asyncio.run(main())
