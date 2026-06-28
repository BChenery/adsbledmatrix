# Setup Guide

## Hardware Assembly

### Parts List
- Raspberry Pi 4 (2GB, 4GB, or 8GB)
- MicroSD card (16GB+, Class 10)
- RTL-SDR USB dongle with antenna
- RGB LED Matrix panels (256×128 total recommended; see below)
- Single-channel HUB75 adapter for Raspberry Pi (e.g. AliExpress "Conversion board for Raspberry Pi to HUB75")
- 5V power supply (10A+ recommended for 4 panels)
- Cooling: heatsinks and/or fan for Pi 4

### Wiring
1. Plug the HUB75 adapter onto the Pi 40-pin GPIO header
2. Connect Panel 1 IN to the adapter with a HUB75 ribbon cable
3. Chain the remaining panels with ribbon cables in serpentine order (see Panel Arrangement)
4. Connect 5V power directly to the panels (do NOT power panels from the Pi)
5. Insert RTL-SDR into a USB port and attach the antenna

### Panel Arrangement
The default configuration is a **256×128** display made from four 128×64 panels wired in a single chain with the `U-mapper`:

```
Panel 1 ──► Panel 2   (top row, left to right)
             │
             ▼
Panel 4 ◄── Panel 3   (bottom row, right to left, serpentine)
(Chain: 4, Parallel: 1, Pixel mapper: U-mapper)
```

Set these environment variables in `/opt/adsbledmatrix/.env`:
```bash
ADSB_LED_MATRIX_ROWS=64
ADSB_LED_MATRIX_COLS=128
ADSB_LED_MATRIX_CHAIN=4
ADSB_LED_MATRIX_PARALLEL=1
ADSB_LED_MATRIX_PIXEL_MAPPER=U-mapper
ADSB_LED_MATRIX_HARDWARE_MAPPING=regular
ADSB_LED_MATRIX_ROW_ADDRESS_TYPE=0
ADSB_LED_MATRIX_BRIGHTNESS=70
ADSB_LED_MATRIX_PWM_BITS=7
ADSB_LED_MATRIX_GPIO_SLOWDOWN=4
```

> ⚠️ `rpi-rgb-led-matrix` supports a maximum of **3 parallel chains** on a standard 40-pin Raspberry Pi. A 512×256 arrangement using sixteen 128×64 panels (4 wide × 4 tall) requires a Raspberry Pi Compute Module or an active adapter board that provides 4+ parallel chains. It will not work on a Pi 4 with a single-channel adapter using `parallel=4`.
>
> On a standard Pi you can still drive 512×256 by wiring all sixteen 128×64 panels in **one chain** and using the `U-mapper`. Set `chain=16`, `parallel=1`, and `pixel_mapper=U-mapper`.

For 512×256 using sixteen 128×64 panels in a single chain with U-mapper:
```
Panel 0  ──► Panel 1  ──► Panel 2  ──► Panel 3
Panel 7  ◄── Panel 6  ◄── Panel 5  ◄── Panel 4
Panel 8  ──► Panel 9  ──► Panel 10 ──► Panel 11
Panel 15 ◄── Panel 14 ◄── Panel 13 ◄── Panel 12
(Chain: 16, Parallel: 1, Pixel mapper: U-mapper)
```

## Software Installation

### Option 1: One-Line Installer (Recommended)
```bash
curl -fsSL https://raw.githubusercontent.com/BChenery/adsbledmatrix/main/scripts/install.sh | sudo bash
```

### Option 2: Manual Installation

1. **Flash Raspberry Pi OS**
   ```bash
   # Use Raspberry Pi Imager or:
   dd if=2024-XX-XX-raspios-bookworm-arm64.img of=/dev/sdX bs=4M status=progress
   ```

2. **Boot and configure**
   ```bash
   sudo raspi-config
   # Enable SPI interface
   # Set hostname to "adsb-display"
   ```

3. **Install dependencies**
   ```bash
   sudo apt update
   sudo apt install -y git python3-pip rtl-sdr librtlsdr-dev hostapd dnsmasq sqlite3 rfkill
   ```

4. **Install readsb**
   ```bash
   sudo apt install -y readsb
   # OR build from source:
   git clone https://github.com/wiedehopf/readsb.git /tmp/readsb
   cd /tmp/readsb
   make clean
   make RTLSDR=yes
   sudo cp readsb /usr/local/bin/readsb
   ```

5. **Install rpi-rgb-led-matrix**
   This step is handled automatically by the installer in step 1. It enables SPI, disables the conflicting onboard audio device, and builds the `rpi-rgb-led-matrix` Python bindings into the project virtualenv.
   If you are installing manually, run the same commands that the installer uses:
   ```bash
   sudo apt install -y libgraphicsmagick++-dev libwebp-dev cython3 cmake ninja-build
   sudo raspi-config nonint do_spi 0
   git clone https://github.com/hzeller/rpi-rgb-led-matrix.git /tmp/rpi-rgb-led-matrix
   cd /tmp/rpi-rgb-led-matrix
   python3 -m pip install .
   cd /opt/adsbledmatrix
   ```

6. **Clone and install application**
   ```bash
   git clone https://github.com/BChenery/adsbledmatrix.git /opt/adsbledmatrix
   cd /opt/adsbledmatrix
   python3 -m venv venv
   source venv/bin/activate
   pip install -r backend/requirements.txt
   ```

6. **Build frontend**
   ```bash
   cd frontend
   npm install
   npm run build
   cd ..
   ```

7. **Import aircraft database**
   ```bash
   python3 scripts/import_aircraft_db.py data/aircraft_db.csv
   ```

8. **Install systemd services**
   ```bash
   sudo cp systemd/*.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable readsb adsbledmatrix
   sudo systemctl start readsb adsbledmatrix
   ```

## First Boot / Onboarding

After installation and reboot:

1. The Pi creates a WiFi access point: `ADSB-Display-XXXX`
2. Connect to it with password: `adsbsetup`
3. Open http://192.168.4.1 in your browser
4. Follow the wizard:
   - Set your latitude/longitude
   - Choose a display layout
   - Enter home WiFi credentials
5. The Pi will restart and join your home network
6. Access it at http://adsb-display.local or your router's assigned IP

## Troubleshooting

### No aircraft showing
```bash
# Check if readsb is receiving data
sudo journalctl -u readsb -f

# Check SBS output
nc localhost 30003
# You should see MSG lines every few seconds

# Check receiver service logs
sudo journalctl -u adsbledmatrix -f
```

### LED matrix not working
```bash
# Check SPI is enabled
ls /dev/spi*
# Should show /dev/spi0.0 and /dev/spi0.1

# Test LED matrix directly (uses the default 4-panel 128x64 U-mapper config)
cd /opt/adsbledmatrix
source venv/bin/activate
sudo python3 -c "
from rgbmatrix import RGBMatrix, RGBMatrixOptions
options = RGBMatrixOptions()
options.rows = 64
options.cols = 128
options.chain_length = 4
options.parallel = 1
options.hardware_mapping = 'regular'
options.pixel_mapper_config = 'U-mapper'
options.row_address_type = 0
options.gpio_slowdown = 4
matrix = RGBMatrix(options=options)
matrix.Fill(255, 0, 0)
"
```

### Web interface not accessible
```bash
# Check if service is running
sudo systemctl status adsbledmatrix

# Check firewall
sudo iptables -L -n | grep 8080

# Test API directly
curl http://localhost:8080/api/health
```

### Poor ADS-B reception
- Move antenna near a window or outside
- Use a dedicated 1090MHz antenna (not the stock RTL-SDR dipole)
- Enable bias-T if using an active antenna: `readsb --device-type rtlsdr --enable-bias-tee`
- Check for interference: `rtl_test -p`

## Advanced Configuration

### Custom Layouts
1. Open http://adsb-display.local/designer
2. Create a new layout or edit existing
3. Drag elements onto the 512×256 canvas
4. Set colors, fonts, data bindings
5. Save and activate

### Night Mode
1. Go to Settings → Night Mode
2. Enable and set start/end times
3. Display will automatically dim during those hours

### Manual Update
```bash
sudo bash /opt/adsbledmatrix/scripts/update.sh
```

### Factory Reset
```bash
sudo systemctl stop adsbledmatrix
sudo rm /opt/adsbledmatrix/data/aircraft_db.sqlite3
sudo reboot
# After reboot the AP will reappear so you can re-run onboarding
```

Or without rebooting:
```bash
sudo systemctl stop adsbledmatrix
sudo rm /opt/adsbledmatrix/data/aircraft_db.sqlite3
sudo /opt/adsbledmatrix/venv/bin/python3 /opt/adsbledmatrix/scripts/wifi_manager.py setup-ap
sudo systemctl start adsbledmatrix
```
