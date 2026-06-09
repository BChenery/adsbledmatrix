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

# Prevent interactive prompts from packages like iptables-persistent
export DEBIAN_FRONTEND=noninteractive

# Update system
echo "[1/8] Updating system packages..."
apt-get update
apt-get upgrade -y

# Install dependencies
echo "[2/8] Installing dependencies..."
apt-get install -y \
  git \
  nodejs \
  npm \
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
  dnsmasq \
  network-manager \
  avahi-daemon

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
# Ensure Node.js and npm are actually available (defensive fallback)
if ! command -v npm &> /dev/null; then
  echo "npm not found. Installing nodejs and npm..."
  apt-get install -y nodejs npm
fi
cd "$INSTALL_DIR/frontend"
npm install
npm run build
cd "$INSTALL_DIR"

# Sync all data assets for offline use
echo "[6.6/8] Syncing data assets (aircraft DB, routes, logos)..."
python3 scripts/sync_data.py || echo "Data sync incomplete (some assets may be missing)"

# Set up WiFi access point for onboarding
echo "[7/8] Setting up WiFi access point..."
# Generate unique SSID suffix from MAC
WLAN_IFACE=$(iw dev | awk '$1=="Interface"{print $2}')
MAC_SUFFIX=$(cat /sys/class/net/${WLAN_IFACE:-wlan0}/address 2>/dev/null | tr -d ':' | tail -c 5 | tr '[:lower:]' '[:upper:]')
AP_SSID="ADSB-Display-${MAC_SUFFIX:-0000}"

# Run wifi manager to establish AP mode and port redirect
python3 scripts/wifi_manager.py setup-ap || echo "WiFi manager failed, continuing anyway"

# Install systemd services
echo "[7.5/8] Installing systemd services..."
cp systemd/*.service /etc/systemd/system/
cp systemd/*.timer /etc/systemd/system/ 2>/dev/null || true
systemctl daemon-reload
systemctl enable readsb.service
systemctl enable adsbledmatrix-wifi.service
systemctl enable adsbledmatrix.service
systemctl enable adsbledmatrix-update.timer
systemctl enable adsbledmatrix-sync.timer
systemctl enable avahi-daemon.service

# Allow the adsb service user to manage WiFi and reboot without a password
echo "adsb ALL=(ALL) NOPASSWD: /opt/adsbledmatrix/venv/bin/python3 /opt/adsbledmatrix/scripts/wifi_manager.py *" > /etc/sudoers.d/adsbledmatrix
echo "adsb ALL=(ALL) NOPASSWD: /sbin/reboot, /usr/sbin/reboot, /sbin/shutdown, /usr/sbin/shutdown, /usr/sbin/nmcli, /usr/sbin/iptables, /usr/sbin/netfilter-persistent" >> /etc/sudoers.d/adsbledmatrix
chmod 440 /etc/sudoers.d/adsbledmatrix

# Set permissions
echo "[8/8] Setting permissions..."
chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR"
chmod +x scripts/*.sh

# Start services
systemctl start readsb
systemctl start adsbledmatrix
systemctl start adsbledmatrix-update.timer
systemctl start adsbledmatrix-sync.timer
systemctl start avahi-daemon

echo ""
echo "============================================"
echo "  Installation Complete!"
echo "============================================"
echo ""
echo "The device is now running in AP mode."
echo "Connect to WiFi: ${AP_SSID}"
echo "Then open: http://192.168.4.1"
echo ""
echo "To check status: sudo systemctl status adsbledmatrix"
echo "To view logs: sudo journalctl -u adsbledmatrix -f"
