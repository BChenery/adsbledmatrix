#!/bin/bash
set -euo pipefail

INSTALL_DIR="/opt/adsbledmatrix"
REPO="BChenery/adsbledmatrix"
API_URL="https://api.github.com/repos/${REPO}/releases/latest"
LOG_FILE="/var/log/adsbledmatrix-update.log"

log() {
    echo "[$(date -Iseconds)] $*" | tee -a "$LOG_FILE"
}

if [ "$(id -u)" -ne 0 ]; then
    log "This script must be run as root"
    exit 1
fi

mkdir -p "$(dirname "$LOG_FILE")"
touch "$LOG_FILE"

CURRENT_VERSION=""
if [ -f "${INSTALL_DIR}/VERSION" ]; then
    CURRENT_VERSION=$(cat "${INSTALL_DIR}/VERSION")
fi

log "Checking for updates. Current version: ${CURRENT_VERSION:-unknown}"

LATEST_JSON=$(curl -fsSL "$API_URL")
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
    PERCENTAGE=$(curl -fsSL "$ROLLOUT_URL" | python3 -c "import sys,json; print(json.load(sys.stdin).get('percentage', 100))")
    DEVICE_ID=$(cat /etc/machine-id 2>/dev/null || openssl rand -hex 16)
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
