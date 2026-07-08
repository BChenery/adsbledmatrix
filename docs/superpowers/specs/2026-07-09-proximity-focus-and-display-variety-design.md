# Proximity Focus, Cycle Count & Layout Variety

## Goal

Improve Display settings so the LED matrix can:

1. **Proximity focus** — automatically lock onto an aircraft when it comes within a user-specified distance (close enough that the user can hear it), interrupting normal cycling.
2. **Configurable cycle size** — let the user choose how many nearest aircraft to rotate through (not hard-coded to 3).
3. **Layout variety** — rotate through multiple aircraft layouts so the display has visual variety instead of a single static layout.

## Background

Today (`display_engine.py` + Settings Display section):

| Behaviour | Current state |
|---|---|
| Display modes | `closest`, `cycle3`, `list` |
| Cycle pool size | Hard-coded to 3 (`get_closest(n=3)`, `min(3, len(closest))`) |
| Layouts | Single `active_layout_id` + single `idle_layout_id` |
| Close approach | No special handling — a nearby aircraft only appears if it is the closest (or happens to be the current cycle slot) |

Users watching the matrix want distant traffic to keep cycling for interest, but when something flies close/overhead the display should snap to that aircraft without manual intervention.

## Scope

- Persist new config fields on `UserConfig`.
- Extend Settings → Display UI for the new controls.
- Update `DisplayEngine._render_frame` selection logic for proximity override, N-aircraft cycle, and multi-layout rotation.
- Keep `closest` / `list` modes working; treat `cycle3` as a legacy alias of the new cycle mode.
- Unit tests for selection priority and config API; Settings UI helper text updates.

## Non-Goals

- Altitude- or track-based “overhead” detection (distance-only for v1).
- Audio / microphone integration.
- Per-layout cycle interval or per-mode layout pools.
- Changing how list layouts render rows (`aircraft_list` element stays as-is).
- Multi-aircraft simultaneous full-detail layouts beyond existing list elements.

## Chosen Approach

**Distance-threshold override + generalised cycle + layout playlist.**

Priority when aircraft are present (highest first):

1. **Proximity focus** (if enabled and at least one aircraft is within threshold) → show the **closest** aircraft inside the threshold. Optionally use a dedicated “focus” layout if configured; otherwise use the normal active layout (or current playlist layout).
2. **Normal display mode** (`closest` / `cycle` / `list`) using the configured cycle pool size.
3. **Idle** when no aircraft.

Layout variety runs independently of aircraft selection: while showing aircraft (and not forced to a single focus layout), the engine advances through a user-selected **layout playlist** on its own interval.

## Detailed Design

### 1. Data Model (`UserConfig`)

| Column | Type | Default | Notes |
|---|---|---|---|
| `cycle_count` | `INTEGER` | `3` | How many nearest aircraft to consider in cycle mode. Clamp 1–10. |
| `proximity_focus_enabled` | `BOOLEAN` | `false` | Master switch for close-approach override. |
| `proximity_focus_km` | `FLOAT` | `3.0` | Distance threshold in **kilometres** (stored in km; UI converts with `distance_unit`). Clamp 0.1–50. |
| `proximity_focus_layout_id` | `INTEGER` FK → layouts | `NULL` | Optional layout used only while proximity focus is active. `NULL` = use current active/playlist layout. |
| `layout_rotation_enabled` | `BOOLEAN` | `false` | When true, rotate through `layout_playlist_ids` instead of only `active_layout_id`. |
| `layout_playlist_ids` | `JSON` | `[]` | Ordered list of layout IDs. Empty or single entry behaves like fixed layout. |
| `layout_rotation_interval_sec` | `INTEGER` | `30` | Seconds between layout switches. Clamp 5–600. |

**Backwards compatibility**

- `display_mode = "cycle3"` remains accepted and is treated as `"cycle"`.
- Settings UI writes `"cycle"` going forward.
- Existing installs with only `active_layout_id` keep current behaviour (`layout_rotation_enabled=false`).

SQLite column adds follow the project’s existing pattern (SQLAlchemy models + startup/`CREATE TABLE`/nullable defaults as used for `receiver_source` etc.). Prefer additive columns with server defaults so existing DBs upgrade cleanly.

### 2. Selection Logic (`DisplayEngine`)

Replace the hard-coded `n=3` path with:

```text
n = clamp(user_config.cycle_count or 3, 1, 10)
candidates = receiver.get_closest(n=max(n, 1))   # still need enough for list/focus
# For list mode, keep fetching enough rows for the layout (existing max_rows path).

if proximity_focus_enabled and candidates:
    threshold = proximity_focus_km  # always km internally
    in_zone = [ac for ac in candidates if ac.distance_km is not None and ac.distance_km <= threshold]
    # Prefer full nearest list for focus: get_closest may need n larger than cycle_count
    # so focus can see a close aircraft that is outside the cycle pool.
```

**Important:** Proximity focus must query a **focus pool** large enough to notice close aircraft that are not among the N cycled (e.g. cycle 3 nearest for variety, but a 4th aircraft at 1 km should still steal focus). Use:

```text
focus_pool = receiver.get_closest(n=max(cycle_count, 10))  # or a fixed cap e.g. 20
cycle_pool = focus_pool[:cycle_count]
```

Then:

```text
if proximity_focus_enabled:
    in_zone = [ac for ac in focus_pool if ac.distance_km <= threshold]
    if in_zone:
        aircraft = min(in_zone, key=distance)  # closest in zone
        layout = focus_layout or current_playlist_layout
        # freeze cycle index advancement while focused (optional but recommended)
        return render(aircraft, layout)

# else normal modes
if mode in ("closest",):
    aircraft = cycle_pool[0]
elif mode in ("cycle", "cycle3"):
    advance cycle_index on interval over len(cycle_pool)
    aircraft = cycle_pool[idx]
elif mode == "list":
    aircraft = cycle_pool[0]  # primary; list element uses its own rows
```

**Hysteresis (recommended, small):** To avoid flicker at the threshold boundary, once focused, keep focus until the aircraft exceeds `threshold * 1.15` (or `threshold + 0.5 km`, whichever is simpler). Document the chosen rule in code comments only if needed; default: simple hard threshold for v1 is acceptable if tests stay simple — prefer **+15% exit hysteresis** for polish.

**Layout rotation**

Engine state:

- `_layout_index: int`
- `_layout_time: datetime`

On each frame when not idle and (`layout_rotation_enabled` and playlist non-empty):

1. Resolve playlist to loaded `Layout` objects (cache IDs → layouts; fall back to `active_layout` if an ID is missing).
2. If interval elapsed, advance `_layout_index`.
3. Use `playlist[index]` as the aircraft layout.

When proximity focus has a dedicated `proximity_focus_layout_id`, **pause** layout rotation while focused (resume index afterward so variety continues).

When playlist is empty or rotation disabled, use `active_layout_id` as today.

`engine.set_layout(active, idle)` should also accept playlist resolution (reload on config change via existing config PUT path).

### 3. Config API

Extend `ConfigResponse` / `ConfigUpdate` in `backend/app/api/config.py` and frontend `UserConfig` type with the new fields.

Validators:

- `cycle_count` ∈ [1, 10]
- `proximity_focus_km` ∈ [0.1, 50]
- `layout_rotation_interval_sec` ∈ [5, 600]
- `display_mode` ∈ {`closest`, `cycle`, `cycle3`, `list`} (normalize `cycle3` → `cycle` on write optional)
- `layout_playlist_ids`: list of positive ints; unknown IDs filtered or rejected with 422 — **filter + log** is friendlier for deleted layouts
- `proximity_focus_layout_id` must exist if set

On PUT that changes layout fields, refresh engine layouts (extend existing `active_layout_id` / `idle_layout_id` notification to include playlist + focus layout).

### 4. Settings UI (Display section)

Insert controls under **When aircraft are detected**, after mode + cycle interval:

1. **Display mode** options:
   - Closest aircraft only
   - Cycle nearest aircraft (was “Cycle up to 3…”)
   - Show list of nearby aircraft

2. When mode is cycle:
   - **Number of aircraft to cycle** — number input 1–10 (default 3)
   - **Switch aircraft every** — existing `cycle_interval_sec`

3. **Proximity focus** subsection (always visible under behaviour):
   - Toggle: “Highlight aircraft when they get close”
   - When on:
     - Distance threshold (number + unit label from `distance_unit`: km or mi; convert on save/load)
     - Optional layout picker: “Focus layout (optional)” — none = keep current layout
   - Helper: “When an aircraft is within this distance, the display locks onto it so you can identify what you hear.”

4. **Layout variety** subsection (replaces single aircraft layout picker behaviour when rotation on):
   - Toggle: “Rotate layouts for variety”
   - When off: existing single **Aircraft layout** picker → `active_layout_id`
   - When on:
     - Multi-select / multi-toggle grid of layouts (reuse `LayoutPicker` pattern with multi-select)
     - Order = selection order or explicit up/down controls (v1: selection order from clicks is fine; store array)
     - Interval seconds input
     - `active_layout_id` remains first playlist entry or last primary for API compatibility (set `active_layout_id` to playlist[0] when saving rotation on)

5. Idle layout picker unchanged.

Helper text must update dynamically with live `aircraft.length` and configured `cycle_count` / threshold.

### 5. Units

- Store `proximity_focus_km` always in kilometres (same as `distance_km` on live aircraft).
- Settings UI: if `distance_unit === 'mi'`, show miles and convert: `km = mi * 1.60934`, `mi = km / 1.60934` (match any existing conversion helpers if present).

### 6. Onboarding

Out of scope for the main path; optional follow-up to mention proximity focus. Do not break existing onboarding defaults (`display_mode`, layouts).

## Edge Cases

| Case | Behaviour |
|---|---|
| Proximity on, no aircraft in zone | Normal mode |
| Multiple aircraft in zone | Closest in zone wins |
| Cycle count 1 | Same as closest, unless proximity steals focus |
| Playlist has deleted layout ID | Skip missing IDs; if none left, fall back to `active_layout_id` |
| List mode + proximity | Proximity still overrides to single-aircraft focus layout/detail; when released, return to list |
| Idle | No proximity; idle layout only |
| Threshold 0 / invalid | Reject on API; UI min 0.1 km (or 0.1 mi converted) |

## Testing

**Backend**

- Unit tests for a pure helper e.g. `select_display_target(candidates, config, cycle_index, focused_hex)` covering:
  - closest / cycle / list selection with variable `cycle_count`
  - proximity override when inside threshold
  - no override when outside
  - hysteresis if implemented
  - `cycle3` alias
- Config API accepts new fields and rejects out-of-range values.
- Display engine integration test with mocked receiver returning ordered aircraft.

**Frontend**

- Settings test: cycle count visible in cycle mode; proximity controls when toggle on; layout multi-select when rotation on (mock config).

**Manual**

1. Cycle 5 aircraft @ 5s; confirm rotation among 5 nearest.
2. Enable proximity at 2 km; fly (or inject) aircraft inside/outside threshold; confirm lock/release.
3. Enable layout rotation with 2–3 layouts; confirm interval switches.
4. Proximity + focus layout: confirm dedicated layout while close.
5. Save/reload page; settings persist.

## File Touch List

| File | Change |
|---|---|
| `backend/app/models.py` | New `UserConfig` columns |
| `backend/app/api/config.py` | Schemas, validation, engine refresh |
| `backend/app/services/display_engine.py` | Selection + layout playlist |
| `backend/app/services/display_selection.py` (new, optional) | Pure selection helper for testability |
| `backend/tests/test_display_selection.py` (new) | Selection unit tests |
| `backend/tests/test_display_engine.py` | Engine-level cases if needed |
| `frontend/src/types/config.ts` | New fields |
| `frontend/src/components/Settings/Settings.tsx` | UI controls |
| `frontend/src/components/Settings/Settings.test.tsx` | Coverage for new controls |
| DB bootstrap / schema ensure path (wherever columns are added today) | Additive migration |

## Open Decisions (defaults for implementation)

Resolved for this plan unless product overrides later:

1. Proximity threshold stored in **km**.
2. Focus pool cap **20** nearest for zone check.
3. Exit hysteresis **15%** above threshold.
4. Layout rotation **pauses** during proximity focus.
5. `display_mode` value **`cycle`** replaces UI label for `cycle3`; both accepted by backend.
