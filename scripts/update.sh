#!/bin/bash
set -e

INSTALL_DIR="/opt/adsbledmatrix"
BACKUP_DIR="/opt/adsbledmatrix-backup"

echo "ADS-B LED Display Updater"

if [ "$EUID" -ne 0 ]; then
  echo "Please run as root: sudo bash update.sh"
  exit 1
fi

# Backup current installation
echo "Creating backup..."
rm -rf "$BACKUP_DIR"
cp -r "$INSTALL_DIR" "$BACKUP_DIR"

# Pull latest code
echo "Pulling latest code..."
cd "$INSTALL_DIR"
git pull origin main

# Update Python dependencies
echo "Updating dependencies..."
source "$INSTALL_DIR/venv/bin/activate"
pip install -r backend/requirements.txt

# Rebuild frontend
echo "Rebuilding frontend..."
cd "$INSTALL_DIR/frontend"
npm install
npm run build

# Sync all data assets
echo "Syncing data assets..."
cd "$INSTALL_DIR"
python3 scripts/sync_data.py || echo "Data sync incomplete"

# Restart services
echo "Restarting services..."
systemctl restart adsbledmatrix

echo "Update complete!"
