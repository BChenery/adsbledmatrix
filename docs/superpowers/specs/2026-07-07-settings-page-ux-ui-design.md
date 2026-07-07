# Settings Page UX/UI Redesign

## Problem Statement

The current Settings page (`frontend/src/components/Settings/Settings.tsx`) renders as a single, full-width vertical stack of cards. On large screens this creates excessive blank space and makes the page feel unfinished. On small screens the same flat stack becomes a long, undifferentiated scroll of controls with inconsistent density and no clear grouping.

Goals:
- Eliminate the "blown out" wide layout on desktop.
- Give the page a clear visual hierarchy and logical grouping.
- Make the layout responsive and touch-friendly on mobile.
- Keep all existing functionality and API contracts unchanged.

## Chosen Approach

**Approach A: Refined single-column with max-width and grouped sections.**

This keeps the page as one scrollable surface (no tabs or hidden sections), which preserves discoverability, while concentrating content so it no longer stretches across wide viewports. Grouping related settings into sections also makes the page easier to scan.

## Design Details

### Page Container

- Wrap the page in a centred container: `max-w-3xl mx-auto px-4 py-6 pb-24`.
  - `max-w-3xl` (48rem / 768px) prevents lines and cards from stretching on large monitors.
  - `pb-24` ensures the bottom fixed navigation never obscures the last card.
- Add a page header with the title "Settings" and a small save-status hint (e.g. "Unsaved changes" / "Saved") derived from the existing `brightnessSaved` state and dirty-state detection if added later.

### Section Grouping

Replace the flat card stack with six grouped cards, in this order:

1. **Status**
   - LED Matrix connection status, dimensions, brightness, diagnostics summary.
   - Live Matrix Preview image.
   - Test Matrix button.
2. **Receiver**
   - ADS-B source selector (Local RTL-SDR / Network receiver).
   - Network host/port inputs and Test connection button (visible only when Network is selected).
   - Current receiver connection status.
3. **Display**
   - Brightness slider.
   - Display mode selector (closest / cycle3 / list) with dynamic helper text.
   - Cycle interval input (visible only in cycle3 mode).
   - Aircraft layout picker.
   - Idle / scanning layout picker.
4. **Location & Units**
   - Location lookup component.
   - Latitude / Longitude inputs.
   - Distance / Altitude / Speed unit selects.
5. **Night Mode**
   - Night mode toggle + start/end times.
   - Sleep mode toggle + start/end times.
6. **System**
   - Auto-update toggle + update status, check/trigger buttons, progress.
   - Reboot / Shut Down buttons.
   - Reset Onboarding button.

### Responsive Behaviour

| Element | Desktop (>= md) | Mobile (< md) |
|---|---|---|
| Page container | centred, max-width 768px | full width, comfortable side padding |
| Paired fields (host/port, lat/lon, start/end times) | 2-column grid | stacked, full-width |
| Unit selects (distance/altitude/speed) | 3-column grid | stacked, full-width |
| Layout picker | 2-column grid | 1-column stack |
| Save button | prominent button group near bottom | full-width, optionally sticky footer |
| Section spacing | `space-y-4` | `space-y-6` for breathing room |

### Visual Hierarchy

- Each section card keeps the existing `Card` component (`bg-led-panel`, `border-white/10`).
- Section header: icon + title on one line, with an optional one-line description in `text-white/50`.
- Use `text-sm` labels and `text-xs` helper text consistently.
- Remove the smallest `text-[10px]` usage on mobile; bump badges/helper text to readable sizes.
- Ensure switches, buttons, and inputs meet a 44px minimum touch target on mobile.

### Component Refactoring

- Keep `Settings.tsx` as the stateful container for config, API calls, and validation.
- Introduce small presentational helpers inside `Settings.tsx` or a sibling file:
  - `SettingsSection` — `Card` wrapper with icon, title, and optional description.
  - `FormGrid` — responsive two-column grid for paired fields.
  - `CompactLayoutPicker` — the existing `LayoutPicker` simplified to avoid duplicated header logic and to render cleanly in both sections.
- No new external dependencies.

### Data Flow & Validation

- Reuse the existing `UserConfig` state and `api.put('/api/config', ...)` save path.
- Keep existing validation for network receiver host/port.
- Keep existing debounced brightness update behaviour.
- No changes to backend endpoints or config schema.

### Testing

- Add `frontend/src/components/Settings/Settings.test.tsx` with a render test that:
  - Mocks the settings hooks and API client.
  - Asserts that all six section headings are present.
  - Asserts that the Save button is rendered.
- Run `npm test` in `frontend/` and ensure no regressions.
- Manually verify the page at 320px, 768px, and 1440px viewports.

## Out of Scope

- Converting Settings into a tabbed or wizard interface.
- Adding new settings fields or backend functionality.
- Changing the application's colour palette or typography system.
- Deep accessibility audit beyond touch-target sizing and semantic headings.

## Files to Modify

- `frontend/src/components/Settings/Settings.tsx` — main refactor.
- `frontend/src/components/Settings/Settings.test.tsx` — new test file.

## Approval

Pending user review of this spec before implementation planning begins.
