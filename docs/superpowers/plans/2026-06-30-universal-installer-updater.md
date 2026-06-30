# Universal Installer & Auto-Updater Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the one-liner install/update path production-ready: preserve customer data, set correct ownership, run auto-updates as root, and support fresh Pi installs.

**Architecture:** A single `scripts/install_latest.sh` detects fresh vs. update mode, handles venv/dependencies, preserves SQLite databases, sets ownership, and rolls back on health-check failure. A new `scripts/check_and_update.sh` plus root systemd timer/service replaces the in-app auto-updater. The app's updater service is reduced to status reporting only.

**Tech Stack:** Bash, systemd, Python/FastAPI, SQLite, GitHub Releases, rpi-rgb-led-matrix.

---

## File Map

| File | Responsibility |
|------|----------------|
| `scripts/install_latest.sh` | Universal installer/updater: fresh install, update, dependency install, ownership, health check, rollback. |
| `scripts/check_and_update.sh` | Daily update checker invoked by systemd; compares versions and calls `install_latest.sh`. |
| `systemd/adsbledmatrix-update.service` | Root-privileged one-shot service that runs `check_and_update.sh`. |
| `systemd/adsbledmatrix-update.timer` | Fires the update service daily. |
| `backend/app/services/updater.py` | Reduced to update status checking; removes file/system operations. |
| `backend/app/api/system.py` | Removes/deprecates the apply-update endpoint; keeps status endpoint. |
| `.github/workflows/release.yml` | Verifies the release tarball contains everything the installer expects. |

---

## Task 1: Rewrite `scripts/install_latest.sh` as universal installer

**Files:**
- Modify: `scripts/install_latest.sh`
- Test: manual on Pi + `bash -n scripts/install_latest.sh`

### Step 1.1: Add preamble and helpers

Replace the top of the file with:

```bash
#!/bin/bash
set -euo pipefail

INSTALL_DIR="/opt/adsbledmatrix"
REPO="BChenery/adsbledmatrix"
API_URL="https://api.github.com/repos/${REPO}/releases/latest"
SERVICE_USER="adsb"
LOG_FILE="/var/log/adsbledmatrix-update.log"
HEALTH_URL="http://127.0.0.1:8080/api/health"

log() {
    echo "[$(date -Iseconds)] $*" | tee -a "$LOG_FILE"
}

if [ "$(id -u)" -ne 0 ]; then
    log "This script must be run as root"
    exit 1
fi

mkdir -p "$(dirname "$LOG_FILE")"
touch "$LOG_FILE"
```

### Step 1.2: Detect fresh install vs update

After the preamble, add:

```bash
if [ -d "${INSTALL_DIR}/venv" ]; then
    MODE="update"
    log "Detected existing install; running in update mode"
else
    MODE="fresh"
    log "No existing venv found; running in fresh-install mode"
fi
```

### Step 1.3: Fetch and verify latest release

Keep the existing release fetch/verify logic, but wrap it in a function and use the variables defined above:

```bash
fetch_release() {
    cd /tmp
    LATEST=$(curl -s "$API_URL" | python3 -c "import sys,json; print(json.load(sys.stdin)['tag_name'])")
    log "Latest release: $LATEST"

    ARCHIVE="adsbledmatrix-${LATEST}.tar.gz"
    CHECKSUM="${ARCHIVE}.sha256"
    BASE_URL="https://github.com/${REPO}/releases/download/${LATEST}"

    curl -L -o "$ARCHIVE" "$BASE_URL/$ARCHIVE"
    curl -L -o "$CHECKSUM" "$BASE_URL/$CHECKSUM"
    sha256sum -c "$CHECKSUM"

    rm -rf /tmp/adsbledmatrix
    tar -xzf "$ARCHIVE" -C /tmp
}

fetch_release
```

### Step 1.4: Add fresh-install setup

Add a function for fresh-install OS setup:

```bash
ensure_service_user() {
    if ! id -u "$SERVICE_USER" >/dev/null 2>&1; then
        log "Creating ${SERVICE_USER} user"
        useradd -r -s /usr/sbin/nologin "$SERVICE_USER" || useradd -r -s /bin/false "$SERVICE_USER"
    fi
}

install_os_deps() {
    log "Installing OS dependencies"
    export DEBIAN_FRONTEND=noninteractive
    apt-get update
    apt-get install -y \
        python3 \
        python3-venv \
        python3-dev \
        python3-pip \
        libssl-dev \
        libffi-dev \
        build-essential \
        git \
        curl
}

build_rgb_matrix() {
    local python_bin="$1"
    log "Building rpi-rgb-led-matrix Python bindings"
    local rgb_dir="/tmp/rpi-rgb-led-matrix"
    if [ ! -d "$rgb_dir" ]; then
        git clone --depth 1 https://github.com/hzeller/rpi-rgb-led-matrix.git "$rgb_dir"
    fi
    cd "$rgb_dir/bindings/python"
    make build-python PYTHON="$python_bin"
    make install-python PYTHON="$python_bin"
}
```

### Step 1.5: Add venv and dependency management

Add:

```bash
ensure_venv_and_requirements() {
    if [ ! -d "${INSTALL_DIR}/venv" ]; then
        log "Creating Python venv"
        python3 -m venv "${INSTALL_DIR}/venv"
    fi
    log "Installing/updating Python requirements"
    "${INSTALL_DIR}/venv/bin/pip" install --upgrade pip
    "${INSTALL_DIR}/venv/bin/pip" install -r "${INSTALL_DIR}/backend/requirements.txt"
}

ensure_rgbmatrix() {
    if "${INSTALL_DIR}/venv/bin/python3" -c "import rgbmatrix" 2>/dev/null; then
        log "rgbmatrix already installed"
        return 0
    fi
    build_rgb_matrix "${INSTALL_DIR}/venv/bin/python3"
}
```

### Step 1.6: Add install/update directory logic

Replace the old rsync block with:

```bash
install_or_update_code() {
    if [ "$MODE" = "fresh" ]; then
        log "Copying release to ${INSTALL_DIR}"
        mkdir -p "$INSTALL_DIR"
        rm -rf "${INSTALL_DIR:?}/"*
        cp -a /tmp/adsbledmatrix/. "$INSTALL_DIR/"
    else
        BACKUP_DIR="${INSTALL_DIR}-backup-$(date +%Y%m%d%H%M%S)"
        log "Backing up current install to $BACKUP_DIR"
        cp -a "$INSTALL_DIR" "$BACKUP_DIR"

        log "Updating files in $INSTALL_DIR (preserving venv, .env, and SQLite DBs)"
        rsync -a --delete \
            --exclude='venv' \
            --exclude='.env' \
            --exclude='*.db' \
            --exclude='*.sqlite' \
            --exclude='*.sqlite3' \
            /tmp/adsbledmatrix/ "$INSTALL_DIR/"
    fi
}
```

### Step 1.7: Add systemd service installation

Add:

```bash
install_systemd_units() {
    log "Installing systemd units"
    cp "${INSTALL_DIR}/systemd/"*.service /etc/systemd/system/ 2>/dev/null || true
    cp "${INSTALL_DIR}/systemd/"*.timer /etc/systemd/system/ 2>/dev/null || true
    systemctl daemon-reload
    systemctl enable adsbledmatrix.service || true
    systemctl enable adsbledmatrix-update.timer || true
    systemctl enable adsbledmatrix-update.service || true
    systemctl enable readsb.service 2>/dev/null || true
}
```

### Step 1.8: Add ownership fix

Add:

```bash
fix_ownership() {
    log "Setting ownership"
    chown -R "${SERVICE_USER}:${SERVICE_USER}" "${INSTALL_DIR}/venv"
    chown -R "${SERVICE_USER}:${SERVICE_USER}" "${INSTALL_DIR}/data"
    chown -R root:root "${INSTALL_DIR}/backend" "${INSTALL_DIR}/hardware" "${INSTALL_DIR}/scripts" "${INSTALL_DIR}/systemd" "${INSTALL_DIR}/docs" 2>/dev/null || true
    chown root:root "${INSTALL_DIR}/README.md" "${INSTALL_DIR}/VERSION" 2>/dev/null || true
}
```

### Step 1.9: Add health check and rollback

Add:

```bash
wait_for_health() {
    local timeout_secs=120
    local interval=5
    local elapsed=0
    while [ "$elapsed" -lt "$timeout_secs" ]; do
        if curl -s --max-time 3 "$HEALTH_URL" | grep -q '"status":"ok"'; then
            log "Health check passed"
            return 0
        fi
        sleep "$interval"
        elapsed=$((elapsed + interval))
    done
    log "Health check failed after ${timeout_secs}s"
    return 1
}

rollback() {
    if [ -z "${BACKUP_DIR:-}" ] || [ ! -d "$BACKUP_DIR" ]; then
        log "No backup available for rollback"
        return 1
    fi
    log "Rolling back from $BACKUP_DIR"
    systemctl stop adsbledmatrix.service || true
    rm -rf "${INSTALL_DIR:?}/"*
    cp -a "${BACKUP_DIR}/." "$INSTALL_DIR/"
    fix_ownership
    systemctl start adsbledmatrix.service || true
    if wait_for_health; then
        log "Rollback succeeded"
        return 0
    else
        log "Rollback failed"
        return 1
    fi
}
```

### Step 1.10: Add main orchestration

At the bottom of the file, replace the old main flow with:

```bash
main() {
    fetch_release

    if [ "$MODE" = "fresh" ]; then
        ensure_service_user
        install_os_deps
        install_or_update_code
        ensure_venv_and_requirements
        ensure_rgbmatrix
        install_systemd_units
    else
        install_or_update_code
        ensure_venv_and_requirements
        ensure_rgbmatrix
        install_systemd_units
    fi

    fix_ownership

    log "Starting services"
    systemctl start adsbledmatrix.service || true
    systemctl start readsb.service 2>/dev/null || true

    if wait_for_health; then
        log "Install/update completed successfully"
        if [ "$MODE" = "update" ]; then
            prune_backups
        fi
    else
        log "Install/update failed health check"
        if [ "$MODE" = "update" ]; then
            rollback
        fi
        exit 1
    fi
}

prune_backups() {
    log "Pruning old backups (keeping last 2)"
    ls -1dt "${INSTALL_DIR}-backup-"* 2>/dev/null | tail -n +3 | xargs -r rm -rf
}

main "$@"
```

### Step 1.11: Syntax check

Run:

```bash
bash -n scripts/install_latest.sh
```

Expected: no output (success).

### Step 1.12: Commit

```bash
git add scripts/install_latest.sh
git commit -m "feat: rewrite install_latest.sh as universal installer/updater

- Detect fresh install vs update based on venv presence
- Create adsb user and install OS deps on fresh install
- Create/update venv and install requirements on every run
- Build rpi-rgb-led-matrix bindings if missing
- Preserve SQLite DBs, .env, and venv during updates
- Set adsb:adsb ownership on venv/ and data/
- Install/enable systemd units
- Health check after start with automatic rollback on failure"
```

---

## Task 2: Create `scripts/check_and_update.sh`

**Files:**
- Create: `scripts/check_and_update.sh`
- Test: `bash -n scripts/check_and_update.sh`

### Step 2.1: Write the update checker script

Create `scripts/check_and_update.sh`:

```bash
#!/bin/bash
set -euo pipefail

INSTALL_DIR="/opt/adsbledmatrix"
REPO="BChenery/adsbledmatrix"
API_URL="https://api.github.com/repos/${REPO}/releases/latest"
LOG_FILE="/var/log/adsbledmatrix-update.log"

log() {
    echo "[$(date -Iseconds)] $*" | tee -a "$LOG_FILE"
}

mkdir -p "$(dirname "$LOG_FILE")"
touch "$LOG_FILE"

if [ "$(id -u)" -ne 0 ]; then
    log "This script must be run as root"
    exit 1
fi

CURRENT_VERSION=""
if [ -f "${INSTALL_DIR}/VERSION" ]; then
    CURRENT_VERSION=$(cat "${INSTALL_DIR}/VERSION")
fi

log "Checking for updates. Current version: ${CURRENT_VERSION:-unknown}"

LATEST_JSON=$(curl -s "$API_URL")
LATEST_VERSION=$(echo "$LATEST_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin)['tag_name'])")
LATEST_VERSION=${LATEST_VERSION#v}

log "Latest release version: $LATEST_VERSION"

if [ "$CURRENT_VERSION" = "$LATEST_VERSION" ]; then
    log "Already up to date"
    exit 0
fi

# Check rollout percentage
ROLLOUT_URL=$(echo "$LATEST_JSON" | python3 -c "
import sys, json
assets = {a['name']: a['browser_download_url'] for a in json.load(sys.stdin).get('assets', [])}
print(assets.get('rollout.json', ''))
")

if [ -n "$ROLLOUT_URL" ]; then
    PERCENTAGE=$(curl -s "$ROLLOUT_URL" | python3 -c "import sys,json; print(json.load(sys.stdin).get('percentage', 100))")
    DEVICE_ID=$(cat /etc/machine-id 2>/dev/null || openssl rand -hex 16)
    BUCKET=$(echo -n "${DEVICE_ID}${LATEST_VERSION}" | sha256sum | head -c 2 | tr '[:lower:]' '[:upper:]')
    BUCKET_DEC=$((16#$BUCKET % 100))
    if [ "$BUCKET_DEC" -ge "$PERCENTAGE" ]; then
        log "Device not in rollout bucket ($BUCKET_DEC >= $PERCENTAGE); skipping update"
        exit 0
    fi
fi

# Check auto_update setting from .env first, then default to true
AUTO_UPDATE=true
if [ -f "${INSTALL_DIR}/.env" ]; then
    if grep -qE '^ADSB_AUTO_UPDATE=false' "${INSTALL_DIR}/.env"; then
        AUTO_UPDATE=false
    fi
fi

if [ "$AUTO_UPDATE" != "true" ]; then
    log "auto_update is disabled; skipping update"
    exit 0
fi

log "Applying update to $LATEST_VERSION"
exec bash -c "$(curl -fsSL https://raw.githubusercontent.com/${REPO}/main/scripts/install_latest.sh)"
```

### Step 2.2: Make it executable and syntax-check

Run:

```bash
chmod +x scripts/check_and_update.sh
bash -n scripts/check_and_update.sh
```

Expected: no output.

### Step 2.3: Commit

```bash
git add scripts/check_and_update.sh
git commit -m "feat: add daily update checker script

scripts/check_and_update.sh runs as root, checks GitHub releases,
respects rollout.json percentage and auto_update setting, then
invokes install_latest.sh to apply the update."
```

---

## Task 3: Update `systemd/adsbledmatrix-update.service`

**Files:**
- Modify: `systemd/adsbledmatrix-update.service`

### Step 3.1: Replace service content

Read the current file, then replace with:

```ini
[Unit]
Description=ADS-B LED Matrix update check
After=network.target

[Service]
Type=oneshot
User=root
Group=root
ExecStart=/opt/adsbledmatrix/scripts/check_and_update.sh
StandardOutput=append:/var/log/adsbledmatrix-update.log
StandardError=append:/var/log/adsbledmatrix-update.log
```

### Step 3.2: Commit

```bash
git add systemd/adsbledmatrix-update.service
git commit -m "fix: run update checker as root via systemd service

The app process drops privileges to adsb, so it cannot update files
or restart services. Run the update check as root instead."
```

---

## Task 4: Update `systemd/adsbledmatrix-update.timer`

**Files:**
- Modify: `systemd/adsbledmatrix-update.timer`

### Step 4.1: Ensure daily timer exists

If the file exists, update it; if not, create it with:

```ini
[Unit]
Description=Daily ADS-B LED Matrix update check

[Timer]
OnCalendar=daily
Persistent=true

[Install]
WantedBy=timers.target
```

### Step 4.2: Commit

```bash
git add systemd/adsbledmatrix-update.timer
git commit -m "feat: daily timer for root update checker"
```

---

## Task 5: Reduce `backend/app/services/updater.py` to status checker

**Files:**
- Modify: `backend/app/services/updater.py`

### Step 5.1: Remove `apply_update`, `_rollback`, `_restart_and_verify`, `_run_migrations`

Keep only:
- `__init__`
- `_get_client`
- `_fetch_text`
- `_fetch_bytes`
- `check_for_update`
- `update_database`
- `sync_data`
- `close`

Remove the imports that are no longer used: `hashlib`, `tarfile`, `shutil`, `subprocess`, `Path` references used only by removed methods, `PROJECT_ROOT` if unused.

The remaining file should look roughly like:

```python
import asyncio
import json
import logging
from typing import Optional
import httpx
from app.config import settings, PROJECT_ROOT
from app.services.device_id import get_device_id
from app.services.rollout import is_in_rollout

logger = logging.getLogger(__name__)


class UpdateService:
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

    async def update_database(self) -> bool:
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
        script = PROJECT_ROOT / "scripts" / "sync_data.py"
        import subprocess
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

Wait — `sync_data` still uses `subprocess`. That's fine because it runs inside the app and only calls a Python script in the venv; it doesn't need root. Keep it.

`PROJECT_ROOT` is exported from `app.config` and used directly (it is not a settings field).

### Step 5.2: Run existing tests

Run:

```bash
cd backend && /opt/adsbledmatrix/venv/bin/python -m pytest tests/ -q
```

If there are tests for updater, adjust or remove tests that expect `apply_update`.

### Step 5.3: Commit

```bash
git add backend/app/services/updater.py
git commit -m "refactor: remove in-app update application

UpdateService now only checks for updates and reports status.
Actual updates are applied by the root systemd update service."
```

---

## Task 6: Update `backend/app/api/system.py`

**Files:**
- Modify: `backend/app/api/system.py`

### Step 6.1: Inspect current endpoints

Read `backend/app/api/system.py` to find the update endpoints.

### Step 6.2: Remove or change the apply-update endpoint

If there is a `POST /api/system/update` that calls `updater.apply_update()`, replace it with a no-op or a trigger for the systemd timer:

```python
@router.post("/system/update")
async def trigger_update():
    """Manual update is handled by the root systemd update service.

    This endpoint exists for backwards compatibility but does not apply
    updates from the app process (which lacks privileges after the LED
    matrix drops to the adsb user).
    """
    return {"status": "manual updates are applied by systemd; check status with GET /api/system/update"}
```

Keep `GET /api/system/update` unchanged.

### Step 6.3: Commit

```bash
git add backend/app/api/system.py
git commit -m "fix: deprecate in-app update application endpoint

POST /api/system/update no longer attempts to apply updates from the
dropped-privilege app process. Updates are applied by the root systemd
update service."
```

---

## Task 7: Verify release workflow tarball

**Files:**
- Read: `.github/workflows/release.yml`

### Step 7.1: Confirm tarball contents

Ensure the workflow creates an archive with:

```text
adsbledmatrix/
  backend/
  data/
  hardware/
  scripts/
  systemd/
  docs/
  README.md
  VERSION
```

The current workflow already does this. No change needed unless the installer expects files not in the tarball.

### Step 7.2: Commit if changes needed

If no changes, skip commit.

---

## Task 8: Manual end-to-end test on the Pi

**Files:**
- All of the above

### Step 8.1: Test the update path

On the Pi, run:

```bash
sudo bash scripts/install_latest.sh
```

Verify:
- No data loss (`aircraft_db.sqlite3` still exists, settings/layouts preserved).
- Service starts and stays up: `sudo systemctl status adsbledmatrix.service`.
- Health endpoint returns OK: `curl http://127.0.0.1:8080/api/health`.
- `data/` and `venv/` are owned by `adsb:adsb`.

### Step 8.2: Test the update checker

Run:

```bash
sudo bash scripts/check_and_update.sh
```

Verify:
- If already on latest, it exits with "Already up to date".
- If a newer release exists, it invokes the installer.

### Step 8.3: Test rollback

To test rollback, temporarily break the latest release (e.g., add an invalid import to `backend/app/main.py` in a test release, or stop the service before health check). Run the installer and verify it restores the backup.

**Warning:** only do this in a controlled environment where you can recover manually.

### Step 8.4: Test fresh install (optional / separate SD card)

On a fresh Pi OS image:

```bash
curl -L https://raw.githubusercontent.com/BChenery/adsbledmatrix/main/scripts/install_latest.sh | sudo bash
```

Verify:
- `adsb` user exists.
- venv exists and contains requirements.
- `rgbmatrix` is importable.
- systemd services are enabled.
- Service starts and `/api/health` returns OK.

### Step 8.5: Commit any test fixes

If any fixes were needed during testing, commit them.

---

## Self-Review Checklist

- [ ] Spec coverage: every requirement in the design doc maps to a task above.
- [ ] No placeholders: every step has concrete code, commands, or file paths.
- [ ] Type consistency: settings object properties and environment variables match across tasks.
- [ ] Testability: manual test steps cover fresh install, update, and rollback.

**Gaps identified:** None after review.
