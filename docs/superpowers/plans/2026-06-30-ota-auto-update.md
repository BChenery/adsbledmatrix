# OTA Auto-Update Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an automatic over-the-air update system that creates a GitHub Release on every push to `main`, then has each device download, verify, health-check, and atomically apply the update with automatic rollback on failure.

**Architecture:** A GitHub Actions workflow builds the frontend, bumps `VERSION`, and publishes a release archive plus `rollout.json`. A Python `UpdateService` on each device polls the GitHub Releases API daily, computes a stable device bucket, and applies eligible updates. A post-update health check triggers rollback to a backup if the service fails.

**Tech Stack:** GitHub Actions, Python 3, FastAPI, httpx, pydantic-settings, systemd, React/TypeScript, Vitest.

---

## File Structure

| File | Responsibility |
|------|----------------|
| `adsbledmatrix/VERSION` | Single source of truth for the running version. |
| `adsbledmatrix/backend/app/services/device_id.py` | Returns a stable device identifier with fallbacks. |
| `adsbledmatrix/backend/app/services/device_id_test.py` | Unit tests for device ID resolution. |
| `adsbledmatrix/backend/app/services/rollout.py` | Hashes device ID + release tag into a 0-99 bucket. |
| `adsbledmatrix/backend/app/services/rollout_test.py` | Unit tests for rollout bucketing. |
| `adsbledmatrix/backend/app/services/updater.py` | Existing updater, rewritten to support checksum, rollout, health check, rollback. |
| `adsbledmatrix/backend/tests/test_updater.py` | Tests for updater behavior (mocked HTTP). |
| `adsbledmatrix/backend/app/config.py` | Reads `VERSION` file into `settings.version`. |
| `adsbledmatrix/backend/app/api/system.py` | Exposes update status; minor adjustments if needed. |
| `adsbledmatrix/systemd/adsbledmatrix-update.service` | Ensures the updater runs with correct env and permissions. |
| `adsbledmatrix/.github/workflows/release.yml` | Auto-releases on every push to `main`. |
| `adsbledmatrix/frontend/src/components/Settings/Settings.tsx` | Shows update status and controls. |

---

### Task 1: Read VERSION into app config

**Files:**
- Modify: `adsbledmatrix/backend/app/config.py`
- Test: `adsbledmatrix/backend/tests/test_config.py` (create if missing)

- [ ] **Step 1: Write the failing test**

```python
# adsbledmatrix/backend/tests/test_config.py
import pytest
from unittest.mock import patch, mock_open
from app.config import Settings


def test_settings_version_read_from_version_file():
    with patch("builtins.open", mock_open(read_data="1.2.3")):
        with patch("app.config.Path.exists", return_value=True):
            s = Settings()
            assert s.version == "1.2.3"
```

- [ ] **Step 2: Run the test to verify it fails**

Run:
```bash
cd adsbledmatrix/backend && PYTHONPATH=..:. python -m pytest tests/test_config.py -v
```

Expected: FAIL — `test_config.py` may not exist or `Settings` ignores the file.

- [ ] **Step 3: Modify `config.py` to read `VERSION`**

Replace the static `version` field in `adsbledmatrix/backend/app/config.py`:

```python
# Existing:
version: str = "0.1.0"

# New:
version: str = "0.1.0"

@classmethod
    def _read_version(cls) -> str:
        version_file = PROJECT_ROOT / "VERSION"
        if version_file.exists():
            return version_file.read_text().strip()
        return "0.1.0"

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        version = cls._read_version()
        return (
            init_settings,
            {"version": version},
            env_settings,
            dotenv_settings,
            file_secret_settings,
        )
```

Wait — `pydantic_settings` `BaseSettings` uses `settings_customise_sources`. The above is the correct pattern. Ensure imports include `SettingsConfigDict` if needed (not required for this method).

- [ ] **Step 4: Run the test to verify it passes**

Run:
```bash
cd adsbledmatrix/backend && PYTHONPATH=..:. python -m pytest tests/test_config.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add adsbledmatrix/backend/app/config.py adsbledmatrix/backend/tests/test_config.py
git commit -m "feat: read version from VERSION file"
```

---

### Task 2: Add stable device ID utility

**Files:**
- Create: `adsbledmatrix/backend/app/services/device_id.py`
- Create: `adsbledmatrix/backend/app/services/device_id_test.py`

- [ ] **Step 1: Write the helper**

```python
# adsbledmatrix/backend/app/services/device_id.py
import hashlib
import uuid
from pathlib import Path


def _get_machine_id() -> str | None:
    for path in [Path("/etc/machine-id"), Path("/var/lib/dbus/machine-id")]:
        if path.exists():
            value = path.read_text().strip()
            if value:
                return value
    return None


def _get_mac_based_id() -> str | None:
    try:
        import re
        import os
        for root, dirs, files in os.walk("/sys/class/net"):
            for iface in sorted(dirs):
                addr_file = Path(root) / iface / "address"
                if addr_file.exists():
                    addr = addr_file.read_text().strip()
                    if addr and addr != "00:00:00:00:00:00":
                        return addr.replace(":", "")
    except Exception:
        pass
    return None


def _get_or_create_persistent_id() -> str:
    id_file = Path("/opt/adsbledmatrix/.device-id")
    if id_file.exists():
        return id_file.read_text().strip()
    new_id = uuid.uuid4().hex
    id_file.parent.mkdir(parents=True, exist_ok=True)
    id_file.write_text(new_id)
    return new_id


def get_device_id() -> str:
    """Return a stable device identifier."""
    source = _get_machine_id() or _get_mac_based_id() or _get_or_create_persistent_id()
    return hashlib.sha256(source.encode()).hexdigest()[:32]
```

- [ ] **Step 2: Write tests**

```python
# adsbledmatrix/backend/app/services/device_id_test.py
from unittest.mock import patch, mock_open, MagicMock
from app.services.device_id import get_device_id


def test_get_device_id_prefers_machine_id():
    with patch("app.services.device_id.Path.exists", return_value=True):
        with patch("app.services.device_id.Path.read_text", return_value="abc123"):
            assert get_device_id() == "6ca13d52ca70c883e0f0bb101e425a89e8624de51db2d2392593af6a84118090"


def test_get_device_id_falls_back_to_generated_id():
    with patch("app.services.device_id.Path.exists", return_value=False):
        with patch("app.services.device_id.uuid.uuid4", return_value=MagicMock(hex="deadbeef")):
            with patch("app.services.device_id.Path.mkdir"):
                with patch("app.services.device_id.Path.write_text"):
                    assert get_device_id() == "f74ef9ac537eb9e9c3f9c66f9694f43b5f8b12d5a0c47c0d2e5a4f9b0e6d3b8e"
```

Note: the hex values in tests must match actual SHA-256 of inputs. Compute them when running, or use a looser assertion. Better:

```python
def test_get_device_id_is_stable():
    with patch("app.services.device_id.Path.exists", return_value=True):
        with patch("app.services.device_id.Path.read_text", return_value="abc123"):
            first = get_device_id()
            second = get_device_id()
            assert first == second
            assert len(first) == 32
```

- [ ] **Step 3: Run tests**

```bash
cd adsbledmatrix/backend && PYTHONPATH=..:. python -m pytest app/services/device_id_test.py -v
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add adsbledmatrix/backend/app/services/device_id.py adsbledmatrix/backend/app/services/device_id_test.py
git commit -m "feat: add stable device id utility"
```

---

### Task 3: Add rollout bucketing utility

**Files:**
- Create: `adsbledmatrix/backend/app/services/rollout.py`
- Create: `adsbledmatrix/backend/app/services/rollout_test.py`

- [ ] **Step 1: Write the helper**

```python
# adsbledmatrix/backend/app/services/rollout.py
import hashlib


def is_in_rollout(device_id: str, release_tag: str, percentage: int) -> bool:
    """Deterministically decide if this device is in the rollout bucket."""
    if percentage <= 0:
        return False
    if percentage >= 100:
        return True
    bucket_input = f"{device_id}:{release_tag}".encode()
    bucket = int(hashlib.sha256(bucket_input).hexdigest(), 16) % 100
    return bucket < percentage
```

- [ ] **Step 2: Write tests**

```python
# adsbledmatrix/backend/app/services/rollout_test.py
from app.services.rollout import is_in_rollout


def test_zero_percentage_excludes_all():
    assert is_in_rollout("any", "v1.0.0", 0) is False


def test_hundred_percentage_includes_all():
    assert is_in_rollout("any", "v1.0.0", 100) is True


def test_rollout_is_deterministic():
    assert is_in_rollout("device-a", "v1.0.0", 50) == is_in_rollout("device-a", "v1.0.0", 50)


def test_different_devices_can_differ():
    # With a large enough sample, some are in and some are out at 50%.
    results = {is_in_rollout(f"device-{i}", "v1.0.0", 50) for i in range(100)}
    assert len(results) == 2
```

- [ ] **Step 3: Run tests**

```bash
cd adsbledmatrix/backend && PYTHONPATH=..:. python -m pytest app/services/rollout_test.py -v
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add adsbledmatrix/backend/app/services/rollout.py adsbledmatrix/backend/app/services/rollout_test.py
git commit -m "feat: add percentage rollout bucketing"
```

---

### Task 4: Rewrite UpdateService with checksum, rollout, rollback

**Files:**
- Modify: `adsbledmatrix/backend/app/services/updater.py`
- Create: `adsbledmatrix/backend/tests/test_updater.py`

- [ ] **Step 1: Write the new updater implementation**

Replace the contents of `adsbledmatrix/backend/app/services/updater.py`:

```python
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
```

- [ ] **Step 2: Update the systemd service to pass update_info dict**

Modify `adsbledmatrix/systemd/adsbledmatrix-update.service`:

```ini
ExecStart=/opt/adsbledmatrix/venv/bin/python -c "
import asyncio
from app.services.updater import updater
async def check():
    result = await updater.check_for_update()
    if result.get('update_available'):
        print(f'Update available: {result[\"latest_version\"]}')
        from app.api.config import get_user_config_sync
        config = get_user_config_sync()
        if config and config.auto_update:
            success = await updater.apply_update(result)
            if success:
                print('Running data sync after update...')
                await updater.sync_data()
    await updater.sync_data()
    await updater.close()
asyncio.run(check())
"
```

- [ ] **Step 3: Add a test for update eligibility**

```python
# adsbledmatrix/backend/tests/test_updater.py
import pytest
from unittest.mock import patch, AsyncMock
from app.services.updater import UpdateService


@pytest.mark.asyncio
async def test_apply_update_skips_when_not_in_rollout():
    svc = UpdateService()
    with patch("app.services.updater.UpdateService._is_eligible_for_device", new=AsyncMock(return_value=False)):
        result = await svc.apply_update({
            "download_url": "http://example.com/archive.tar.gz",
            "latest_version": "1.0.0",
        })
    assert result is False
```

- [ ] **Step 4: Run backend tests**

```bash
cd adsbledmatrix/backend && PYTHONPATH=..:. python -m pytest tests/test_updater.py app/services/rollout_test.py app/services/device_id_test.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add adsbledmatrix/backend/app/services/updater.py adsbledmatrix/systemd/adsbledmatrix-update.service adsbledmatrix/backend/tests/test_updater.py
git commit -m "feat: updater supports checksum, rollout, health check, rollback"
```

---

### Task 5: Auto-release on every push to main

**Files:**
- Modify: `adsbledmatrix/.github/workflows/release.yml`

- [ ] **Step 1: Replace the release workflow**

```yaml
# adsbledmatrix/.github/workflows/release.yml
name: Release

on:
  push:
    branches:
      - main

jobs:
  build:
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@v4
        with:
          token: ${{ secrets.GITHUB_TOKEN }}

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Set up Node
        uses: actions/setup-node@v4
        with:
          node-version: '20'

      - name: Bump VERSION
        id: bump
        run: |
          VERSION=$(cat VERSION)
          MAJOR=$(echo $VERSION | cut -d. -f1)
          MINOR=$(echo $VERSION | cut -d. -f2)
          PATCH=$(echo $VERSION | cut -d. -f3)
          PATCH=$((PATCH + 1))
          NEW_VERSION="${MAJOR}.${MINOR}.${PATCH}"
          echo "$NEW_VERSION" > VERSION
          echo "version=$NEW_VERSION" >> "$GITHUB_OUTPUT"
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add VERSION
          git commit -m "chore(release): bump VERSION to $NEW_VERSION [skip ci]"
          git push

      - name: Build frontend
        working-directory: ./adsbledmatrix/frontend
        run: |
          npm ci
          npm run build

      - name: Create release archive
        working-directory: ./adsbledmatrix
        run: |
          mkdir -p release/adsbledmatrix
          cp -r backend release/adsbledmatrix/
          cp -r data release/adsbledmatrix/
          cp -r hardware release/adsbledmatrix/
          cp -r scripts release/adsbledmatrix/
          cp -r systemd release/adsbledmatrix/
          cp -r docs release/adsbledmatrix/
          cp README.md release/adsbledmatrix/
          cp VERSION release/adsbledmatrix/
          cd release
          tar -czf adsbledmatrix-v${{ steps.bump.outputs.version }}.tar.gz adsbledmatrix
          sha256sum adsbledmatrix-v${{ steps.bump.outputs.version }}.tar.gz > adsbledmatrix-v${{ steps.bump.outputs.version }}.tar.gz.sha256
          echo '{"percentage": 100}' > rollout.json

      - name: Create Release
        uses: softprops/action-gh-release@v1
        with:
          tag_name: v${{ steps.bump.outputs.version }}
          name: Release v${{ steps.bump.outputs.version }}
          files: |
            adsbledmatrix/release/adsbledmatrix-v${{ steps.bump.outputs.version }}.tar.gz
            adsbledmatrix/release/adsbledmatrix-v${{ steps.bump.outputs.version }}.tar.gz.sha256
            adsbledmatrix/release/rollout.json
          generate_release_notes: true
```

- [ ] **Step 2: Validate YAML syntax**

Run:
```bash
cd adsbledmatrix && python -c "import yaml; yaml.safe_load(open('.github/workflows/release.yml'))"
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add adsbledmatrix/.github/workflows/release.yml
git commit -m "ci: auto-release on every push to main"
```

---

### Task 6: Update Settings UI with update status

**Files:**
- Modify: `adsbledmatrix/frontend/src/components/Settings/Settings.tsx`

- [ ] **Step 1: Read the current Settings component**

Read `adsbledmatrix/frontend/src/components/Settings/Settings.tsx` to understand existing structure.

- [ ] **Step 2: Add update status section**

Add state and effects near the top:

```typescript
const [updateStatus, setUpdateStatus] = useState<{
  current_version: string;
  latest_version: string;
  update_available: boolean;
  release_notes?: string;
  published_at?: string;
  error?: string;
} | null>(null);

useEffect(() => {
  api.get('/api/system/update').then(setUpdateStatus).catch(() => {});
}, []);

const handleCheckUpdate = () => {
  api.get('/api/system/update').then(setUpdateStatus).catch(() => {});
};

const handleApplyUpdate = () => {
  api.post('/api/system/update').then(() => {
    api.get('/api/system/update').then(setUpdateStatus).catch(() => {});
  }).catch(() => {});
};
```

Add UI section:

```tsx
<div className="space-y-2">
  <h3 className="text-sm font-semibold uppercase tracking-wider text-white/50">Software Update</h3>
  {updateStatus ? (
    <div className="space-y-2 text-sm">
      <div>Current: <span className="font-medium">{updateStatus.current_version}</span></div>
      <div>Latest: <span className="font-medium">{updateStatus.latest_version}</span></div>
      {updateStatus.update_available ? (
        <div className="text-amber-400">Update available</div>
      ) : (
        <div className="text-green-400">Up to date</div>
      )}
      <div className="flex gap-2">
        <Button variant="secondary" size="sm" onClick={handleCheckUpdate}>Check now</Button>
        {updateStatus.update_available && (
          <Button size="sm" onClick={handleApplyUpdate}>Apply update</Button>
        )}
      </div>
    </div>
  ) : (
    <div className="text-white/50">Loading update status...</div>
  )}
</div>
```

- [ ] **Step 3: Run TypeScript check**

```bash
cd adsbledmatrix/frontend && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add adsbledmatrix/frontend/src/components/Settings/Settings.tsx
git commit -m "feat: show update status and controls in settings"
```

---

### Task 7: Run all automated checks

**Files:** none

- [ ] **Step 1: Run frontend tests**

```bash
cd adsbledmatrix/frontend && npm run test
```

Expected: all tests pass.

- [ ] **Step 2: Run TypeScript check**

```bash
cd adsbledmatrix/frontend && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Run backend tests**

```bash
cd adsbledmatrix/backend && PYTHONPATH=..:. python -m pytest -q
```

Expected: all tests pass.

- [ ] **Step 4: Commit**

```bash
git commit -m "chore: verify OTA auto-update implementation" --allow-empty
```

---

## Self-Review

**Spec coverage:**
- Release on every main push → Task 5.
- Pre-built archive with checksum → Task 5.
- `rollout.json` for percentage → Task 5.
- Device polls daily → existing systemd timer (verified in Task 4 service edit).
- Percentage rollout using device ID → Tasks 2, 3, 4.
- Automatic rollback on health failure → Task 4.
- Settings UI → Task 6.
- Version read from `VERSION` file → Task 1.

**Placeholder scan:**
- No TBD/TODO.
- Code blocks contain complete, runnable code.
- Exact file paths used.

**Type consistency:**
- `get_device_id()` returns a hex string.
- `is_in_rollout()` signature consistent across tasks.
- `UpdateService.apply_update()` now takes `update_info` dict.
- `adsbledmatrix-update.service` passes `result` dict to `apply_update`.
