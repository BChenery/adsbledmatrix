# Radar Plane Symbol Design

## Goal

Add an option to the existing `radar` layout element so the aircraft marker can be shown as a small plane silhouette instead of the default red dot. The plane is rotated to the aircraft's heading to give an at-a-glance sense of where the aircraft is pointing.

## Scope

- Add a toggle on the radar element to switch between the existing dot and a plane symbol.
- The plane symbol rotates to match the aircraft's heading.
- The plane uses the existing aircraft dot colour.
- If the aircraft has no heading, fall back to the dot.
- Changes apply to both the Designer canvas preview and the backend LED matrix renderer.

## Visual Design

The radar element stays unchanged except for the aircraft marker:

- **Dot mode (existing):** a 3 px radius filled circle at the bearing/distance position, coloured with `dot_color`.
- **Plane mode (new):** a small plane silhouette centred on the same bearing/distance position, rotated so the nose points in the aircraft's heading. The silhouette is drawn with the same `dot_color`.

Plane shape (unrotated, pointing up/North):

```
        Nose (0, -4)
          *
         / \
   LW *-   -* RW
         \ /
          * Tail (0, 3)
```

The polygon is roughly:

```
[(0, -4), (-3, 2), (-1, 1), (0, 3), (1, 1), (3, 2)]
```

Each point is rotated around the aircraft position by `heading` degrees, where 0° heading = up/North. The shape is intentionally simple so it renders clearly on a low-resolution LED matrix.

## Element Properties

| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `use_plane_symbol` | boolean | `false` | When `true`, draw a plane silhouette instead of the aircraft dot. |

All existing radar properties (`range_km`, `ring_color`, `dot_color`, `user_dot_color`, `show_rings`, `show_ticks`) remain unchanged. `dot_color` still controls the colour of the aircraft marker in both modes.

## Backend

### DisplayEngine

Modify `backend/app/services/display_engine.py` in the existing `_draw_radar` method.

After computing the aircraft's bearing/distance position:

1. If `ctx.aircraft.heading` is `None` or `use_plane_symbol` is `False`, draw the existing 3 px dot.
2. If `use_plane_symbol` is `True` and a heading exists:
   - Define the unrotated plane polygon relative to `(dot_x, dot_y)`.
   - Rotate each point by `heading` degrees.
   - Fill the polygon with `dot_color`.

Rotation helper (reuse existing `math` import):

```python
def _rotate_point(px, py, cx, cy, angle_deg):
    angle = math.radians(angle_deg)
    cos_a = math.cos(angle)
    sin_a = math.sin(angle)
    rx = cx + (px - cx) * cos_a - (py - cy) * sin_a
    ry = cy + (px - cx) * sin_a + (py - cy) * cos_a
    return rx, ry
```

Plane polygon points (relative to centre):

```python
plane = [(0, -4), (-3, 2), (-1, 1), (0, 3), (1, 1), (3, 2)]
```

## Frontend

### Layout type

Add `use_plane_symbol?: boolean` to `LayoutElement` in `frontend/src/types/layout.ts`.

### Canvas preview

Modify `frontend/src/components/LayoutDesigner/Canvas.tsx` in the radar rendering branch.

Use the same logic as the backend: if `el.use_plane_symbol` is true and the aircraft has a heading, draw the rotated polygon; otherwise draw the existing arc.

Canvas rotation helper:

```typescript
function rotatePoint(px: number, py: number, cx: number, cy: number, angleDeg: number): [number, number] {
  const angle = (angleDeg * Math.PI) / 180;
  const cos = Math.cos(angle);
  const sin = Math.sin(angle);
  return [
    cx + (px - cx) * cos - (py - cy) * sin,
    cy + (px - cx) * sin + (py - cy) * cos,
  ];
}
```

Draw the polygon with `ctx.fillStyle = dotColor` and `ctx.fill()`.

### Property panel

Modify `frontend/src/components/LayoutDesigner/PropertyPanel.tsx` in the `radar` block.

Add a checkbox after the existing radar toggles:

```tsx
<div className="flex items-center gap-2 pt-1">
  <input
    type="checkbox"
    id="use_plane_symbol"
    checked={element.use_plane_symbol ?? false}
    onChange={(e) => update('use_plane_symbol', e.target.checked)}
    className="w-4 h-4 rounded border-gray-600"
  />
  <Label htmlFor="use_plane_symbol" className="cursor-pointer">Use Plane Symbol</Label>
</div>
```

### Element palette

No change required. The existing radar preset keeps `use_plane_symbol` unset/false, preserving current behaviour.

## Testing

- Backend unit test: create a radar element with `use_plane_symbol=true` and an aircraft at a known heading. Render it and assert that a non-dot plane-shaped pixel cluster appears at the expected position and orientation.
- Frontend: verify the checkbox appears when a radar element is selected and toggling it updates the element state.
- On-Pi validation: enable the plane symbol on a layout, save, and confirm the LED matrix shows a plane marker rotated to the aircraft heading.

## Out of Scope

- Multiple aircraft markers.
- Animated plane symbols or trail history.
- A separate plane colour property (it reuses `dot_color`).
- Custom plane symbol upload or alternate icon sets.
