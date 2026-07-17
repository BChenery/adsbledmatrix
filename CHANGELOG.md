# Changelog

All notable user-facing changes to ADS-B LED Display.

The format is based on [Keep a Changelog](https://keepachangelog.com/).
Versions follow the `VERSION` file and GitHub releases.

## [0.1.48] - 2026-07-18

### Fixed
- Fresh install and OTA now **require** a full aircraft/route import from localadsb (`flights.db`); install aborts if enrichment data is missing or too small (no more callsign-only devices with ~65 aircraft)
- Network SBS receiver no longer dies or blocks **Save** when switching receiver host/port
- Local RTL-SDR `readsb` can start/stop again after the LED stack drops privileges to `adsb`
- Route lookups no longer permanently cache “not found”, so new routes appear after a data sync without a process restart

### Changed
- Production layouts from the field Pi are now the shipped defaults (including Radar); design-system palette/safe-margin checks relaxed for designer-customized layouts
- Heading arrow in the designer preview rotates with aircraft heading, scales with box size, and has an **Arrow Size** control

## [0.1.40] - 2026-07-15

### Added
- Layout designer **Apply** action to push a layout to the matrix without permanently saving it
- Text on the designer canvas now clips the same way it does on the LED matrix

## [0.1.39] - 2026-07-14

### Fixed
- Interesting-aircraft yellow flash alerts wait until the local baseline is ready (no early false alarms)

## [0.1.38] - 2026-07-14

### Added
- **Interesting aircraft** alerts driven by your local sighting history (rare visitors, long absences)
- Warm-up period so the device can learn “normal” traffic before rarity alerts fire
- Settings for alert range, rarity thresholds, hold time, and optional dedicated layout

## [0.1.37] - 2026-07-13

### Changed
- You can delete custom layouts, as long as at least one layout always remains

## [0.1.36] - 2026-07-12

### Changed
- Product web UI restyled to match the marketing design system (dark LED aesthetic, clearer navigation)

## [0.1.35] - 2026-07-11

### Fixed
- Night mode and sleep windows apply more reliably in the configured timezone
- Layout save and rename now persist correctly

## [0.1.34] - 2026-07-10

### Fixed
- Manual **Trigger update** from Settings works without interactive sudo on the Pi

## [0.1.33] - 2026-07-09

### Fixed
- Idle layout clock uses your configured local timezone

## [0.1.32] - 2026-07-08

### Fixed
- Settings shows real update progress instead of a stale “100% complete” state

## [0.1.31] - 2026-07-07

### Added
- Map preview for receiver coordinates in Settings

## [0.1.30] - 2026-07-06

### Fixed
- Update health checks and safer rollback that preserves the Python virtualenv

## [0.1.29] - 2026-07-05

### Added
- **Proximity focus** — lock onto very close aircraft with optional layout override
- Configurable aircraft **cycle count**
- **Layout playlist** rotation for more variety on the matrix

## [0.1.28] - 2026-07-03

### Fixed
- Update scripts no longer exit early when optional `.env` settings are missing

## [0.1.27] - 2026-07-02

### Changed
- Settings page reorganized: clearer Status, Display, and System sections
- More responsive layout pickers and form grids on phones

## [0.1.26] - 2026-07-01

### Fixed
- Update scripts tolerate missing rollout or progress files without failing the whole update

## [0.1.25] - 2026-06-30

### Fixed
- Airline logo fringe/colour dots cleaned up on the LED matrix (alpha threshold)

## [0.1.24] - 2026-06-29

### Fixed
- Sleep and dim windows are timezone-aware
- Clearer progress feedback while an update runs

## [0.1.23] - 2026-06-28

### Fixed
- Aircraft / route database sync re-imports when the DB is missing or stale

## [0.1.22] - 2026-06-27

### Fixed
- Updates fix install-directory ownership before pulling new software

## Earlier

### Added
- Real-time ADS-B reception with RTL-SDR + `readsb`
- 256×128 LED matrix display with visual layout designer
- Onboarding wizard and WiFi captive portal
- Local aircraft database, airline logos, and route enrichment
- Night mode, multi-aircraft cycling, and live web preview
- Auto-update via GitHub releases
