import json
import logging
import tarfile
from pathlib import Path
from typing import Optional
import httpx
from app.config import settings, PROJECT_ROOT

logger = logging.getLogger(__name__)


class UpdateService:
    """Checks GitHub releases for updates and applies them."""

    GITHUB_API = "https://api.github.com/repos/{repo}/releases/latest"
    RAW_URL = "https://raw.githubusercontent.com/{repo}/main/data/aircraft_db.csv"

    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def check_for_update(self) -> dict:
        """Return update info dict with latest version and download URL."""
        client = await self._get_client()
        url = self.GITHUB_API.format(repo=settings.github_repo)
        try:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
            latest_version = data.get("tag_name", "v0.0.0").lstrip("v")
            return {
                "current_version": settings.version,
                "latest_version": latest_version,
                "update_available": latest_version != settings.version,
                "download_url": data.get("tarball_url"),
                "release_notes": data.get("body", ""),
                "published_at": data.get("published_at"),
            }
        except Exception as e:
            logger.error(f"Update check failed: {e}")
            return {
                "current_version": settings.version,
                "latest_version": settings.version,
                "update_available": False,
                "error": str(e),
            }

    async def apply_update(self, download_url: str) -> bool:
        """Download and apply update tarball."""
        client = await self._get_client()
        try:
            # Backup current
            backup_dir = PROJECT_ROOT.parent / "adsbledmatrix-backup"
            if backup_dir.exists():
                import shutil
                shutil.rmtree(backup_dir)
            import shutil
            shutil.copytree(PROJECT_ROOT, backup_dir)

            # Download
            response = await client.get(download_url)
            response.raise_for_status()
            tar_path = Path("/tmp/adsbledmatrix-update.tar.gz")
            tar_path.write_bytes(response.content)

            # Extract
            extract_dir = Path("/tmp/adsbledmatrix-update")
            if extract_dir.exists():
                shutil.rmtree(extract_dir)
            extract_dir.mkdir()
            with tarfile.open(tar_path, "r:gz") as tar:
                tar.extractall(extract_dir)

            # Find extracted folder (GitHub tarball has repo-commit folder)
            subdirs = [d for d in extract_dir.iterdir() if d.is_dir()]
            if not subdirs:
                raise RuntimeError("No directory found in tarball")
            src_dir = subdirs[0]

            # Copy over existing installation
            for item in src_dir.iterdir():
                dest = PROJECT_ROOT / item.name
                if item.is_dir():
                    if dest.exists():
                        shutil.rmtree(dest)
                    shutil.copytree(item, dest)
                else:
                    shutil.copy2(item, dest)

            # Update database if CSV changed
            await self.update_database()

            logger.info("Update applied successfully")
            return True
        except Exception as e:
            logger.error(f"Update failed: {e}")
            return False

    async def update_database(self) -> bool:
        """Download latest aircraft database CSV from GitHub."""
        client = await self._get_client()
        url = self.RAW_URL.format(repo=settings.github_repo)
        try:
            response = await client.get(url)
            if response.status_code == 200:
                csv_path = settings.data_dir / "aircraft_db.csv"
                csv_path.write_bytes(response.content)
                from app.services.aircraft_db import db
                await db.import_csv(csv_path)
                logger.info("Aircraft database updated")
                return True
        except Exception as e:
            logger.error(f"Database update failed: {e}")
        return False

    async def sync_data(self) -> dict:
        """Trigger a data sync (aircraft DB, routes, logos) via sync_data.py."""
        import subprocess
        script = PROJECT_ROOT / "scripts" / "sync_data.py"
        result = subprocess.run(
            [str(PROJECT_ROOT / "venv" / "bin" / "python"), str(script)],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None


updater = UpdateService()
