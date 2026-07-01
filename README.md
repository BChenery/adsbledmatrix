# ADS-B LED Aircraft Display

A complete, consumer-ready ADS-B aircraft display system for Raspberry Pi 4. Receives real-time aircraft transponder signals via RTL-SDR, decodes them with [`readsb`](https://github.com/wiedehopf/readsb), and renders the closest aircraft onto a configurable 256×128 RGB LED matrix — all controllable through a built-in web interface.

---

## ✨ Features

- **Real-Time ADS-B Reception** — Decodes 1090 MHz transponder signals using RTL-SDR + `readsb`
- **256×128 LED Matrix Display** — Shows the nearest aircraft with fully customizable layouts
- **Visual Layout Designer** — Drag-and-drop web UI to design exactly what appears on the LED panel
- **Onboarding Wizard** — First-boot WiFi captive portal for location, network, and display setup
- **Aircraft Database** — Local SQLite enrichment with registration, type, operator, and airline logos
- **Auto-Update** — Daily background checks for software and aircraft database updates via GitHub
- **Night Mode** — Automatically dims the display during configured hours
- **Multi-Aircraft Cycling** — Rotate through closest aircraft or show compact list views
- **Live Web Preview** — WebSocket-streamed aircraft data viewed in the browser

---

## 🛠 Hardware Requirements

| Component | Recommendation |
|-----------|----------------|
| **Computer** | Raspberry Pi 4 (2 GB, 4 GB, or 8 GB) |
| **Storage** | MicroSD card (16 GB+, Class 10) |
| **Receiver** | RTL-SDR USB dongle with 1090 MHz antenna |
| **Display** | RGB LED Matrix panels (default config is 256×128; larger arrangements need a Compute Module or active adapter) |
| **Driver** | Single-channel HUB75 adapter board for Raspberry Pi (e.g. AliExpress "Conversion board for Raspberry Pi to HUB75") |
| **Power** | 5 V power supply (10 A+ recommended for 4 panels) |
| **Cooling** | Heatsinks and/or fan for the Pi 4 |

> **Note:** Do not power the LED panels from the Pi's USB port. Use a separate 5 V supply.

---

## 🚀 Quick Start

### One-Line Installer (Recommended)

Flash **Raspberry Pi OS (64-bit)** to your SD card, boot the Pi, and run:

```bash
curl -fsSL https://raw.githubusercontent.com/BChenery/adsbledmatrix/main/scripts/install.sh | sudo bash
```

The installer will:
- Install system dependencies (`readsb`, SPI drivers, etc.)
- Enable SPI and disable the onboard audio device (both required for the LED matrix)
- Build and install the `rpi-rgb-led-matrix` Python bindings
- Clone this repository to `/opt/adsbledmatrix`
- Build the frontend and install Python dependencies
- Import the aircraft database
- Install and start the systemd services

### Verify the LED matrix is working

After the installer finishes and the Pi reboots, you can make sure the LED panels are wired correctly by running this one-liner on the Pi:

```bash
curl -X POST http://localhost:8080/api/display/test
```

The matrix should flash a quick **red → green → blue** test pattern. If you want a full system health check instead, run:

```bash
sudo bash /opt/adsbledmatrix/scripts/verify.sh
```

### First Boot / Onboarding (Super Simple Steps)

This is the part where you tell the little computer in the box where you live and how to get on your internet. It only takes a few minutes.

#### What you need before you start
- A phone, tablet, or computer that can connect to WiFi
- The name of your home WiFi network (often called the **SSID**)
- The password for your home WiFi network
- Your address or your latitude/longitude (the wizard can look this up for you)

#### Step 1: Install the software
Copy this one line, paste it into the Pi's terminal, and press Enter. It does all the hard work for you.

```bash
curl -fsSL https://raw.githubusercontent.com/BChenery/adsbledmatrix/main/scripts/install.sh | sudo bash
```

This command downloads the aeroplane-tracker program and sets everything up. It will take a few minutes. When it is done, the Pi will restart itself.

#### Step 2: Wait for the new WiFi network to appear
After the Pi restarts, it creates its own little WiFi network so you can talk to it. This network is called something like:

**`ADSB-Display-XXXX`**

The `XXXX` part is the last few letters from the Pi's network card, so every box has a slightly different name.

Go to the WiFi settings on your phone or computer. You will see `ADSB-Display-XXXX` in the list of networks. Tap it and type this password:

**`adsbsetup`**

> 💡 **Tip:** While you are connected to this network, your phone will say "No internet." That is normal. The Pi is not giving you internet — it is just giving you a direct line to talk to it.

#### Step 3: The setup page should pop up by itself
Because the Pi is acting like a WiFi hotspot, your phone or computer will notice and show a window that says something like "Sign in to network" or "Captive portal." Tap that window.

If the window does **not** pop up, open your web browser (Safari, Chrome, Edge, etc.) and type this exact address:

**`http://192.168.4.1`**

Then press Enter. The setup wizard will appear.

#### Step 4: Tell the wizard about your home
The wizard has four little steps:

1. **Welcome** — Tap "Get Started."
2. **Location** — Type your town, suburb, or address into the search box. Pick the right result, or type your latitude and longitude if you know them. This tells the box where it is so it can work out how far away the aeroplanes are.
3. **Layout** — Pick how you want the information to look on the LED screen. You can change this later.
4. **WiFi** — Type the name of your home WiFi network and its password. This is so the Pi can leave its temporary hotspot and join your real internet.

When you tap **Finish Setup**, the Pi saves everything, switches to your home WiFi, and restarts.

#### Step 5: Connect back to your home WiFi
The Pi will turn off its temporary `ADSB-Display-XXXX` network and join your home WiFi instead. On your phone or computer, go back to your WiFi settings and reconnect to your normal home network.

#### Step 6: Open the display any time you want
Now that the Pi is on your home network, you can visit it in your browser using this easy address:

**`http://adsb-display.local`**

If that does not work, you can also look at your router's list of connected devices to find the Pi's new IP address.

---

#### What if something goes wrong?

- **I cannot see `ADSB-Display-XXXX` in my WiFi list.**
  - Make sure the Pi has finished starting up. It can take 1–2 minutes after the green light stops blinking.
  - Try turning the Pi off and on again.
  - If you still cannot see it, connect a keyboard/monitor or SSH in and run:
    ```bash
    sudo /opt/adsbledmatrix/venv/bin/python3 /opt/adsbledmatrix/scripts/wifi_manager.py setup-ap
    ```
    The hotspot should appear within a few seconds.

- **The setup page does not open.**
  - Make sure you are connected to `ADSB-Display-XXXX`.
  - Open your browser and type `http://192.168.4.1` manually.
  - Try a different browser or device.

- **The Pi does not connect to my home WiFi after setup.**
  - Check that you typed the WiFi name and password correctly.
  - The Pi will automatically fall back to the `ADSB-Display-XXXX` hotspot if it cannot connect, so you can try again.
  - Make sure your home WiFi is a normal 2.4 GHz or 5 GHz network with a password (not a special office or hotel login page).

- **I typed the wrong WiFi password.**
  - Connect to `ADSB-Display-XXXX` again, open `http://192.168.4.1`, and go through the wizard once more.

---

## 📁 Project Structure

```
adsbledmatrix/
├── backend/               # FastAPI + Python services
│   ├── app/
│   │   ├── api/           # REST endpoints & WebSocket
│   │   ├── services/      # ADSB receiver, display engine, updater
│   │   └── static/        # Built React frontend assets
│   ├── tests/
│   ├── pyproject.toml
│   └── requirements.txt
├── frontend/              # React + TypeScript + Tailwind CSS + Vite
│   └── src/
│       ├── components/
│       │   ├── LayoutDesigner/    # Canvas-based LED designer
│       │   ├── OnboardingWizard/  # First-boot captive portal
│       │   ├── Settings/          # Device & display settings
│       │   └── LiveAircraft/      # Real-time aircraft list
│       ├── hooks/
│       └── types/
├── hardware/              # LED matrix abstraction & mock driver
├── data/                  # SQLite DB, aircraft CSV, airline logos
├── scripts/               # Installation & update helpers
├── systemd/               # systemd service & timer definitions
└── docs/                  # Architecture & setup documentation
```

---

## 🧑‍💻 Development

### Prerequisites

- Python 3.10+
- Node.js 18+
- `rtl-sdr` and `readsb` (for live ADS-B data; optional for UI dev)

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The `npm run dev` command starts **both** the backend (port `8000`) and the frontend dev server (port `5173`) concurrently. The frontend proxies API calls to `localhost:8000` automatically.

To run them separately:

```bash
npm run dev:backend   # Uvicorn on port 8000
npm run dev:frontend  # Vite on port 5173
```

---

## ⚙️ Configuration

Environment variables (all prefixed with `ADSB_`):

| Variable | Default | Description |
|----------|---------|-------------|
| `ADSB_DATA_DIR` | `./data` | Path to data directory |
| `ADSB_READSB_HOST` | `127.0.0.1` | `readsb` TCP host |
| `ADSB_READSB_PORT` | `30003` | `readsb` SBS/BaseStation port |
| `ADSB_LED_MATRIX_ROWS` | `64` | LED panel rows |
| `ADSB_LED_MATRIX_COLS` | `128` | LED panel columns |
| `ADSB_LED_MATRIX_CHAIN` | `4` | Panels chained |
| `ADSB_LED_MATRIX_PARALLEL` | `1` | Parallel chains (max 3 on a standard Pi) |
| `ADSB_LED_MATRIX_HARDWARE_MAPPING` | `regular` | HUB75 mapping (`regular`, `adafruit-hat`, `adafruit-hat-pwm`) |
| `ADSB_LED_MATRIX_PIXEL_MAPPER` | `U-mapper` | Pixel mapper, e.g. `U-mapper` for serpentine chained grids |
| `ADSB_LED_MATRIX_ROW_ADDRESS_TYPE` | `0` | Row address type (0–5) |
| `ADSB_LED_MATRIX_MULTIPLEXING` | `0` | Multiplexing type (0–17) |
| `ADSB_LED_MATRIX_PANEL_TYPE` | `""` | Panel type, e.g. `FM6126A` |
| `ADSB_LED_MATRIX_PWM_BITS` | `7` | PWM bits (1–11) |
| `ADSB_LED_MATRIX_BRIGHTNESS` | `70` | Brightness (0–100) |
| `ADSB_LED_MATRIX_GPIO_SLOWDOWN` | `4` | GPIO slowdown (0–4) |
| `ADSB_LED_MATRIX_FLIP_VERTICAL` | `true` | Swap top/bottom panel rows for bottom-fed HUB75 wiring |
| `ADSB_LED_MATRIX_RGB_SEQUENCE` | `BGR` | RGB channel order (`RGB` or `BGR`) |
| `ADSB_GITHUB_REPO` | `BChenery/adsbledmatrix` | Update source repo |

---

## 🔄 Updating

The device checks for updates daily via a systemd timer. You can also trigger a manual update:

```bash
sudo bash /opt/adsbledmatrix/scripts/update.sh
```

Or via the web UI: **Settings → Updates → Check Now**

Rollback copies are preserved in `/opt/adsbledmatrix-backup/`.

---

## 🔄 Factory Reset

To erase all settings and start the onboarding wizard again:

```bash
sudo systemctl stop adsbledmatrix
sudo rm /opt/adsbledmatrix/data/aircraft_db.sqlite3
sudo reboot
```

After reboot the `ADSB-Display-XXXX` hotspot will reappear. Connect to it and run through the setup wizard again.

---

## 🐛 Troubleshooting

### No aircraft showing

```bash
# Verify readsb is receiving data
sudo journalctl -u readsb -f

# Check SBS output stream
nc localhost 30003
# You should see MSG lines every few seconds

# Check application logs
sudo journalctl -u adsbledmatrix -f
```

### LED matrix is blank

```bash
# Ensure SPI is enabled
ls /dev/spi*
# Expected: /dev/spi0.0 and /dev/spi0.1

# Test matrix directly (uses the default P2 4-panel serpentine config)
python3 -c "
from rgbmatrix import RGBMatrix, RGBMatrixOptions
opts = RGBMatrixOptions()
opts.rows = 64
opts.cols = 128
opts.chain_length = 4
opts.parallel = 1
opts.hardware_mapping = 'regular'
opts.pixel_mapper_config = 'U-mapper'
opts.row_address_type = 3
opts.pwm_bits = 7
opts.brightness = 70
opts.gpio_slowdown = 4
RGBMatrix(options=opts).Fill(255, 0, 0)
"
```

### Web UI not loading

```bash
# Check service status
sudo systemctl status adsbledmatrix

# Test API health
curl http://localhost:8080/api/health
```

---

## 📜 License

MIT License — See [LICENSE](LICENSE) for details.

---

## 📚 Additional Documentation

- [Architecture Overview](docs/ARCHITECTURE.md)
- [Detailed Setup Guide](docs/SETUP.md)
