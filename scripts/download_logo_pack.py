#!/usr/bin/env python3
"""Download the full airline logo pack from Jxck-S/airline-logos for offline use.

Uses raw GitHub CDN URLs — no API calls, no rate limits.

Usage:
    python scripts/download_logo_pack.py
    python scripts/download_logo_pack.py --limit 200
    python scripts/download_logo_pack.py --workers 50
    python scripts/download_logo_pack.py --from-db
"""

import argparse
import asyncio
import csv
import sys
from io import BytesIO
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

import httpx
from PIL import Image

from app.config import settings

LOGO_SIZE = (96, 96)
SOURCE_OWNER = "Jxck-S"
SOURCE_REPO = "airline-logos"
SOURCE_BRANCH = "main"


async def download_logo(
    client: httpx.AsyncClient,
    icao: str,
    dest_dir: Path,
    sem: asyncio.Semaphore,
) -> tuple[str, bool]:
    """Download a single logo from Jxck-S sources, resize, and save."""
    dest = dest_dir / f"{icao}.png"

    # Skip if already exists and looks valid
    if dest.exists() and dest.stat().st_size > 500:
        return icao, False  # skipped

    sources = [
        f"https://raw.githubusercontent.com/{SOURCE_OWNER}/{SOURCE_REPO}/{SOURCE_BRANCH}/flightaware_logos/{icao}.png",
        f"https://raw.githubusercontent.com/{SOURCE_OWNER}/{SOURCE_REPO}/{SOURCE_BRANCH}/radarbox_logos/{icao}.png",
    ]

    async with sem:
        for url in sources:
            try:
                resp = await client.get(url, timeout=15.0)
                if resp.status_code == 200 and len(resp.content) > 200:
                    # Resize and standardize
                    img = Image.open(BytesIO(resp.content))
                    img = img.convert("RGBA")
                    img = img.resize(LOGO_SIZE, Image.LANCZOS)
                    buf = BytesIO()
                    img.save(buf, format="PNG", optimize=True)
                    dest.write_bytes(buf.getvalue())
                    return icao, True
            except Exception:
                continue
        return icao, False


def get_icao_list_from_csv(csv_path: Path) -> list[str]:
    """Read ICAO codes from airlines.csv."""
    icaos = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            icao = row.get("icao", "").strip().upper()
            if icao:
                icaos.append(icao)
    return icaos


def get_icao_list_from_aircraft_db() -> list[str]:
    """Extract unique operator_icao codes from aircraft_db.csv."""
    csv_path = settings.data_dir / "aircraft_db.csv"
    if not csv_path.exists():
        return []
    icaos = set()
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            icao = row.get("operator_icao", "").strip().upper()
            if icao:
                icaos.add(icao)
    return sorted(icaos)


async def main():
    parser = argparse.ArgumentParser(description="Download airline logo pack for offline use")
    parser.add_argument("--limit", type=int, default=0, help="Limit total logos downloaded")
    parser.add_argument("--workers", type=int, default=30, help="Concurrent download workers")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be downloaded")
    parser.add_argument("--from-db", action="store_true", help="Use aircraft_db.csv instead of airlines.csv")
    args = parser.parse_args()

    dest_dir = settings.logos_dir
    dest_dir.mkdir(parents=True, exist_ok=True)

    if args.from_db:
        icaos = get_icao_list_from_aircraft_db()
        source = "aircraft_db.csv"
    else:
        csv_path = settings.data_dir / "airlines.csv"
        icaos = get_icao_list_from_csv(csv_path)
        source = "airlines.csv"

    if args.limit > 0:
        icaos = icaos[:args.limit]

    print(f"Source: {source} ({len(icaos)} ICAO codes)")
    print(f"Target: {dest_dir}")
    print(f"Workers: {args.workers}")

    if args.dry_run:
        for icao in icaos[:20]:
            print(f"  Would attempt {icao}")
        if len(icaos) > 20:
            print(f"  ... and {len(icaos) - 20} more")
        return

    # Download with concurrency limit
    sem = asyncio.Semaphore(args.workers)
    async with httpx.AsyncClient() as client:
        tasks = [download_logo(client, icao, dest_dir, sem) for icao in icaos]

        done = 0
        success = 0
        skipped = 0
        failed = 0
        for coro in asyncio.as_completed(tasks):
            icao, ok = await coro
            done += 1
            if ok:
                success += 1
            elif (dest_dir / f"{icao}.png").exists():
                skipped += 1
            else:
                failed += 1
            if done % 100 == 0 or done == len(tasks):
                print(f"  Progress: {done}/{len(tasks)} (downloaded: {success}, skipped: {skipped}, missing: {failed})")

    print(f"\nDone! Downloaded {success} new logos. Skipped {skipped} (already present). Missing {failed}.")
    print(f"Total logos in {dest_dir}: {len(list(dest_dir.glob('*.png')))}")


if __name__ == "__main__":
    asyncio.run(main())
