# ADS-B LED Aircraft Display

A complete, consumer-ready ADS-B aircraft display system for Raspberry Pi 4. Receives real-time aircraft transponder signals via RTL-SDR, decodes them with [`readsb`](https://github.com/wiedehopf/readsb), and renders the closest aircraft onto a configurable 512×256 RGB LED matrix — all controllable through a built-in web interface.

---

## ✨ Features

- **Real-Time ADS-B Reception** — Decodes 1090 MHz transponder signals using RTL-SDR + `readsb`
- **512×256 LED Matrix Display** — Shows the nearest aircraft with fully customizable layouts
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
| **Display** | RGB LED Matrix panels totalling 512×256 (e.g., four 128×64 panels) |
| **Driver** | LED Matrix HAT or Bonnet (e.g., Adafruit RGB Matrix Bonnet) |
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
- Clone this repository to `/opt/adsbledmatrix`
- Build the frontend and install Python dependencies
- Import the aircraft database
- Install and start the systemd services

### First Boot / Onboarding

1. After installation and reboot, the Pi creates a WiFi access point: **`ADSB-Display-XXXX`**
2. Connect to it with password: **`adsbsetup`**
3. Open **http://192.168.4.1** in your browser
4. Follow the wizard to set your latitude/longitude, choose a layout, and enter your home WiFi credentials
5. The Pi will restart and join your home network
6. Access the web UI at **http://adsb-display.local** (or your router's assigned IP)

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
| `ADSB_LED_MATRIX_PARALLEL` | `1` | Parallel chains |
| `ADSB_LED_MATRIX_BRIGHTNESS` | `100` | Brightness (0–100) |
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

# Test matrix directly
python3 -c "
from rgbmatrix import RGBMatrix, RGBMatrixOptions
opts = RGBMatrixOptions()
opts.rows = 64; opts.cols = 128; opts.chain_length = 4
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
