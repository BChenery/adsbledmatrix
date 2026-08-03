# localadsb Databases

Core aircraft/routing data copied from the `localadsb` project for the LED matrix.

## Files

| File | Description |
|------|-------------|
| `aircraft_routes.db` | **Core** localadsb DB: `aircraft_registry`, `aero_fleet`, `australian_registry`, `route_cache`. This is the source of truth (not the capture log). |
| `aircraft.csv.gz` | Optional gzipped CSV of the aircraft registry. |
| `aircraft_type_names.json` | ICAO type code → human-readable name (e.g. `A339` → `Airbus A330-900neo`). |
| `icao_aircraft_types.json` | ICAO type designators with technical descriptors. |
| `acars_routes.json` | Optional ACARS-derived routes. |

`flights.db` is **not** used here. In localadsb that file is capture-log only.

## Import

```bash
python3 scripts/import_localadsb.py
```

## Quick queries

```bash
sqlite3 aircraft_routes.db "SELECT hex_id, registration, aircraft_type, operator FROM aircraft_registry LIMIT 10;"
```
