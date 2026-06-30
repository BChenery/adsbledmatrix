#!/bin/bash
set -e

INSTALL_DIR="/opt/adsbledmatrix"
REPO="BChenery/adsbledmatrix"
API_URL="https://api.github.com/repos/${REPO}/releases/latest"

echo "Checking latest release..."
LATEST=$(curl -s "$API_URL" | python3 -c "import sys,json; print(json.load(sys.stdin)['tag_name'])")
echo "Latest release: $LATEST"

ARCHIVE="adsbledmatrix-${LATEST}.tar.gz"
CHECKSUM="${ARCHIVE}.sha256"
BASE_URL="https://github.com/${REPO}/releases/download/${LATEST}"

cd /tmp
curl -L -o "$ARCHIVE" "$BASE_URL/$ARCHIVE"
curl -L -o "$CHECKSUM" "$BASE_URL/$CHECKSUM"
sha256sum -c "$CHECKSUM"

BACKUP_DIR="${INSTALL_DIR}-backup-$(date +%Y%m%d%H%M%S)"
echo "Stopping service and backing up current install to $BACKUP_DIR..."
sudo systemctl stop adsbledmatrix.service
sudo cp -a "$INSTALL_DIR" "$BACKUP_DIR"

sudo rm -rf /tmp/adsbledmatrix
sudo tar -xzf "$ARCHIVE" -C /tmp

sudo rsync -a --delete /tmp/adsbledmatrix/ "$INSTALL_DIR/"

echo "Starting service..."
sudo systemctl start adsbledmatrix.service

echo "Done. Check status with: sudo systemctl status adsbledmatrix.service"
