# localadsb Databases

This folder contains aircraft/routing databases copied from the `localadsb` project
for use by the LED matrix ADSB display.

## Files

| File | Description |
|------|-------------|
| `flights.db` | SQLite database with the main **aircraft registry**. Table `aircraft_registry` maps ICAO 24-bit hex codes to registration, aircraft type code, operator/airline, and seen counts. |
| `aircraft.csv.gz` | Raw gzipped CSV source of the aircraft registry (hex, registration, type code, description). |
| `aircraft_type_names.json` | Lookup table mapping ICAO type codes (e.g. `A339`, `B38M`) to human-readable names (e.g. `Airbus A330-900neo`, `Boeing 737 MAX 8`). |
| `icao_aircraft_types.json` | ICAO aircraft type designators with technical descriptors (`desc` = L/S/H/etc., `wtc` = wake turbulence category). |
| `acars_routes.json` | Route cache derived from ACARS messages (callsign → origin/destination pairs). |

## Quick queries

### List aircraft registry entries
```bash
sqlite3 flights.db "SELECT hex_id, registration, aircraft_type, operator FROM aircraft_registry LIMIT 10;"
```

### Look up a human-readable type name
```python
import json
with open('aircraft_type_names.json') as f:
    names = json.load(f)
print(names.get('A339'))  # Airbus A330-900neo
```
