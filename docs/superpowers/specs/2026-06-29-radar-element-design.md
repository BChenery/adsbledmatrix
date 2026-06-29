# Radar Element Design

## Goal

Add a new `radar` layout element to the Designer so users can drop a radar-style circle onto the LED matrix. The element shows the user's location at the centre and the currently displayed aircraft as a dot, giving an instant sense of where the aircraft is relative to the observer.

## Scope

- One aircraft dot only — the aircraft currently selected by the display engine (`closest` / `cycle3`).
- User-configurable range (default 20 km).
- Optional range rings and N/E/S/W tick marks.
- Available in the Designer element palette and configurable via the property panel.

## Visual Design

The element renders inside its bounding box (`x`, `y`, `width`, `height`).

- **Outer circle**: outline of the radar display.
- **Range rings**: concentric circles at 25%, 50%, 75%, 100% of the selected range.
- **Bearing ticks**: small tick marks pointing to N, E, S, W (0°, 90°, 180°, 270°).
- **User dot**: a small dot at the centre.
- **Aircraft dot**: a coloured dot positioned by the aircraft's real bearing and distance from the user.
- **Clipping**: if the aircraft is beyond the selected range, the dot is clamped to the edge of the radar circle.
- **No aircraft**: the radar background, rings, ticks and user dot are still drawn; the aircraft dot is hidden.

## Element Properties

| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `element_type` | string | `"radar"` | Fixed type identifier. |
| `range_km` | float/int | `20` | Maximum distance shown on the radar. |
| `ring_color` | string | `"#333333"` | Colour of the range rings and bearing ticks. |
| `dot_color` | string | `"#ff0000"` | Colour of the aircraft dot. |
| `user_dot_color` | string | `"#00ff00"` | Colour of the centre user dot. |
| `show_rings` | boolean | `true` | Whether to draw range rings. |
| `show_ticks` | boolean | `true` | Whether to draw N/E/S/W tick marks. |
| `x`, `y`, `width`, `height`, `z_index` | standard | required | Same as all other elements. |

## Backend

### DisplayEngine

Add a new branch in `DisplayEngine._render_element` for `element.element_type == "radar"`:

1. Compute the radar centre `(cx, cy)` and usable radius from the element bounds.
2. Draw the outer circle.
3. If `show_rings`, draw concentric range rings.
4. If `show_ticks`, draw short radial tick marks for N/E/S/W.
5. Draw the centre user dot.
6. If `ctx.aircraft` exists and has `distance_km` and `bearing`:
   - `ratio = min(distance_km / range_km, 1.0)`
   - `angle = math.radians(bearing - 90)` (0° is up/North)
   - `dot_x = cx + radius * ratio * cos(angle)`
   - `dot_y = cy + radius * ratio * sin(angle)`
   - Draw the aircraft dot at `(dot_x, dot_y)`.

The receiver already calculates `distance_km` and `bearing` from the user's configured lat/lon, so no new geospatial code is required.

### API / Models

No new API endpoints are required. The existing `LayoutUpdate` / `ElementCreate` schemas accept free-form `element_type` strings, so the backend will persist the new element type without changes.

## Frontend

### Element Palette

Add a `radar` preset to `frontend/src/components/LayoutDesigner/ElementPalette.tsx` with a default template:

```ts
{
  element_type: 'radar',
  x: 10,
  y: 10,
  width: 80,
  height: 80,
  range_km: 20,
  ring_color: '#333333',
  dot_color: '#ff0000',
  user_dot_color: '#00ff00',
  show_rings: true,
  show_ticks: true,
}
```

### Property Panel

Extend `frontend/src/components/LayoutDesigner/PropertyPanel.tsx` to show inputs for `range_km`, `ring_color`, `dot_color`, `user_dot_color`, `show_rings`, and `show_ticks` when a radar element is selected. Re-use existing colour and number inputs where possible.

## Testing

- Backend unit test: create a `radar` element and a mock aircraft at a known bearing/distance, render it, and assert the aircraft dot appears at the expected pixel location.
- Frontend: verify the radar preset appears in the palette and that property inputs update the element state.
- On-Pi validation: drop a radar element on a layout, save, and confirm the dot tracks the displayed aircraft.

## Out of Scope

- Showing multiple aircraft dots.
- Smooth animation or trail history.
- Range auto-scaling based on aircraft distance.
- Labels/numbers on range rings.
