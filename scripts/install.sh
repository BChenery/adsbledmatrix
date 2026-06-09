#!/bin/bash
set -e

# ADS-B LED Display Installer
# Run on a fresh Raspberry Pi OS (Bookworm or later)

REPO_URL="https://github.com/BChenery/adsbledmatrix"
INSTALL_DIR="/opt/adsbledmatrix"
SERVICE_USER="adsb"

echo "============================================"
echo "  ADS-B LED Display Installer"
echo "============================================"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
  echo "Please run as root: sudo bash install.sh"
  exit 1
fi

# Update system
echo "[1/9] Updating system packages..."
apt-get update
apt-get upgrade -y

# Install dependencies
echo "[2/9] Installing dependencies..."
apt-get install -y \
  git \
  python3 \
  python3-pip \
  python3-venv \
  python3-dev \
  build-essential \
  libffi-dev \
  libssl-dev \
  libz-dev \
  rtl-sdr \
  librtlsdr-dev \
  hostapd \
  dnsmasq

# Install readsb (ADS-B decoder)
echo "[3/9] Installing readsb..."
if ! command -v readsb &> /dev/null; then
  apt-get install -y readsb || {
    echo "readsb not in apt, building from source..."
    apt-get install -y libncurses5-dev
    git clone https://github.com/wiedehopf/readsb.git /tmp/readsb
    cd /tmp/readsb
    make
    make install
    cd -
  }
fi

# Create service user
echo "[4/9] Creating service user..."
if ! id "$SERVICE_USER" &>/dev/null; then
  useradd -r -s /bin/false -d "$INSTALL_DIR" "$SERVICE_USER"
fi
usermod -a -G gpio,spi,i2c,plugdev "$SERVICE_USER"

# Clone repository
echo "[5/9] Installing application..."
if [ -d "$INSTALL_DIR" ]; then
  echo "Existing installation found. Updating..."
  cd "$INSTALL_DIR"
  git pull || true
else
  git clone "$REPO_URL" "$INSTALL_DIR"
  cd "$INSTALL_DIR"
fi

# Set up Python environment
echo "[6/9] Setting up Python environment..."
python3 -m venv "$INSTALL_DIR/venv"
source "$INSTALL_DIR/venv/bin/activate"
pip install --upgrade pip
pip install -r backend/requirements.txt

# Build rpi-rgb-led-matrix Python bindings
echo "[7/9] Building LED matrix library..."
apt-get install -y libgraphicsmagick++-dev libwebp-dev || true
if [ ! -d /tmp/rpi-rgb-led-matrix ]; then
  git clone https://github.com/hzeller/rpi-rgb-led-matrix.git /tmp/rpi-rgb-led-matrix
fi
cd /tmp/rpi-rgb-led-matrix
make -C utils || true
cd bindings/python
make build-python PYTHON="$INSTALL_DIR/venv/bin/python"
make install-python PYTHON="$INSTALL_DIR/venv/bin/python"
cd "$INSTALL_DIR"

# Build frontend
echo "[8/9] Building frontend..."
cd "$INSTALL_DIR/frontend"
npm install
npm run build
cd "$INSTALL_DIR"

# Sync all data assets for offline use
echo "[8.5/9] Syncing data assets (aircraft DB, routes, logos)..."
python3 scripts/sync_data.py || echo "Data sync incomplete (some assets may be missing)"

# Install systemd services
echo "[9/9] Installing systemd services..."
cp systemd/*.service /etc/systemd/system/
cp systemd/*.timer /etc/systemd/system/ 2>/dev/null || true
systemctl daemon-reload
systemctl enable readsb.service
systemctl enable adsbledmatrix.service
systemctl enable adsbledmatrix-update.timer
systemctl enable adsbledmatrix-sync.timer

# Set permissions
echo "[9.5/9] Setting permissions..."
chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR"
chmod +x scripts/*.sh

# Start services
systemctl start readsb
systemctl start adsbledmatrix
systemctl start adsbledmatrix-update.timer
systemctl start adsbledmatrix-sync.timer

echo ""
echo "============================================"
echo "  Installation Complete!"
echo "============================================"
echo ""
echo "The device is now running in AP mode."
echo "Connect to WiFi: ADSB-Display-XXXX"
echo "Then open: http://192.168.4.1"
echo ""
echo "To check status: sudo systemctl status adsbledmatrix"
echo "To view logs: sudo journalctl -u adsbledmatrix -f"
