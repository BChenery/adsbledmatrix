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
repo_owner=$(stat -c '%U' "$INSTALL_DIR")
if [ "$repo_owner" = "$(whoami)" ]; then
  git pull origin main
else
  sudo -u "$repo_owner" git pull origin main
fi

# Update Python dependencies
echo "Updating dependencies..."
source "$INSTALL_DIR/venv/bin/activate"
pip install -r backend/requirements.txt

# Ensure the LED matrix Python bindings are still present (rebuild if missing)
echo "Checking LED matrix bindings..."
if ! python3 -c "import rgbmatrix" 2>/dev/null; then
  echo "LED matrix bindings missing; rebuilding..."
  rm -rf /tmp/rpi-rgb-led-matrix
  git clone --depth 1 https://github.com/hzeller/rpi-rgb-led-matrix.git /tmp/rpi-rgb-led-matrix
  cd /tmp/rpi-rgb-led-matrix
  python3 -m pip install .
  cd "$INSTALL_DIR"
fi

# Rebuild frontend
echo "Rebuilding frontend..."
cd "$INSTALL_DIR/frontend"
npm install
npm run build

# Sync all data assets
echo "Syncing data assets..."
cd "$INSTALL_DIR"
python3 scripts/sync_data.py || echo "Data sync incomplete"

# Install any updated systemd units and reload
echo "Updating systemd units..."
cp "$INSTALL_DIR"/systemd/*.service /etc/systemd/system/
cp "$INSTALL_DIR"/systemd/*.timer /etc/systemd/system/ 2>/dev/null || true
systemctl daemon-reload

# Restart services
echo "Restarting services..."
systemctl restart adsbledmatrix

echo "Update complete!"
