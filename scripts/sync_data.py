#!/usr/bin/env python3
"""Sync all data assets from the GitHub repo for offline operation.

Downloads the latest data files (aircraft_db, routes, airlines) and refreshes
the logo pack. After syncing, the device can operate fully offline.

Usage:
    python scripts/sync_data.py
    python scripts/sync_data.py --force
    python scripts/sync_data.py --skip-logos
"""

import argparse
import asyncio
import hashlib
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

import httpx

from app.config import settings
from app.database import init_db

# Data files to sync from repo
DATA_FILES = [
    "data/aircraft_db.csv",
    "data/airlines.csv",
    "data/routes.csv",
    "data/localadsb/flights.db",
    "data/localadsb/aircraft_type_names.json",
]

RAW_BASE = "https://raw.githubusercontent.com/{repo}/main/{path}"


def _file_hash(path: Path) -> str:
    """Return SHA256 hex digest of file contents."""
    if not path.exists():
        return ""
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


async def download_file(client: httpx.AsyncClient, repo: str, rel_path: str, dest: Path) -> bool:
    """Download a single file if it has changed. Returns True if updated."""
    url = RAW_BASE.format(repo=repo, path=rel_path)
    local_path = settings.data_dir.parent / rel_path
    local_path.parent.mkdir(parents=True, exist_ok=True)

    old_hash = _file_hash(local_path)

    try:
        resp = await client.get(url, timeout=30.0)
        if resp.status_code == 404:
            print(f"  ⚠ {rel_path} not found in repo (skipped)")
            return False
        if resp.status_code != 200:
            print(f"  ✗ {rel_path} download failed (HTTP {resp.status_code})")
            return False

        new_hash = hashlib.sha256(resp.content).hexdigest()
        if new_hash == old_hash:
            print(f"  ✓ {rel_path} unchanged")
            return False

        local_path.write_bytes(resp.content)
        print(f"  ✓ {rel_path} updated")
        return True
    except Exception as e:
        print(f"  ✗ {rel_path} error: {e}")
        return False


async def sync_data_files(client: httpx.AsyncClient, repo: str, force: bool = False) -> list[str]:
    """Download all tracked data files. Returns list of updated files."""
    updated = []
    for rel_path in DATA_FILES:
        if await download_file(client, repo, rel_path, settings.data_dir):
            updated.append(rel_path)
        elif force:
            # Force re-import even if file didn't change
            local_path = settings.data_dir.parent / rel_path
            if local_path.exists():
                updated.append(rel_path)
    return updated


async def import_aircraft_db() -> int:
    """Import aircraft database CSV into SQLite."""
    from app.services.aircraft_db import db
    csv_path = settings.data_dir / "aircraft_db.csv"
    if not csv_path.exists():
        print("  ⚠ aircraft_db.csv not found, skipping import")
        return 0
    count = await db.import_csv(csv_path)
    print(f"  ✓ Imported {count} aircraft records")
    return count


async def import_routes() -> int:
    """Import routes CSV into SQLite."""
    from app.services.route_service import route_service
    csv_path = settings.data_dir / "routes.csv"
    if not csv_path.exists():
        print("  ⚠ routes.csv not found, skipping import")
        return 0
    count = await route_service.import_from_csv(csv_path)
    print(f"  ✓ Imported {count} routes")
    return count


async def sync_logos() -> dict:
    """Run the logo pack download script."""
    script = Path(__file__).resolve().parent / "download_logo_pack.py"
    result = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        print("  ✓ Logo pack refreshed")
    else:
        print(f"  ⚠ Logo refresh warning: {result.stderr.strip() or 'unknown'}")
    return {"ok": result.returncode == 0, "output": result.stdout}


async def main():
    parser = argparse.ArgumentParser(description="Sync data assets from GitHub repo")
    parser.add_argument("--force", action="store_true", help="Re-import even if files haven't changed")
    parser.add_argument("--skip-logos", action="store_true", help="Skip logo pack refresh")
    parser.add_argument("--repo", default=settings.github_repo, help="GitHub repo slug (owner/repo)")
    args = parser.parse_args()

    print("=" * 50)
    print("ADS-B LED Display Data Sync")
    print("=" * 50)
    print(f"Repo:    {args.repo}")
    print(f"Data dir: {settings.data_dir}")
    print()

    await init_db()

    async with httpx.AsyncClient() as client:
        print("[1/5] Syncing data files...")
        updated = await sync_data_files(client, args.repo, force=args.force)

    print()
    print("[2/5] Importing aircraft database...")
    aircraft_count = await import_aircraft_db()

    print()
    print("[3/5] Importing routes...")
    routes_count = await import_routes()

    if not args.skip_logos:
        print()
        print("[4/5] Refreshing logo pack...")
        await sync_logos()
    else:
        print()
        print("[4/5] Skipping logo refresh (--skip-logos)")

    localadsb_script = Path(__file__).resolve().parent / "import_localadsb.py"
    flights_db_local = settings.data_dir / "localadsb" / "flights.db"
    flights_db_rel = "data/localadsb/flights.db"
    if localadsb_script.exists() and flights_db_local.exists() and (flights_db_rel in updated or args.force):
        print()
        print("[5/5] Importing localadsb databases...")
        result = subprocess.run(
            [sys.executable, str(localadsb_script)],
            capture_output=True,
            text=True,
        )
        print(result.stdout)
        if result.returncode != 0:
            print(f"  ⚠ localadsb import warning: {result.stderr.strip() or 'unknown'}")

    # Write sync timestamp
    sync_file = settings.data_dir / ".last_sync"
    sync_file.write_text(datetime.now(timezone.utc).isoformat())

    print()
    print("=" * 50)
    print("Sync complete!")
    print(f"  Files updated: {len(updated)}")
    print(f"  Aircraft: {aircraft_count}")
    print(f"  Routes: {routes_count}")
    print(f"  Timestamp: {sync_file.read_text().strip()}")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
