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
echo "[1/8] Updating system packages..."
apt-get update
apt-get upgrade -y

# Install dependencies
echo "[2/8] Installing dependencies..."
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
echo "[3/8] Installing readsb..."
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
echo "[4/8] Creating service user..."
if ! id "$SERVICE_USER" &>/dev/null; then
  useradd -r -s /bin/false -d "$INSTALL_DIR" "$SERVICE_USER"
fi
usermod -a -G gpio,spi,i2c,plugdev "$SERVICE_USER"

# Clone repository
echo "[5/8] Installing application..."
if [ -d "$INSTALL_DIR" ]; then
  echo "Existing installation found. Updating..."
  cd "$INSTALL_DIR"
  git pull || true
else
  git clone "$REPO_URL" "$INSTALL_DIR"
  cd "$INSTALL_DIR"
fi

# Set up Python environment
echo "[6/8] Setting up Python environment..."
python3 -m venv "$INSTALL_DIR/venv"
source "$INSTALL_DIR/venv/bin/activate"
pip install --upgrade pip
pip install -r backend/requirements.txt

# Build frontend
echo "[6.5/8] Building frontend..."
cd "$INSTALL_DIR/frontend"
npm install
npm run build
cd "$INSTALL_DIR"

# Install systemd services
echo "[7/8] Installing systemd services..."
cp systemd/*.service /etc/systemd/system/
cp systemd/*.timer /etc/systemd/system/ 2>/dev/null || true
systemctl daemon-reload
systemctl enable readsb.service
systemctl enable adsbledmatrix.service

# Set permissions
echo "[8/8] Setting permissions..."
chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR"
chmod +x scripts/*.sh

# Start services
systemctl start readsb
systemctl start adsbledmatrix

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
