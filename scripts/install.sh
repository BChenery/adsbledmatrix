#!/bin/bash
set -e

# ADS-B LED Display Installer
# Run on a fresh Raspberry Pi OS (Bookworm or later)

REPO_URL="https://github.com/BChenery/adsbledmatrix"
INSTALL_DIR="/opt/adsbledmatrix"
SERVICE_USER="adsb"

# Helper: enable SPI (required by rpi-rgb-led-matrix)
enable_spi() {
  echo "[3.5/8] Enabling SPI interface..."
  if command -v raspi-config >/dev/null 2>&1; then
    raspi-config nonint do_spi 0 || true
  fi
  # Belt-and-suspenders: make sure the overlay is set in config.txt
  local config_file="/boot/config.txt"
  [ -f /boot/firmware/config.txt ] && config_file="/boot/firmware/config.txt"
  if [ -f "$config_file" ] && ! grep -q "^dtparam=spi=on" "$config_file"; then
    echo "dtparam=spi=on" >> "$config_file"
  fi
}

# Helper: disable onboard audio (it shares timing hardware with the LED matrix)
disable_onboard_audio() {
  echo "[3.6/8] Disabling onboard audio (shares hardware with LED matrix)..."
  local config_file="/boot/config.txt"
  [ -f /boot/firmware/config.txt ] && config_file="/boot/firmware/config.txt"
  if [ -f "$config_file" ] && ! grep -q "^dtparam=audio=off" "$config_file"; then
    echo "dtparam=audio=off" >> "$config_file"
  fi
  if [ ! -f /etc/modprobe.d/blacklist-rgb-matrix.conf ]; then
    echo "blacklist snd_bcm2835" > /etc/modprobe.d/blacklist-rgb-matrix.conf
    update-initramfs -u || true
  fi
}

# Helper: build and install the rpi-rgb-led-matrix Python bindings into the venv
install_led_matrix_library() {
  echo "[6.1/8] Building rpi-rgb-led-matrix Python bindings..."
  local build_dir="/tmp/rpi-rgb-led-matrix"
  rm -rf "$build_dir"
  git clone --depth 1 https://github.com/hzeller/rpi-rgb-led-matrix.git "$build_dir"
  cd "$build_dir"
  # Modern rpi-rgb-led-matrix uses scikit-build-core + pyproject.toml
  python3 -m pip install .
  cd "$INSTALL_DIR"
  python3 -c "import rgbmatrix; print('rgbmatrix OK')"
}

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
  python3-setuptools \
  build-essential \
  cmake \
  ninja-build \
  cython3 \
  libffi-dev \
  libssl-dev \
  libz-dev \
  libzstd-dev \
  libgraphicsmagick++-dev \
  libwebp-dev \
  rtl-sdr \
  librtlsdr-dev \
  hostapd \
  dnsmasq \
  iptables \
  iptables-persistent \
  network-manager \
  avahi-daemon \
  raspi-config \
  sqlite3 \
  rfkill

# Install readsb (ADS-B decoder)
echo "[3/8] Installing readsb..."
# Always build from source so RTL-SDR support is guaranteed.
# The apt package is often compiled without it.
apt-get install -y libncurses5-dev
# Stop the service before overwriting the binary so the copy doesn't fail
systemctl stop readsb || true
if [ -d "/tmp/readsb" ]; then
  rm -rf /tmp/readsb
fi
git clone https://github.com/wiedehopf/readsb.git /tmp/readsb
cd /tmp/readsb
make clean
make RTLSDR=yes
cp readsb /usr/local/bin/readsb
chmod +x /usr/local/bin/readsb
cd -
if [ ! -f "/usr/local/bin/readsb" ]; then
  echo "ERROR: readsb binary not found at /usr/local/bin/readsb"
  exit 1
fi

# Blacklist the DVB-T TV driver so it doesn't steal the RTL-SDR dongle
echo "blacklist dvb_usb_rtl28xxu" > /etc/modprobe.d/blacklist-rtl-sdr.conf
# Unload it now if it's already loaded
rmmod dvb_usb_rtl28xxu 2>/dev/null || true

# Enable SPI and disable onboard audio for the LED matrix
enable_spi
disable_onboard_audio

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
  repo_owner=$(stat -c '%U' "$INSTALL_DIR")
  if [ "$repo_owner" = "$(whoami)" ]; then
    git pull || true
  else
    sudo -u "$repo_owner" git pull || true
  fi
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

# Build and install the LED matrix library
install_led_matrix_library

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
python3 scripts/sync_data.py --force || echo "Data sync incomplete (some assets may be missing)"

# Import localadsb databases if present
echo "[6.7/8] Importing localadsb aircraft and route databases..."
python3 scripts/import_localadsb.py || echo "localadsb import skipped or failed"

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
echo "adsb ALL=(ALL) NOPASSWD: /sbin/reboot, /usr/sbin/reboot, /sbin/shutdown, /usr/sbin/shutdown, /usr/sbin/nmcli, /usr/sbin/iptables, /usr/sbin/netfilter-persistent, /bin/systemctl restart adsbledmatrix" >> /etc/sudoers.d/adsbledmatrix
chmod 440 /etc/sudoers.d/adsbledmatrix

# Set permissions
echo "[8/8] Setting permissions..."
# The main service and manual update/verify scripts run as root, so keep the
# application code and git repo root-owned. Only runtime data needs to be
# writable by the adsb service user.
chown -R root:root "$INSTALL_DIR"
chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR/data"
chmod +x scripts/*.sh

# Ensure netfilter-persistent is enabled so iptables rules survive reboots
systemctl enable netfilter-persistent || true

# Start/restart services so the new code and systemd units take effect.
# (Don't fail the whole install if one service can't start yet.)
systemctl start readsb || true
systemctl restart adsbledmatrix || true
systemctl start adsbledmatrix-update.timer || true
systemctl start adsbledmatrix-sync.timer || true
systemctl start avahi-daemon || true

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
echo ""
echo "Rebooting in 10 seconds..."
sleep 10
reboot
