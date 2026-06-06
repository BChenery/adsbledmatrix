# Setup Guide

## Hardware Assembly

### Parts List
- Raspberry Pi 4 (2GB, 4GB, or 8GB)
- MicroSD card (16GB+, Class 10)
- RTL-SDR USB dongle with antenna
- RGB LED Matrix panels (512×256 total)
- LED matrix HAT/bonnet for Pi
- 5V power supply (10A+ recommended for 4 panels)
- Cooling: heatsinks and/or fan for Pi 4

### Wiring
1. Install LED matrix HAT onto Pi GPIO header
2. Connect LED panels to HAT using ribbon cables
3. Connect 5V power to HAT (do NOT power panels from Pi USB)
4. Insert RTL-SDR into USB port
5. Attach antenna to RTL-SDR

### Panel Arrangement
For 512×256 using four 128×64 panels:
```
Panel 0 ──► Panel 1 ──► Panel 2 ──► Panel 3
(Chain: 4, Parallel: 1)
```

For 256×128 using four 64×64 panels:
```
Panel 0 ──► Panel 1   (Chain 1)
Panel 2 ──► Panel 3   (Chain 2, Parallel)
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
   sudo apt install -y git python3-pip rtl-sdr librtlsdr-dev hostapd dnsmasq
   ```

4. **Install readsb**
   ```bash
   sudo apt install -y readsb
   # OR build from source:
   git clone https://github.com/wiedehopf/readsb.git
   cd readsb && make && sudo make install
   ```

5. **Clone and install application**
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

# Test LED matrix directly
cd /opt/adsbledmatrix
source venv/bin/activate
python3 -c "
from rgbmatrix import RGBMatrix, RGBMatrixOptions
options = RGBMatrixOptions()
options.rows = 64
options.cols = 128
options.chain_length = 4
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
sudo systemctl start adsbledmatrix
# Then re-run onboarding
```
