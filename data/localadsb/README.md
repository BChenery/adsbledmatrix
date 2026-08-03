# localadsb Databases

This folder contains aircraft/routing databases copied from the `localadsb` project
for use by the LED matrix ADSB display.

## Files

| File | Description |
|------|-------------|
| `aircraft_routes.db` | **Preferred** slim SQLite export: `aircraft_registry`, `aero_fleet`, `australian_registry`, `route_cache`. No live flight history (~13 MB vs ~50 MB full DB). |
| `flights.db` | Legacy full operational DB from localadsb (includes `flights` / `flight_tracks`). Kept only as a fallback while devices transition. |
| `aircraft.csv.gz` | Raw gzipped CSV source of the aircraft registry (hex, registration, type code, description). |
| `aircraft_type_names.json` | Lookup table mapping ICAO type codes (e.g. `A339`, `B38M`) to human-readable names (e.g. `Airbus A330-900neo`, `Boeing 737 MAX 8`). |
| `icao_aircraft_types.json` | ICAO aircraft type designators with technical descriptors (`desc` = L/S/H/etc., `wtc` = wake turbulence category). |
| `acars_routes.json` | Route cache derived from ACARS messages (callsign → origin/destination pairs). |

## Import

```bash
python3 scripts/import_localadsb.py
```

The importer prefers `aircraft_routes.db` and falls back to `flights.db` if the slim
file is not present.

## Quick queries

### List aircraft registry entries
```bash
sqlite3 aircraft_routes.db "SELECT hex_id, registration, aircraft_type, operator FROM aircraft_registry LIMIT 10;"
```

### Look up a human-readable type name
```python
import json
with open('aircraft_type_names.json') as f:
    names = json.load(f)
print(names.get('A339'))  # Airbus A330-900neo
```
