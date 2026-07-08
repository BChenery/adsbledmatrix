# Proximity Focus, Cycle Count & Layout Variety — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let Settings control (1) auto-focus on aircraft within a distance threshold, (2) how many nearest aircraft to cycle, and (3) multi-layout rotation for variety.

**Architecture:** Add config fields on `UserConfig`, expose them via `/api/config`, implement pure selection logic used by `DisplayEngine`, and extend the Settings Display section UI. Spec: `docs/superpowers/specs/2026-07-09-proximity-focus-and-display-variety-design.md`.

**Tech Stack:** Python 3 / FastAPI / SQLAlchemy, React 18 / TypeScript / Tailwind / shadcn, pytest, Vitest.

---

## File Structure

| File | Responsibility |
|---|---|
| `backend/app/models.py` | New `UserConfig` columns |
| `backend/app/api/config.py` | Config schemas, validation, engine reload hooks |
| `backend/app/services/display_selection.py` | Pure aircraft/layout selection (unit-testable) |
| `backend/app/services/display_engine.py` | Call selection helper; layout playlist state |
| `backend/tests/test_display_selection.py` | Selection priority tests |
| `frontend/src/types/config.ts` | TypeScript config fields |
| `frontend/src/components/Settings/Settings.tsx` | Display controls UI |
| `frontend/src/components/Settings/Settings.test.tsx` | UI tests for new controls |

---

## Task 1: Data model + config API

**Files:**
- Modify: `backend/app/models.py`
- Modify: `backend/app/api/config.py`
- Ensure schema bootstrap (same path as previous additive columns) creates the new columns on existing SQLite DBs

- [ ] **Step 1: Add columns to `UserConfig`**

```python
cycle_count = Column(Integer, nullable=False, default=3, server_default=text("3"))
proximity_focus_enabled = Column(Boolean, nullable=False, default=False, server_default=text("0"))
proximity_focus_km = Column(Float, nullable=False, default=3.0, server_default=text("3.0"))
proximity_focus_layout_id = Column(Integer, ForeignKey("layouts.id"), nullable=True)
layout_rotation_enabled = Column(Boolean, nullable=False, default=False, server_default=text("0"))
layout_playlist_ids = Column(JSON, nullable=False, default=list, server_default=text("'[]'"))
layout_rotation_interval_sec = Column(Integer, nullable=False, default=30, server_default=text("30"))
```

Add relationship for `proximity_focus_layout` if useful (optional).

- [ ] **Step 2: Extend `ConfigResponse` / `ConfigUpdate`**

Include all new fields. Add validators:

- `cycle_count` 1–10
- `proximity_focus_km` 0.1–50
- `layout_rotation_interval_sec` 5–600
- `display_mode` in `closest`, `cycle`, `cycle3`, `list` (accept `cycle3` as alias)

- [ ] **Step 3: On config PUT, reload engine layouts when playlist/focus layout changes**

Extend the existing block that reloads layouts on `active_layout_id` / `idle_layout_id` changes to also react to `layout_playlist_ids`, `layout_rotation_enabled`, `proximity_focus_layout_id`.

- [ ] **Step 4: Schema ensure for existing DBs**

If the project uses runtime `ALTER TABLE` helpers, add the new columns the same way as `receiver_source`. Verify with a quick local boot or unit test that defaults apply.

- [ ] **Step 5: Commit**

```bash
git add backend/app/models.py backend/app/api/config.py
git commit -m "feat(config): add proximity focus, cycle count, layout playlist fields"
```

---

## Task 2: Pure display selection helper

**Files:**
- Create: `backend/app/services/display_selection.py`
- Create: `backend/tests/test_display_selection.py`

- [ ] **Step 1: Implement selection helper**

```python
# backend/app/services/display_selection.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, List, Optional, Sequence


FOCUS_POOL_CAP = 20
EXIT_HYSTERESIS = 1.15


@dataclass
class SelectionResult:
    aircraft: Any
    mode: str  # "proximity" | "closest" | "cycle" | "list"
    cycle_index: int
    focused: bool
    exit_threshold_km: float


def normalize_display_mode(mode: Optional[str]) -> str:
    if mode in (None, ""):
        return "closest"
    if mode == "cycle3":
        return "cycle"
    return mode


def select_aircraft(
    focus_pool: Sequence[Any],
    *,
    display_mode: str,
    cycle_count: int,
    cycle_index: int,
    proximity_enabled: bool,
    proximity_km: float,
    currently_focused: bool = False,
) -> SelectionResult:
    """Pick which aircraft to show.

    ``focus_pool`` must be ordered nearest-first (as from get_closest).
    """
    mode = normalize_display_mode(display_mode)
    n = max(1, min(int(cycle_count or 3), 10))
    pool = list(focus_pool)[:FOCUS_POOL_CAP]
    cycle_pool = pool[:n] if pool else []

    threshold = float(proximity_km or 3.0)
    exit_threshold = threshold * EXIT_HYSTERESIS if currently_focused else threshold

    if proximity_enabled and pool:
        in_zone = [
            ac for ac in pool
            if getattr(ac, "distance_km", None) is not None
            and ac.distance_km <= exit_threshold
        ]
        if in_zone:
            aircraft = min(in_zone, key=lambda a: a.distance_km)
            return SelectionResult(
                aircraft=aircraft,
                mode="proximity",
                cycle_index=cycle_index,
                focused=True,
                exit_threshold_km=exit_threshold,
            )

    if not cycle_pool:
        return SelectionResult(
            aircraft=None,
            mode=mode,
            cycle_index=0,
            focused=False,
            exit_threshold_km=threshold,
        )

    if mode == "cycle":
        idx = cycle_index % len(cycle_pool)
        return SelectionResult(
            aircraft=cycle_pool[idx],
            mode="cycle",
            cycle_index=idx,
            focused=False,
            exit_threshold_km=threshold,
        )

    # closest and list both pin primary to nearest
    return SelectionResult(
        aircraft=cycle_pool[0],
        mode=mode if mode in ("closest", "list") else "closest",
        cycle_index=0,
        focused=False,
        exit_threshold_km=threshold,
    )


def select_layout_index(
    playlist_len: int,
    *,
    rotation_enabled: bool,
    current_index: int,
    advance: bool,
) -> int:
    if not rotation_enabled or playlist_len <= 0:
        return 0
    if advance:
        return (current_index + 1) % playlist_len
    return current_index % playlist_len
```

- [ ] **Step 2: Write tests**

Cover at minimum:

1. `cycle3` normalizes to `cycle`
2. Cycle uses only first N of pool
3. Proximity overrides cycle when aircraft inside threshold
4. Proximity does not fire when outside threshold
5. Hysteresis keeps focus slightly past threshold when `currently_focused=True`
6. Closest always returns index 0
7. Empty pool returns `aircraft=None`

- [ ] **Step 3: Run tests**

```bash
cd backend && python -m pytest tests/test_display_selection.py -q
```

Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/display_selection.py backend/tests/test_display_selection.py
git commit -m "feat(display): add pure aircraft selection helper with proximity override"
```

---

## Task 3: Wire selection into `DisplayEngine`

**Files:**
- Modify: `backend/app/services/display_engine.py`
- Modify: `backend/tests/test_display_engine.py` (add cases if practical)

- [ ] **Step 1: Add engine state**

```python
self._layout_index = 0
self._layout_time = datetime.utcnow()
self._proximity_focused = False
self._playlist_layouts: list = []
self._focus_layout = None
```

- [ ] **Step 2: Extend `set_layout` (or add `set_display_layouts`)**

Accept active, idle, optional focus layout, optional playlist list. Cache on the engine.

- [ ] **Step 3: Replace hard-coded cycle-3 path in `_render_frame`**

Pseudocode:

```python
user_config = get_user_config_sync()
cycle_count = getattr(user_config, "cycle_count", 3) if user_config else 3
focus_pool = receiver.get_closest(n=max(cycle_count, 20))
# advance cycle timer only when not proximity-focused
# call select_aircraft(...)
# resolve layout:
#   if result.focused and self._focus_layout: layout = self._focus_layout
#   elif layout_rotation_enabled and playlist: layout = playlist[select_layout_index(...)]
#   else: layout = self._current_layout
# pause layout rotation advance while focused
self._proximity_focused = result.focused
```

Keep list-mode row fetching using existing `get_closest` for list elements (already uses `max_rows`).

- [ ] **Step 4: Run existing + new tests**

```bash
cd backend && python -m pytest tests/test_display_engine.py tests/test_display_selection.py -q
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/display_engine.py backend/tests/test_display_engine.py
git commit -m "feat(display): proximity focus, cycle_count, and layout playlist in engine"
```

---

## Task 4: Frontend types + Settings UI

**Files:**
- Modify: `frontend/src/types/config.ts`
- Modify: `frontend/src/components/Settings/Settings.tsx`
- Modify: `frontend/src/components/Settings/Settings.test.tsx`

- [ ] **Step 1: Extend `UserConfig`**

```ts
cycle_count: number;
proximity_focus_enabled: boolean;
proximity_focus_km: number;
proximity_focus_layout_id?: number | null;
layout_rotation_enabled: boolean;
layout_playlist_ids: number[];
layout_rotation_interval_sec: number;
```

Update Settings test mock config with the same defaults.

- [ ] **Step 2: Display mode options**

```tsx
<SelectItem value="closest">Closest aircraft only</SelectItem>
<SelectItem value="cycle">Cycle nearest aircraft</SelectItem>
<SelectItem value="list">Show list of nearby aircraft</SelectItem>
```

Map legacy `cycle3` → show as `cycle` when loading (`value={config.display_mode === 'cycle3' ? 'cycle' : config.display_mode}`).

- [ ] **Step 3: Cycle count control**

When mode is cycle:

- Number input `cycle_count` min 1 max 10
- Existing interval input

Helper text uses `Math.min(config.cycle_count, aircraft.length)`.

- [ ] **Step 4: Proximity focus controls**

- Switch for `proximity_focus_enabled`
- When on: distance input in current `distance_unit` (convert to/from km on change)
- Optional `LayoutPicker` single-select for `proximity_focus_layout_id` with a “Use current layout” clear option

Conversion helpers (inline is fine):

```ts
const KM_PER_MI = 1.60934;
function kmToDisplay(km: number, unit: string) {
  return unit === 'mi' ? km / KM_PER_MI : km;
}
function displayToKm(value: number, unit: string) {
  return unit === 'mi' ? value * KM_PER_MI : value;
}
```

- [ ] **Step 5: Layout variety controls**

- Switch `layout_rotation_enabled`
- Off: existing single aircraft layout picker → `active_layout_id`
- On:
  - Multi-select layout cards (click toggles membership in `layout_playlist_ids`; preserve order of first selection)
  - Interval input for `layout_rotation_interval_sec`
  - On save path / update: keep `active_layout_id` synced to `layout_playlist_ids[0]` when rotation is on and playlist non-empty

Extend `LayoutPicker` with optional `multi` / `selectedIds` / `onToggle` props **or** add a small `LayoutPlaylistPicker` sibling to avoid breaking single-select call sites (idle + focus).

- [ ] **Step 6: Tests**

- Mock config includes new fields
- Assert “Cycle nearest” option exists
- With `display_mode: 'cycle'`, cycle count control is present
- With `proximity_focus_enabled: true`, threshold control is present

- [ ] **Step 7: Run frontend tests**

```bash
cd frontend && npm test -- --run src/components/Settings/Settings.test.tsx
```

- [ ] **Step 8: Commit**

```bash
git add frontend/src/types/config.ts frontend/src/components/Settings/Settings.tsx frontend/src/components/Settings/Settings.test.tsx
git commit -m "feat(settings): proximity focus, cycle count, and layout variety controls"
```

---

## Task 5: End-to-end verification

- [ ] **Step 1: Manual checklist**

1. Settings → Display → Cycle mode, set count=5, interval=3s → matrix cycles up to 5 nearest.
2. Enable proximity at ~2 km (or 1.2 mi) → aircraft inside threshold locks on; outside returns to cycle.
3. Optional focus layout → only used while locked.
4. Enable layout rotation with 2+ layouts → switches on interval; pauses during proximity if focus layout set.
5. Reload Settings → values persist.
6. Legacy `cycle3` in DB still works (shows as cycle).

- [ ] **Step 2: Full test suite (project defaults)**

```bash
cd backend && python -m pytest -q
cd frontend && npm test -- --run
```

- [ ] **Step 3: Final commit if any polish**

```bash
git commit -m "test: cover proximity focus and display variety settings"
```

---

## Implementation Notes

- Always store distance in **km** on the backend; convert only in the UI.
- Focus pool cap is 20; cycle pool is the first `cycle_count` of that list.
- Do not advance `cycle_index` while proximity-focused (avoids jumping after release).
- Do not advance layout playlist while proximity-focused if a dedicated focus layout is active; if no focus layout, keeping rotation running is acceptable but pausing is simpler — **pause always while focused**.
- Filter missing playlist layout IDs at render time rather than failing hard.

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-07-09-proximity-focus-and-display-variety.md`.**

Spec: `docs/superpowers/specs/2026-07-09-proximity-focus-and-display-variety-design.md`.

Suggested order: Task 1 → Task 2 → Task 3 → Task 4 → Task 5.
