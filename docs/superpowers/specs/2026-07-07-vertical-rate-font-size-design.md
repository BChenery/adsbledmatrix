# Vertical Rate Font Size Control — Design

## Goal

Let users change the text size of the dedicated **Vertical Rate** (`v. Rate`) element on the Designer page.

## Background

The Designer has a dedicated `vertical_rate` element type that renders an arrow + rate value. The canvas preview and the backend renderer already know how to draw text at a specific `font_size`, but the property panel only exposes the **Font Size** control for `text` and `data_field` elements. As a result, a `vertical_rate` element always uses its hard-coded default size and cannot be made bigger.

## Scope

- Add a **Font Size** input for `vertical_rate` elements only.
- Preserve the existing default size when no value is set.
- No schema or type changes are required; `LayoutElement` already has `font_size?: number`.

## Changes

### Frontend — Property Panel

File: `frontend/src/components/LayoutDesigner/PropertyPanel.tsx`

Add a conditional Font Size input when `element.element_type === 'vertical_rate'`. Reuse the same numeric input pattern used for `text` and `data_field`:

```tsx
{element.element_type === 'vertical_rate' && (
  <div className="space-y-1">
    <Label htmlFor="vertical-rate-font-size">Font Size</Label>
    <Input
      id="vertical-rate-font-size"
      type="number"
      value={element.font_size || ''}
      onChange={(e) => update('font_size', parseInt(e.target.value) || undefined)}
    />
  </div>
)}
```

### Backend — Display Engine

File: `backend/app/services/display_engine.py`

Update `_draw_vertical_rate` to pass the element's `font_size` through to `_draw_text`. If `font_size` is unset, keep the current default of `h - 4` so existing layouts render unchanged.

Current call:

```python
self._draw_text(draw, x, y, w, text, color, None, h - 4, height=h)
```

New call:

```python
font_size = getattr(element, "font_size", None)
font_family = getattr(element, "font_family", None)
self._draw_text(draw, x, y, w, text, color, font_family, font_size or h - 4, height=h)
```

The `font_family` is read but not exposed in the UI for this change; reading it keeps the renderer consistent with other text elements and makes a future Font Family control trivial to add.

### Canvas Preview

No change is required. `frontend/src/components/LayoutDesigner/Canvas.tsx` already uses `el.font_size || 12` when drawing `vertical_rate` text, so the preview will match the new setting.

## Validation

`scripts/validate_layouts.py` already rejects `font_size` values greater than `height - 4` for any element, so no additional validation is needed.

## Tests

### Frontend

Add a test in `frontend/src/components/LayoutDesigner/PropertyPanel.test.tsx` (new file) that mounts `PropertyPanel` with a `vertical_rate` element and asserts:

- A "Font Size" input is rendered.
- Changing the input value calls `onChange` with an updated element whose `font_size` matches the new value.

### Backend

Add a test in `backend/tests/test_display_engine.py` that draws two `vertical_rate` elements with explicit font sizes 12 and 24 and verifies that the larger size renders more non-black pixels.

## Acceptance Criteria

- [ ] Selecting a `vertical_rate` element in the Designer shows a Font Size input.
- [ ] Setting the Font Size updates the element and the canvas preview immediately.
- [ ] Saving the layout persists the `font_size` value.
- [ ] The backend renderer uses the saved `font_size` for `vertical_rate` elements.
- [ ] Existing layouts without a `font_size` render exactly as before.
- [ ] New frontend and backend tests pass.
