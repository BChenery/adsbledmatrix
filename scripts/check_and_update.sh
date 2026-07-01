#!/bin/bash
set -euo pipefail

INSTALL_DIR="/opt/adsbledmatrix"
REPO="BChenery/adsbledmatrix"
API_URL="https://api.github.com/repos/${REPO}/releases/latest"
LOG_FILE="/var/log/adsbledmatrix-update.log"
LOCK_FILE="/var/run/adsbledmatrix-update.lock"
if [ ! -d "/var/run" ]; then
    LOCK_FILE="/tmp/adsbledmatrix-update.lock"
fi

log() {
    echo "[$(date -Iseconds)] $*" | tee -a "$LOG_FILE"
}

if [ "$(id -u)" -ne 0 ]; then
    log "This script must be run as root"
    exit 1
fi

mkdir -p "$(dirname "$LOG_FILE")"
touch "$LOG_FILE"

# Concurrency lock
acquire_lock() {
    if command -v flock >/dev/null 2>&1; then
        exec 200>"$LOCK_FILE"
        if ! flock -n 200; then
            log "Another update is already running; exiting"
            exit 0
        fi
        echo $$ >&200
    else
        if [ -f "$LOCK_FILE" ]; then
            OLD_PID=$(cat "$LOCK_FILE" 2>/dev/null || echo "")
            if [ -n "$OLD_PID" ] && kill -0 "$OLD_PID" 2>/dev/null; then
                log "Another update is already running (PID $OLD_PID); exiting"
                exit 0
            fi
        fi
        echo $$ > "$LOCK_FILE"
    fi
}
acquire_lock

CURRENT_VERSION=""
if [ -f "${INSTALL_DIR}/VERSION" ]; then
    CURRENT_VERSION=$(cat "${INSTALL_DIR}/VERSION")
fi

log "Checking for updates. Current version: ${CURRENT_VERSION:-unknown}"

if ! LATEST_JSON=$(curl -fsSL --max-time 60 "$API_URL"); then
    log "Failed to fetch latest release information from GitHub"
    exit 1
fi

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
    if ! PERCENTAGE_JSON=$(curl -fsSL --max-time 60 "$ROLLOUT_URL"); then
        log "Failed to fetch rollout configuration; skipping update"
        exit 1
    fi
    PERCENTAGE=$(echo "$PERCENTAGE_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin).get('percentage', 100))")

    # Persistent device ID fallback
    DEVICE_ID_FILE="${INSTALL_DIR}/data/.device_id"
    mkdir -p "$(dirname "$DEVICE_ID_FILE")"
    if [ -f /etc/machine-id ]; then
        DEVICE_ID=$(cat /etc/machine-id)
    elif [ -f "$DEVICE_ID_FILE" ]; then
        DEVICE_ID=$(cat "$DEVICE_ID_FILE")
    else
        DEVICE_ID=$(openssl rand -hex 16)
        echo "$DEVICE_ID" > "$DEVICE_ID_FILE"
    fi

    BUCKET_HEX=$(echo -n "${DEVICE_ID}${LATEST_VERSION}" | sha256sum | head -c 2 | tr '[:lower:]' '[:upper:]')
    BUCKET_DEC=$((16#$BUCKET_HEX % 100))
    if [ "$BUCKET_DEC" -ge "$PERCENTAGE" ]; then
        log "Device not in rollout bucket ($BUCKET_DEC >= $PERCENTAGE); skipping update"
        exit 0
    fi
fi

# Check auto_update setting from .env first, then default to true
AUTO_UPDATE=true
if [ -f "${INSTALL_DIR}/.env" ]; then
    VALUE=$(grep -E '^\s*ADSB_AUTO_UPDATE\s*=' "${INSTALL_DIR}/.env" | sed 's/.*=//' | tr -d "[:space:]'\"" | tr '[:upper:]' '[:lower:]')
    if [ "$VALUE" = "false" ] || [ "$VALUE" = "0" ]; then
        AUTO_UPDATE=false
    fi
fi

if [ "$AUTO_UPDATE" != "true" ]; then
    log "auto_update is disabled; skipping update"
    exit 0
fi

log "Applying update to $LATEST_VERSION"

INSTALL_SCRIPT=$(mktemp)
trap 'rm -f "$INSTALL_SCRIPT"' EXIT
if ! curl -fsSL --max-time 60 "https://raw.githubusercontent.com/${REPO}/main/scripts/install_latest.sh" -o "$INSTALL_SCRIPT"; then
    log "Failed to download install script"
    exit 1
fi
if ! bash -n "$INSTALL_SCRIPT"; then
    log "Downloaded install script failed syntax check"
    exit 1
fi
exec bash "$INSTALL_SCRIPT"
