# System Architecture

## Overview

The ADS-B LED Display is a full-stack embedded system running on Raspberry Pi 4. It receives aircraft transponder signals via RTL-SDR, decodes them with `readsb`, enriches the data with a local SQLite aircraft database, and renders the closest aircraft onto a configurable 256×128 LED matrix (four P2 128×64 panels in a single serpentine HUB75 chain).

## Component Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        RASPBERRY PI 4                            │
│  ┌──────────┐      ┌──────────────┐      ┌──────────────────┐  │
│  │ RTL-SDR  │      │ 256×128 LED  │      │   PYTHON FASTAPI  │  │
│  │ Dongle   │─────▶│ Matrix (4×)  │◀─────│   BACKEND         │  │
│  └──────────┘      └──────────────┘      └──────────────────┘  │
│       │                                          │               │
│       │ USB                              ┌───────┴───────┐       │
│       ▼                                  │               │       │
│  ┌──────────┐                     ┌──────▼─────┐  ┌──────▼─────┐│
│  │ readsb   │                     │ ADSB       │  │ Display    ││
│  │ (daemon) │────────────────────▶│ Receiver   │  │ Engine     ││
│  │          │  TCP 30003 (SBS)    │ Service    │  │ (PIL +     ││
│  └──────────┘                     │            │  │  rpi-rgb-  ││
│                                   └──────┬─────┘  │  led-mtx)  ││
│                                          │         └────────────┘│
│                                   ┌──────▼─────┐                  │
│                                   │ Aircraft   │                  │
│                                   │ Database   │                  │
│                                   │ (SQLite)   │                  │
│                                   └────────────┘                  │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │              REACT FRONTEND (served via FastAPI)             │  │
│  │  ┌─────────────┐  ┌──────────────┐  ┌──────────────────┐   │  │
│  │  │ Layout      │  │ Onboarding   │  │ Settings / Live  │   │  │
│  │  │ Designer    │  │ Wizard       │  │ Aircraft View    │   │  │
│  │  └─────────────┘  └──────────────┘  └──────────────────┘   │  │
│  └─────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## Data Flow

1. **Signal Reception**: RTL-SDR receives 1090MHz radio signals from aircraft transponders
2. **Decoding**: `readsb` demodulates and decodes ADS-B messages, outputs SBS/BaseStation CSV format on TCP 30003
3. **Ingestion**: `ADSBReceiver` service maintains an in-memory dictionary of live aircraft, parsing incoming SBS lines
4. **Enrichment**: `AircraftDatabase` looks up hex codes in SQLite to get registration, type, operator info
5. **Geolocation**: Haversine formula calculates distance/bearing from user's configured lat/lon
6. **Selection**: Closest aircraft (or top N in cycle mode) is selected for display
7. **Rendering**: `DisplayEngine` rasterizes the active layout using PIL, then outputs to LED matrix
8. **Web UI**: FastAPI serves React app; WebSocket streams live aircraft data for preview

## Services

### ADSBReceiver (`backend/app/services/adsb_receiver.py`)
- Asyncio TCP client connecting to readsb
- Parses SBS/BaseStation MSG types 1-8
- Maintains `Dict[str, LiveAircraft]` with automatic stale cleanup
- Callback system for real-time updates

### DisplayEngine (`backend/app/services/display_engine.py`)
- 30 FPS render loop in separate asyncio task
- Builds PIL Image from layout elements
- Supports: text, data_field, image, shape, heading_arrow, vertical_rate, distance_bar, radar_blip
- Double-buffered output to LED matrix
- Idle/no-signal layouts with animated radar sweep

### AircraftDatabase (`backend/app/services/aircraft_db.py`)
- SQLite via SQLAlchemy async ORM
- CSV import for bulk aircraft data loading
- In-memory LRU cache for enrichment lookups

### Updater (`backend/app/services/updater.py`)
- Checks GitHub Releases API for new versions
- Downloads tarball, extracts over installation
- Runs database migrations
- systemd timer triggers daily at 3 AM + random delay

## Database Schema

### aircraft
| Column | Type | Description |
|--------|------|-------------|
| hex_code | TEXT PK | ICAO 24-bit address |
| registration | TEXT | Tail number |
| manufacturer | TEXT | Boeing, Airbus, etc. |
| model | TEXT | 737-800, A320, etc. |
| type_code | TEXT | ICAO type designator |
| operator | TEXT | Airline name |
| operator_icao | TEXT | Airline ICAO code |

### layouts
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Layout ID |
| name | TEXT | Display name |
| width | INTEGER | Canvas width (256) |
| height | INTEGER | Canvas height (128) |
| is_default | BOOLEAN | Pre-installed layout |

### layout_elements
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Element ID |
| layout_id | INTEGER FK | Parent layout |
| element_type | TEXT | Type enum |
| x, y, width, height | INTEGER | Geometry |
| z_index | INTEGER | Stacking order |
| color, bg_color | TEXT | Hex colors |
| format_str | TEXT | Python format string |
| data_field | TEXT | Bound field name |
| show_if | TEXT | Visibility condition |

### user_config
Single-row configuration table storing all user preferences.

## LED Matrix Configuration

The system uses `rpi-rgb-led-matrix` Python bindings. The default build is a 256×128 display made from four P2 128×64 panels wired in a single serpentine HUB75 chain:

```bash
ADSB_LED_MATRIX_ROWS=64
ADSB_LED_MATRIX_COLS=128
ADSB_LED_MATRIX_CHAIN=4
ADSB_LED_MATRIX_PARALLEL=1
ADSB_LED_MATRIX_HARDWARE_MAPPING=regular
ADSB_LED_MATRIX_PIXEL_MAPPER=U-mapper
ADSB_LED_MATRIX_ROW_ADDRESS_TYPE=3
ADSB_LED_MATRIX_PWM_BITS=7
ADSB_LED_MATRIX_BRIGHTNESS=70
ADSB_LED_MATRIX_GPIO_SLOWDOWN=4
```

## Update Mechanism

1. `adsbledmatrix-update.timer` triggers daily
2. `adsbledmatrix-update.service` runs Python check
3. Compares local `VERSION` with GitHub latest release tag
4. If newer: download tarball → verify → extract → backup old version
5. Re-import `data/aircraft_db.csv` from repo
6. Restart `adsbledmatrix.service`

Rollback: Previous version preserved in `/opt/adsbledmatrix-backup/`

## Security Considerations

- All configuration stays local (no cloud required)
- WiFi password stored in SQLite (plaintext - encryption TBD)
- Local network access only (port 8080)
- No external APIs required for core functionality
- Airline logos downloaded on-demand and cached locally
