import asyncio
import hashlib
import json
import logging
import shutil
import subprocess
import tarfile
from pathlib import Path
from typing import Optional
import httpx
from app.config import settings, PROJECT_ROOT
from app.services.device_id import get_device_id
from app.services.rollout import is_in_rollout

logger = logging.getLogger(__name__)


class UpdateService:
    """Checks GitHub releases for updates and applies them safely."""

    GITHUB_API = "https://api.github.com/repos/{repo}/releases/latest"
    RAW_URL = "https://raw.githubusercontent.com/{repo}/main/data/aircraft_db.csv"

    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def _fetch_text(self, url: str) -> str:
        client = await self._get_client()
        response = await client.get(url)
        response.raise_for_status()
        return response.text

    async def _fetch_bytes(self, url: str) -> bytes:
        client = await self._get_client()
        response = await client.get(url)
        response.raise_for_status()
        return response.content

    async def check_for_update(self) -> dict:
        """Return update info dict with latest version and download URL."""
        client = await self._get_client()
        url = self.GITHUB_API.format(repo=settings.github_repo)
        try:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
            latest_version = data.get("tag_name", "v0.0.0").lstrip("v")
            assets = {a["name"]: a["browser_download_url"] for a in data.get("assets", [])}
            return {
                "current_version": settings.version,
                "latest_version": latest_version,
                "update_available": latest_version != settings.version,
                "download_url": assets.get(f"adsbledmatrix-v{latest_version}.tar.gz"),
                "checksum_url": assets.get(f"adsbledmatrix-v{latest_version}.tar.gz.sha256"),
                "rollout_url": assets.get("rollout.json"),
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

    async def _is_eligible_for_device(self, release_tag: str, rollout_url: Optional[str]) -> bool:
        if not rollout_url:
            return True
        try:
            rollout_text = await self._fetch_text(rollout_url)
            rollout_data = json.loads(rollout_text)
            percentage = int(rollout_data.get("percentage", 100))
        except Exception as e:
            logger.warning(f"Could not read rollout config, defaulting to 100%: {e}")
            percentage = 100
        device_id = get_device_id()
        return is_in_rollout(device_id, release_tag, percentage)

    async def apply_update(self, update_info: dict) -> bool:
        """Download, verify, and apply an update with rollback on failure."""
        download_url = update_info.get("download_url")
        checksum_url = update_info.get("checksum_url")
        release_tag = f"v{update_info.get('latest_version', '0.0.0')}"
        if not download_url:
            logger.error("No download URL in update info")
            return False

        try:
            if not await self._is_eligible_for_device(release_tag, update_info.get("rollout_url")):
                logger.info("Device not in rollout bucket for %s", release_tag)
                return False

            # Download and verify
            archive_bytes = await self._fetch_bytes(download_url)
            if checksum_url:
                expected_checksum = (await self._fetch_text(checksum_url)).strip().split()[0]
                actual_checksum = hashlib.sha256(archive_bytes).hexdigest()
                if actual_checksum != expected_checksum:
                    logger.error("Checksum mismatch: expected %s, got %s", expected_checksum, actual_checksum)
                    return False

            # Backup current
            backup_dir = PROJECT_ROOT.parent / "adsbledmatrix-backup"
            if backup_dir.exists():
                shutil.rmtree(backup_dir)
            shutil.copytree(PROJECT_ROOT, backup_dir)

            # Extract
            tar_path = Path("/tmp/adsbledmatrix-update.tar.gz")
            tar_path.write_bytes(archive_bytes)
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
            src_dir = subdirs[0] / "adsbledmatrix"
            if not src_dir.exists():
                raise RuntimeError("Expected 'adsbledmatrix' folder in tarball")

            # Copy over existing installation
            for item in src_dir.iterdir():
                dest = PROJECT_ROOT / item.name
                if item.is_dir():
                    if dest.exists():
                        shutil.rmtree(dest)
                    shutil.copytree(item, dest)
                else:
                    shutil.copy2(item, dest)

            # Run migrations
            await self._run_migrations()

            # Restart service and health check
            if not await self._restart_and_verify():
                logger.error("Health check failed after update, rolling back")
                await self._rollback(backup_dir)
                return False

            logger.info("Update applied successfully")
            return True
        except Exception as e:
            logger.error(f"Update failed: {e}")
            return False

    async def _run_migrations(self) -> None:
        """Run Alembic migrations if available; otherwise no-op."""
        try:
            result = subprocess.run(
                [str(PROJECT_ROOT / "venv" / "bin" / "alembic"), "upgrade", "head"],
                cwd=PROJECT_ROOT / "backend",
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                logger.warning("Migration command failed: %s", result.stderr)
        except FileNotFoundError:
            logger.info("No alembic found, skipping migrations")

    async def _restart_and_verify(self) -> bool:
        """Restart the service and poll health until success or timeout."""
        subprocess.run(["systemctl", "restart", "adsbledmatrix"], check=True)
        deadline = asyncio.get_event_loop().time() + 120
        while asyncio.get_event_loop().time() < deadline:
            await asyncio.sleep(5)
            try:
                client = await self._get_client()
                response = await client.get(f"http://127.0.0.1:{settings.port}/api/health")
                if response.status_code == 200:
                    data = response.json()
                    if data.get("status") == "ok":
                        return True
            except Exception as e:
                logger.debug("Health check not ready: %s", e)
        return False

    async def _rollback(self, backup_dir: Path) -> None:
        """Restore the backup and restart."""
        if not backup_dir.exists():
            logger.error("No backup available for rollback")
            return
        for item in PROJECT_ROOT.iterdir():
            if item.name == "venv" or item.name == "data":
                continue
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()
        for item in backup_dir.iterdir():
            dest = PROJECT_ROOT / item.name
            if item.is_dir():
                shutil.copytree(item, dest)
            else:
                shutil.copy2(item, dest)
        subprocess.run(["systemctl", "restart", "adsbledmatrix"], check=True)
        logger.info("Rollback complete")

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
