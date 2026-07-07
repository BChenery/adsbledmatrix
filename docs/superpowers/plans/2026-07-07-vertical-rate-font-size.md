# Vertical Rate Font Size Control — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Font Size input for the dedicated `vertical_rate` element in the Layout Designer and make both the preview canvas and the LED renderer use it.

**Architecture:** The `vertical_rate` element already stores optional `font_size` on `LayoutElement`. We will expose that property in the property panel and pass it through to the backend text renderer. If no size is set, the backend keeps its current `height - 4` default so existing layouts are unchanged.

**Tech Stack:** React + TypeScript + Tailwind (frontend), Vitest + `@testing-library/react` + jsdom (frontend tests), Python + Pillow + pytest (backend).

---

## File Structure

| File | Responsibility |
|------|---------------|
| `frontend/src/components/LayoutDesigner/PropertyPanel.tsx` | Add the Font Size input for `vertical_rate` elements. |
| `frontend/vite.config.ts` | Tell Vitest to use the `jsdom` environment for component tests. |
| `frontend/src/components/LayoutDesigner/PropertyPanel.test.tsx` | New test: the panel renders a Font Size input for `vertical_rate` and changing it calls `onChange`. |
| `backend/app/services/display_engine.py` | Update `_draw_vertical_rate` to read `element.font_size` and fall back to `h - 4`. |
| `backend/tests/test_display_engine.py` | New test: a larger `font_size` renders more pixels than the default. |

---

### Task 1: Add Component Test Dependencies and Configure Vitest

**Files:**
- Modify: `frontend/vite.config.ts`
- Modify: `frontend/package.json` (devDependencies)

- [ ] **Step 1: Install test dependencies**

```bash
cd frontend
npm install --save-dev @testing-library/react jsdom
```

All remaining git commands in this plan should be run from the worktree root (`/home/bchen/GitHub/adsledmatrix/adsbledmatrix/.worktrees/feature-vertical-rate-font-size`).

- [ ] **Step 2: Configure Vitest to use jsdom**

Modify `frontend/vite.config.ts` by adding a `test` block:

```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  build: {
    outDir: '../backend/app/static',
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true,
      },
    },
  },
  test: {
    environment: 'jsdom',
  },
})
```

- [ ] **Step 3: Run existing tests to confirm the environment still works**

```bash
npm run test
```

Expected: both existing test files pass.

- [ ] **Step 4: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/vite.config.ts
git commit -m "chore: add component testing dependencies for LayoutDesigner"
```

---

### Task 2: Expose Font Size for `vertical_rate` in the Property Panel

**Files:**
- Modify: `frontend/src/components/LayoutDesigner/PropertyPanel.tsx`

- [ ] **Step 1: Add the Font Size input for `vertical_rate`**

Insert the following block in `frontend/src/components/LayoutDesigner/PropertyPanel.tsx` inside the properties form, after the Z-Index field and before the Color field:

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

- [ ] **Step 2: Type-check the frontend**

```bash
npm run build
```

Expected: `tsc` exits with no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/LayoutDesigner/PropertyPanel.tsx
git commit -m "feat: expose font size control for vertical_rate elements"
```

---

### Task 3: Add Frontend Test for the New Control

**Files:**
- Create: `frontend/src/components/LayoutDesigner/PropertyPanel.test.tsx`

- [ ] **Step 1: Write the test**

Create `frontend/src/components/LayoutDesigner/PropertyPanel.test.tsx`:

```tsx
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import PropertyPanel from './PropertyPanel';
import type { LayoutElement, Layout } from '@/types/layout';

describe('PropertyPanel', () => {
  it('renders a Font Size input for vertical_rate and updates the element', () => {
    const element: LayoutElement = {
      element_type: 'vertical_rate',
      x: 4,
      y: 4,
      z_index: 0,
      width: 64,
      height: 32,
    };

    const layout: Layout = {
      name: 'Test Layout',
      width: 256,
      height: 128,
      is_default: false,
      elements: [element],
    };

    const onChange = vi.fn();

    render(
      <PropertyPanel
        layout={layout}
        onLayoutChange={() => {}}
        element={element}
        onChange={onChange}
        onDelete={() => {}}
      />
    );

    const input = screen.getByLabelText('Font Size') as HTMLInputElement;
    expect(input).toBeDefined();
    expect(input.value).toBe('');

    fireEvent.change(input, { target: { value: '20' } });

    expect(onChange).toHaveBeenCalledTimes(1);
    expect(onChange).toHaveBeenCalledWith({
      ...element,
      font_size: 20,
    });
  });
});
```

- [ ] **Step 2: Run the new test and confirm it passes**

```bash
npm run test
```

Expected: the new `PropertyPanel.test.tsx` test passes.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/LayoutDesigner/PropertyPanel.test.tsx
git commit -m "test: verify vertical_rate font size control in property panel"
```

---

### Task 4: Make the Backend Renderer Use `font_size` for `vertical_rate`

**Files:**
- Modify: `backend/app/services/display_engine.py`

- [ ] **Step 1: Pass `element` into `_draw_vertical_rate`**

In `_render_element`, change the call from:

```python
elif element_type == "vertical_rate":
    self._draw_vertical_rate(draw, x, y, w, h, ctx, color)
```

to:

```python
elif element_type == "vertical_rate":
    self._draw_vertical_rate(draw, x, y, w, h, element, ctx, color)
```

- [ ] **Step 2: Update `_draw_vertical_rate` to read the element's font size**

Replace the existing `_draw_vertical_rate` method with:

```python
    def _draw_vertical_rate(self, draw: ImageDraw.Draw, x: int, y: int, w: int, h: int, element: Any, ctx: RenderContext, color: Tuple[int, int, int]):
        rate = ctx.aircraft.vertical_rate if ctx.aircraft else None
        if rate is None:
            text = "---"
        elif rate > 100:
            text = f"▲ {rate}"
        elif rate < -100:
            text = f"▼ {abs(rate)}"
        else:
            text = "→ level"
        font_size = getattr(element, "font_size", None)
        font_family = getattr(element, "font_family", None)
        self._draw_text(draw, x, y, w, text, color, font_family, font_size or h - 4, height=h)
```

- [ ] **Step 3: Run backend tests to confirm no regressions**

From the `backend` directory:

```bash
PYTHONPATH=..:. /home/bchen/GitHub/adsledmatrix/adsbledmatrix/backend/.venv/bin/python -m pytest tests/test_display_engine.py -q
```

Expected: all existing tests still pass.

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/display_engine.py
git commit -m "feat: use vertical_rate element font_size in display engine"
```

---

### Task 5: Add Backend Test for `vertical_rate` Font Size

**Files:**
- Modify: `backend/tests/test_display_engine.py`

- [ ] **Step 1: Append the test to the existing test file**

Add the following helper at the top of `backend/tests/test_display_engine.py` (after the imports):

```python
def _count_non_black_pixels(img):
    """Count pixels that are not exactly black."""
    return sum(1 for px in img.get_flattened_data() if px != (0, 0, 0))
```

Then append this test to `backend/tests/test_display_engine.py`:

```python
def test_vertical_rate_uses_custom_font_size(engine):
    """A larger explicit font_size should render more text pixels than a smaller one."""
    from unittest.mock import MagicMock
    from app.services.display_engine import RenderContext
    from PIL import Image, ImageDraw

    aircraft = MagicMock()
    aircraft.vertical_rate = 1200

    ctx = RenderContext(aircraft=aircraft)

    element_small = MagicMock()
    element_small.element_type = 'vertical_rate'
    element_small.font_size = 12
    element_small.font_family = None

    element_large = MagicMock()
    element_large.element_type = 'vertical_rate'
    element_large.font_size = 24
    element_large.font_family = None

    img_small = Image.new('RGB', (64, 32), (0, 0, 0))
    draw_small = ImageDraw.Draw(img_small)
    engine._draw_vertical_rate(draw_small, 0, 0, 64, 32, element_small, ctx, (255, 255, 255))

    img_large = Image.new('RGB', (64, 32), (0, 0, 0))
    draw_large = ImageDraw.Draw(img_large)
    engine._draw_vertical_rate(draw_large, 0, 0, 64, 32, element_large, ctx, (255, 255, 255))

    small_pixels = _count_non_black_pixels(img_small)
    large_pixels = _count_non_black_pixels(img_large)

    assert small_pixels > 0, "Expected the small font to render some text"
    assert large_pixels > small_pixels, (
        f"Expected larger font_size to render more pixels, got {large_pixels} <= {small_pixels}"
    )
```

Note: comparing against the default `h - 4` fallback (28 for a 32px box) would fail because any valid custom font size is `<= h - 4`. The test therefore compares two explicit sizes (12 vs 24).

- [ ] **Step 2: Run the new test and confirm it passes**

```bash
PYTHONPATH=..:. /home/bchen/GitHub/adsledmatrix/adsbledmatrix/backend/.venv/bin/python -m pytest tests/test_display_engine.py::test_vertical_rate_uses_custom_font_size -v
```

Expected: `test_vertical_rate_uses_custom_font_size` passes.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_display_engine.py
git commit -m "test: verify vertical_rate respects custom font_size"
```

---

### Task 6: Final Verification

- [ ] **Step 1: Run the full frontend test suite**

```bash
cd frontend
npm run test
```

Expected: all frontend tests pass.

- [ ] **Step 2: Run the full backend test suite**

```bash
cd backend
PYTHONPATH=..:. /home/bchen/GitHub/adsledmatrix/adsbledmatrix/backend/.venv/bin/python -m pytest -q
```

Expected: all backend tests pass.

- [ ] **Step 3: Lint the frontend (pre-existing config issue)**

```bash
cd frontend
npm run lint
```

Note: the frontend currently has no ESLint configuration file, so `npm run lint` fails with "ESLint couldn't find a configuration file." This is a pre-existing issue unrelated to this feature. If a config is added in the future, this step should pass with no lint errors. The new code follows the same patterns as the existing property-panel inputs.

- [ ] **Step 4: Final commit if any fixes were needed**

If any test fixes were required, commit them; otherwise this task is verification only. Ensure the worktree is clean (no build artifacts from `npm run build` are left in `backend/app/static/`).

---

## Self-Review

- **Spec coverage:**
  - Property panel Font Size input → Task 2.
  - Backend uses the saved size → Task 4.
  - Canvas preview already respects `font_size` → no task needed.
  - Frontend test → Task 3.
  - Backend test → Task 5.
  - Existing validator limits size → no task needed.
- **Placeholder scan:** No TODOs, TBDs, or vague steps. Each step includes exact file paths and code.
- **Type consistency:** `LayoutElement` type already has `font_size?: number`; the panel update uses `parseInt(...)` consistent with other fields. Backend reads `element.font_size` via `getattr`, consistent with `_render_element` and the design spec.
