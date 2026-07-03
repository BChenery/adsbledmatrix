# Design: Add BC Layout to Defaults and Make It the Default

## Context

A custom layout named **BC** has been created on the production Raspberry Pi (`10.0.0.139`). It is currently stored in the runtime database (`/opt/adsbledmatrix/data/aircraft_db.sqlite3`, layout id `14`) but is not part of the shipped default layouts, nor is it the active default.

The goal is to:
1. Add the BC layout to the standard/default layout list shipped with the application.
2. Make BC the default active layout for new and existing installs.

## Current behaviour

- Default layouts live in `data/default_layouts.json` and are merged into the DB on every startup in `backend/app/lifespan.py`.
- Each layout has an `is_default` boolean field in the JSON schema, but the startup logic ignores it.
- `lifespan.py` selects the active layout by picking the first non-idle layout in the JSON list.
- The current default is therefore implicitly the first layout in the file (`Aviation Enthusiast`).

## Proposed changes

### 1. Add BC to `data/default_layouts.json`

Insert a cleaned copy of the BC layout (exported from the Pi database) into the standard list. Clean-up steps:
- Remove runtime-only fields: `id`, `layout_id`, `created_at`, `updated_at`.
- Remove `null`/default fields that are not part of the canonical default layout schema (e.g. `font_family`, `bg_color`, `image_path`, `image_url`, `range_km`, radar colours/show flags when irrelevant).
- Map the DB column `format` back to `format_str`.
- Set `is_default: true`.

### 2. Update other layouts

Set `is_default: false` on every other layout in `data/default_layouts.json`.

### 3. Respect `is_default` in startup logic

Update `backend/app/lifespan.py` so that, when no active layout is configured in `user_config`, it chooses the layout whose `is_default` flag is `true`. Maintain the existing fallback (first non-idle layout) if no layout is marked default.

### 4. Update the Pi

- Replace `/opt/adsbledmatrix/data/default_layouts.json` with the updated file.
- Update the `user_config` table so `active_layout_id` points to the BC layout (`id = 14`).
- Restart the adsbledmatrix service so the merge logic applies the change and the display engine loads BC.

## Verification

- `scripts/validate_layouts.py` must pass for the updated `data/default_layouts.json`.
- `pytest backend/tests/test_layouts.py::test_default_layouts_validate` must pass.
- After restarting the Pi service, querying `/api/layouts` should show BC with `is_default: true`, and the LED matrix should render BC.

## Scope / non-goals

- No changes to the layout designer, API schemas, or frontend.
- No changes to the idle layout selection logic.
- No renaming of the BC layout; it is kept exactly as named by the user.
