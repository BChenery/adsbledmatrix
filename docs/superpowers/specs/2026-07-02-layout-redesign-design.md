# Default Layout Redesign

## Objective

Redesign every default layout in `data/default_layouts.json` so they look deliberate, polished, and "wow" on the LED matrix. Fix overlapping fields, out-of-bounds elements, inconsistent sizing, and clashing colours. Introduce a shared design system so all layouts feel like one product.

## Background

The display renders layouts from `data/default_layouts.json` onto a 256×128 pixel canvas (four 128×64 P2 panels in a U-mapper chain). The startup code in `backend/app/lifespan.py` merges this file into the database on every boot, replacing the elements of any existing layout with the same name. That means updating the JSON is sufficient to refresh existing installs.

Current problems observed across the defaults:
- Font sizes exceed their declared box heights (e.g. 32 px font in a 24 px box).
- Elements sit on or beyond the canvas edge.
- Overlapping fields in `Aviation Enthusiast`, `Flight Tracker`, and `Split Detail + List`.
- Colours are arbitrary: cyan, orange, green, white, grey with no hierarchy.
- No consistent margin, grid, or vertical rhythm.
- Distance bar labels are rendered below the bar, often clipping the bottom margin.
- Aircraft list rows use fixed spacing that does not account for the 128 px height.

## Design System

### Canvas
- Logical size: 256 × 128 px.
- Safe area: 4 px margin on all sides, so content lives in `x: 4–252`, `y: 4–124`.
- Spacing base unit: 4 px.

### Colour Palette
| Role | Hex | Usage |
|------|-----|-------|
| Background | `#000000` | Empty canvas |
| Primary | `#00d4ff` | Callsign, hero numbers, active state |
| Secondary | `#a0aec0` | Labels, captions, metadata |
| Accent | `#ffb347` | Distance, route, highlight values |
| Positive | `#4ade80` | Climb, good status |
| Negative | `#f87171` | Descent, alerts |
| Muted | `#334155` | Dividers, rings, subtle borders |
| White | `#ffffff` | Idle hero text only |

All layouts use only these colours. No ad-hoc hex codes.

### Typography
| Style | Font size | Box height | Use |
|-------|-----------|------------|-----|
| Hero | 32 px | 36 px | Giant callsign or distance |
| Title | 24 px | 28 px | Section title, route |
| Body | 16 px | 20 px | Primary data values |
| Caption | 12 px | 16 px | Labels, units, header text |

Text is rendered inside its box with a consistent anchor:
- Hero/title/value boxes: horizontally centred, vertically anchored near the top so cap-height fills the upper portion.
- Captions, labels, and table content: left-aligned.
Box height must be ≥ font size + 4 px for descenders.

### Vertical Rhythm
- 4 px gap between related items (e.g. label + value).
- 8 px gap between groups.
- 12 px gap between major sections.
- Distance bars sit at `y = 118` with height 6 px, so the bar body ends exactly at the safe-area bottom (`y = 124`).

## Layout Families

The 13 existing layouts are grouped into families. Each family shares the same zone structure so the user can switch between them without relearning where to look.

### 1. Flight Card
Layouts: `Aviation Enthusiast`, `Flight Tracker`, `Pilot View`, `Type & Speed`

Structure (single-aircraft focus):
```
+------------------------------------------+
| [LOGO*]  CALLSIGN          ROUTE    DIST |
|          registration/type               |
|  ALT        SPD        HDG   [ARROW]     |
|  vertical rate                           |
| [========== distance bar ==========]     |
+------------------------------------------+
```
- Top row: logo (48×48, x=4), callsign (hero, x=60, width 130), route (title, right aligned), distance value (accent, far right).
- Second row: registration / type code / operator (caption, secondary).
- Third row: ALT, SPD, HDG labels + values in three columns; heading arrow on the right.
- Fourth row: vertical rate (caption).
- Bottom: full-width distance bar.

*Logo shown only when `has_logo` is true.

### 2. Brand Hero
Layouts: `Airline Brand`, `Logo & Distance`

Structure:
```
+------------------------------------------+
| [       LARGE LOGO       ]  CALLSIGN      |
|                             ROUTE        |
|                             DISTANCE     |
| [========== distance bar ==========]     |
+------------------------------------------+
```
- Left half: logo 100×100 px, centred vertically.
- Right half: callsign (title), route (body), distance (hero).
- Bottom: full-width distance bar.

### 3. Route Hero
Layout: `Route Focus`

Structure:
```
+------------------------------------------+
| CALLSIGN                          [LOGO*]|
|                                          |
|      ORIGIN  →  DESTINATION              |
|                                          |
|  ALT       SPD       HDG        DIST     |
| [========== distance bar ==========]     |
+------------------------------------------+
```
- Top: callsign left, small logo right.
- Middle: giant route `ORIGIN → DESTINATION` (hero), centred.
- Bottom row: four data chips and distance bar.

### 4. Minimal
Layout: `Minimal`

Structure:
```
+------------------------------------------+
|                                          |
|           CALLSIGN                       |
|                                          |
|           DISTANCE                       |
|                                          |
+------------------------------------------+
```
- Callsign hero, centred horizontally.
- Distance hero, centred horizontally, accent colour.
- No bar, no labels, maximum readability from across a room.

### 5. Lists
Layouts: `Airport Board`, `Close Encounters`, `Split Detail + List`

#### Airport Board
- Full-width table from x=4 to x=252.
- Header caption row: callsign, origin, destination, alt, spd, dist.
- 5 rows at 22 px row height, 12 px font.
- Alternating row backgrounds are not used (LED panels have low fill factor); instead a subtle divider line every row in muted colour.

#### Close Encounters
- Title "CLOSEST AIRCRAFT" at top in primary.
- 5 rows, 22 px row height, columns: callsign, route, distance.
- Distance right-aligned in accent.

#### Split Detail + List
- Left panel (170 px wide): single aircraft detail following Flight Card compact rules.
- Right panel (74 px wide): list of next 4 aircraft, callsign + distance only.
- Vertical divider line at x=174 in muted colour.

### 6. Radar / Idle
Layout: `Idle / Scanning`

Structure:
```
+------------------------------------------+
|                                          |
|         [radar sweep animation]          |
|                                          |
|       "Scanning for aircraft..."         |
|              HH:MM:SS                    |
+------------------------------------------+
```
- Radar blip centred, 100×100 px.
- Text caption below, white.
- Time in secondary caption.

### 7. Info Dense
Layout: `Data Dump`

Structure (tight grid, everything visible at once):
- Row 1: callsign (hero), registration + type code (caption, right).
- Row 2: operator ICAO, route.
- Row 3: ALT, SPD, HDG chips.
- Row 4: DIST + vertical rate.
- Heading arrow 32×32 bottom-right.
- Distance bar at bottom.

## Validation

Add a standalone validation script `scripts/validate_layouts.py` that loads `data/default_layouts.json` and checks:
1. Every element fits inside the layout width/height.
2. No two elements overlap (unless one has `z_index` higher and both are opaque; text-over-image is allowed).
3. Font size ≤ box height - 4 px.
4. Only palette colours are used.
5. Required fields present for each element type.

This script can be run locally and later added to CI. It does not block the display engine at runtime.

## Minor Engine Helpers

To make the redesigns render cleanly, make three small changes in `display_engine.py`:
1. Clip text to its declared box width so long callsigns or routes do not bleed into neighbours.
2. Draw text using the box top as the baseline anchor, then add a small offset so cap-height sits near the top of the box (current code draws from the top-left including font internal leading, which can look off-centre).
3. Stop `distance_bar` from drawing its own label below the bar. The redesigned layouts place the distance value in a separate `data_field` element, so the bar label currently overdraws the bottom margin.

Both changes are backward-compatible and make existing user layouts safer too.

## Files to Change

1. `data/default_layouts.json` — all layouts redesigned.
2. `scripts/validate_layouts.py` — new validation script.
3. `backend/app/services/display_engine.py` — text clipping and baseline alignment.
4. `backend/tests/test_layouts.py` — extend to assert defaults pass validation.

## Out of Scope

- New element types (icons, charts, weather).
- Layout designer UI changes.
- Removing existing layouts.
- Runtime layout validation in the display engine.

## Success Criteria

- All 13 default layouts fit within the 256×128 canvas with no overlaps.
- Every layout uses only the approved palette.
- `scripts/validate_layouts.py` passes with zero warnings.
- A rendered preview of each layout (via existing framebuffer endpoint or local mock) looks intentional and readable from a distance.
