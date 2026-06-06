# ADS-B LED Aircraft Display

A complete consumer-facing ADS-B LED aircraft display system for Raspberry Pi 4.

## Features

- **Real-time ADS-B Reception**: Uses `readsb` with RTL-SDR to decode aircraft transponder signals
- **512×256 LED Matrix Display**: Shows closest aircraft with configurable layout
- **Web-Based Layout Designer**: Drag-and-drop interface to design what appears on the LED matrix
- **Onboarding Wizard**: First-boot setup for location, WiFi, and display preferences
- **Auto-Update**: Pulls software and aircraft database updates from GitHub
- **Multi-Aircraft Support**: Cycle between closest aircraft or show compact list view
- **Night Mode**: Automatically dim display during configured hours

## Hardware Requirements

- Raspberry Pi 4 (2GB+ recommended)
- RTL-SDR USB dongle (e.g., Nooelec NESDR Smart)
- 512×256 RGB LED matrix (4x 128×64 or 2x2 256×128 panels)
- LED matrix HAT or bonnet for Pi (e.g., Adafruit RGB Matrix Bonnet)
- 5V power supply (sufficient for Pi + LED matrix)
- MicroSD card (16GB+)

## Quick Start

```bash
# Flash Raspberry Pi OS to SD card, boot, then run:
curl -fsSL https://raw.githubusercontent.com/BChenery/adsbledmatrix/main/scripts/install.sh | sudo bash
```

After installation:
1. Connect to the `ADSB-Display-XXXX` WiFi network
2. Open http://192.168.4.1 in your browser
3. Follow the onboarding wizard to set your location
4. The display will immediately start showing nearby aircraft!

## Project Structure

```
adsbledmatrix/
├── backend/           # FastAPI + Python services
│   ├── app/
│   │   ├── main.py
│   │   ├── api/       # REST + WebSocket endpoints
│   │   ├── services/  # ADSB receiver, display engine, updater
│   │   └── static/    # React frontend build
├── frontend/          # React + TypeScript + Tailwind
│   └── src/
│       ├── components/
│       │   ├── LayoutDesigner/   # Canvas-based LED designer
│       │   ├── OnboardingWizard/ # First-boot setup
│       │   ├── Settings/         # Device configuration
│       │   └── LiveAircraft/     # Live aircraft view
├── hardware/          # LED matrix abstraction
├── data/              # SQLite DB, aircraft CSV, logos
├── scripts/           # Installation and update scripts
├── systemd/           # systemd service files
└── docs/              # Documentation
```

## Development

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

**One-command dev mode** — `npm run dev` starts **both** the backend (port 8000) and frontend (port 5173) automatically. The frontend proxies API requests to `localhost:8000`.

To run them separately:
```bash
npm run dev:backend   # Uvicorn on port 8000
npm run dev:frontend  # Vite on port 5173
```

## Configuration

Environment variables (prefix with `ADSB_`):

| Variable | Default | Description |
|----------|---------|-------------|
| `ADSB_DATA_DIR` | `./data` | Data directory path |
| `ADSB_READSB_HOST` | `127.0.0.1` | readsb TCP host |
| `ADSB_READSB_PORT` | `30003` | readsb SBS port |
| `ADSB_LED_MATRIX_BRIGHTNESS` | `100` | LED brightness (0-100) |
| `ADSB_GITHUB_REPO` | `BChenery/adsbledmatrix` | Update source repo |

## Updating

The device checks for updates daily. You can also trigger a manual update:

```bash
sudo bash /opt/adsbledmatrix/scripts/update.sh
```

Or via the web UI: **Settings → Updates → Check Now**

## License

MIT License - See LICENSE file for details.
