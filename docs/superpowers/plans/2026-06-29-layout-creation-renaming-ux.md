# Layout Creation & Renaming UX Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make newly created layouts appear in the toolbar menu immediately and allow the active layout's name to be edited inline in the toolbar, with name changes auto-saving.

**Architecture:** Move new-layout persistence from the Save button to the Create modal submit. Add an inline editable name field in the toolbar that auto-saves on blur. Keep the Save button responsible for canvas/element changes only. Introduce a tiny layout-name normalization helper with unit tests.

**Tech Stack:** React, TypeScript, Tailwind CSS, shadcn/ui Input/Button/DropdownMenu, Vitest, existing `useLayouts` hook.

---

## File Structure

| File | Responsibility |
|------|----------------|
| `adsbledmatrix/frontend/src/lib/layoutName.ts` | Pure helper to trim/normalize layout names and fall back when empty. |
| `adsbledmatrix/frontend/src/lib/layoutName.test.ts` | Unit tests for the helper. |
| `adsbledmatrix/frontend/src/components/LayoutDesigner/LayoutDesigner.tsx` | Owns layout state, handles immediate create on modal submit, handles rename API calls, wires props to Toolbar and PropertyPanel. |
| `adsbledmatrix/frontend/src/components/LayoutDesigner/Toolbar.tsx` | Renders inline editable layout name input + separate dropdown menu button. |
| `adsbledmatrix/frontend/src/components/LayoutDesigner/PropertyPanel.tsx` | Adds `onNameBlur` prop so the existing Name field can also trigger auto-save. |

---

### Task 1: Add layout name normalization helper with tests

**Files:**
- Create: `adsbledmatrix/frontend/src/lib/layoutName.ts`
- Create: `adsbledmatrix/frontend/src/lib/layoutName.test.ts`

- [ ] **Step 1: Write the helper**

```typescript
// adsbledmatrix/frontend/src/lib/layoutName.ts
export function normalizeLayoutName(
  name: string,
  fallback = 'Untitled Layout'
): string {
  const trimmed = name.trim();
  return trimmed || fallback;
}
```

- [ ] **Step 2: Write the failing test**

```typescript
// adsbledmatrix/frontend/src/lib/layoutName.test.ts
import { describe, it, expect } from 'vitest';
import { normalizeLayoutName } from './layoutName';

describe('normalizeLayoutName', () => {
  it('trims surrounding whitespace', () => {
    expect(normalizeLayoutName('  My Layout  ')).toBe('My Layout');
  });

  it('falls back for empty or whitespace-only names', () => {
    expect(normalizeLayoutName('')).toBe('Untitled Layout');
    expect(normalizeLayoutName('   ')).toBe('Untitled Layout');
  });

  it('uses a custom fallback when provided', () => {
    expect(normalizeLayoutName('', 'Default')).toBe('Default');
  });
});
```

- [ ] **Step 3: Run the test to verify it fails (file not imported yet / function exists but tests should pass after creation)**

Run:
```bash
cd adsbledmatrix/frontend && npm run test -- src/lib/layoutName.test.ts
```

Expected: PASS once files are created.

- [ ] **Step 4: Commit**

```bash
git add adsbledmatrix/frontend/src/lib/layoutName.ts adsbledmatrix/frontend/src/lib/layoutName.test.ts
git commit -m "feat: add layout name normalization helper"
```

---

### Task 2: Persist new layout immediately on modal Create

**Files:**
- Modify: `adsbledmatrix/frontend/src/components/LayoutDesigner/LayoutDesigner.tsx:136-144`

- [ ] **Step 1: Import the helper at the top of LayoutDesigner.tsx**

```typescript
import { normalizeLayoutName } from '@/lib/layoutName';
```

- [ ] **Step 2: Change `handleCreateNew` to async and call `create`**

Replace:

```typescript
const handleCreateNew = () => {
  setActiveLayout({
    ...DEFAULT_LAYOUT,
    name: newLayoutName.trim() || DEFAULT_LAYOUT.name,
  });
  setSelectedElement(null);
  setShowNewModal(false);
  setNewLayoutName('');
};
```

With:

```typescript
const handleCreateNew = async () => {
  try {
    const created = await create({
      ...DEFAULT_LAYOUT,
      name: normalizeLayoutName(newLayoutName, DEFAULT_LAYOUT.name),
    });
    setActiveLayout(created);
    setSelectedElement(null);
    setShowNewModal(false);
    setNewLayoutName('');
    toast.success('Layout created');
  } catch (err: any) {
    const message = err?.response?.detail
      ? JSON.stringify(err.response.detail)
      : err instanceof Error
      ? err.message
      : 'Create failed';
    toast.error(`Create failed: ${message}`);
  }
};
```

- [ ] **Step 3: Update the Create button to disable while creating**

In the New Layout modal's Create button, add a disabled state. Add local state if needed, or simply disable based on a temporary loading flag. For minimal change, add:

```typescript
const [isCreating, setIsCreating] = useState(false);
```

And wrap the create call with `setIsCreating(true/false)`.

The button becomes:

```tsx
<Button onClick={handleCreateNew} disabled={isCreating} className="flex-1 gap-2">
  <Plus size={16} />
  Create
</Button>
```

- [ ] **Step 4: Verify the new layout appears in the menu without pressing Save**

Run the dev server:
```bash
cd adsbledmatrix/frontend && npm run dev
```

Open the Designer, click **+**, enter a name, click **Create**. The new layout should appear in the dropdown menu immediately.

- [ ] **Step 5: Commit**

```bash
git add adsbledmatrix/frontend/src/components/LayoutDesigner/LayoutDesigner.tsx
git commit -m "feat: persist new layout immediately on create"
```

---

### Task 3: Add inline name input to Toolbar

**Files:**
- Modify: `adsbledmatrix/frontend/src/components/LayoutDesigner/Toolbar.tsx`

- [ ] **Step 1: Add `Input` import and new props**

```typescript
import { Input } from '@/components/ui/input';

interface ToolbarProps {
  ...
  layoutName: string;
  onRename: (name: string) => Promise<void>;
  canRename: boolean;
}
```

- [ ] **Step 2: Add local draft name state and sync from props**

Inside the component:

```typescript
const [draftName, setDraftName] = useState(layoutName);

useEffect(() => {
  setDraftName(layoutName);
}, [layoutName]);
```

- [ ] **Step 3: Replace the dropdown trigger with an input + separate dropdown button**

Replace the existing layout selector block (lines 50-70):

```tsx
<DropdownMenu>
  <DropdownMenuTrigger asChild>
    <Button variant="secondary" className="min-w-[160px] justify-between gap-2">
      <span className="truncate">{activeLayout?.name || 'Select Layout'}</span>
      <ChevronDown size={14} />
    </Button>
  </DropdownMenuTrigger>
  <DropdownMenuContent align="start" className="w-56">
    ...
  </DropdownMenuContent>
</DropdownMenu>
```

With:

```tsx
<div className="flex items-center gap-1">
  <Input
    type="text"
    value={draftName}
    onChange={(e) => setDraftName(e.target.value)}
    onBlur={async () => {
      if (!canRename || draftName === layoutName) return;
      try {
        await onRename(draftName);
      } catch {
        setDraftName(layoutName);
      }
    }}
    disabled={!canRename}
    placeholder="Layout name"
    className="h-9 min-w-[140px] bg-led-black border-white/10 text-sm"
  />
  <DropdownMenu>
    <DropdownMenuTrigger asChild>
      <Button variant="secondary" size="icon" className="h-9 w-9">
        <ChevronDown size={14} />
      </Button>
    </DropdownMenuTrigger>
    <DropdownMenuContent align="start" className="w-56">
      {layouts.map((l) => (
        <DropdownMenuItem key={l.id} onClick={() => onSelectLayout(l)}>
          <div>
            <div className="font-medium">{l.name}</div>
            <div className="text-xs text-white/40">{l.width}×{l.height}</div>
          </div>
        </DropdownMenuItem>
      ))}
      {layouts.length === 0 && (
        <div className="px-2 py-3 text-sm text-white/30">No layouts yet</div>
      )}
    </DropdownMenuContent>
  </DropdownMenu>
</div>
```

- [ ] **Step 4: Commit**

```bash
git add adsbledmatrix/frontend/src/components/LayoutDesigner/Toolbar.tsx
git commit -m "feat: inline editable layout name in toolbar"
```

---

### Task 4: Wire toolbar rename to the backend

**Files:**
- Modify: `adsbledmatrix/frontend/src/components/LayoutDesigner/LayoutDesigner.tsx`

- [ ] **Step 1: Add `handleRename` function**

After `handleCreateNew`, add:

```typescript
const handleRename = async (name: string) => {
  if (!activeLayout?.id || name === activeLayout.name) return;
  const normalized = normalizeLayoutName(name, activeLayout.name);
  try {
    const updated = await update(activeLayout.id, { name: normalized });
    setActiveLayout(updated);
    toast.success('Layout renamed');
  } catch (err: any) {
    const message = err?.response?.detail
      ? JSON.stringify(err.response.detail)
      : err instanceof Error
      ? err.message
      : 'Rename failed';
    toast.error(`Rename failed: ${message}`);
    throw err;
  }
};
```

- [ ] **Step 2: Pass props to Toolbar**

```tsx
<Toolbar
  ...
  layoutName={activeLayout?.name || ''}
  onRename={handleRename}
  canRename={!!activeLayout?.id}
/>
```

- [ ] **Step 3: Verify renaming in the toolbar**

In the running app, select a layout, edit the name in the toolbar, press Tab/click away. The dropdown menu should show the new name and a success toast should appear.

- [ ] **Step 4: Commit**

```bash
git add adsbledmatrix/frontend/src/components/LayoutDesigner/LayoutDesigner.tsx
git commit -m "feat: wire toolbar rename to backend"
```

---

### Task 5: Auto-save name from the right-side property panel

**Files:**
- Modify: `adsbledmatrix/frontend/src/components/LayoutDesigner/PropertyPanel.tsx`
- Modify: `adsbledmatrix/frontend/src/components/LayoutDesigner/LayoutDesigner.tsx`

- [ ] **Step 1: Add `onNameBlur` prop to PropertyPanel**

```typescript
interface PropertyPanelProps {
  layout: Layout;
  onLayoutChange: (layout: Layout) => void;
  onNameBlur?: () => void;
  element: LayoutElement | null;
  onChange: (el: LayoutElement) => void;
  onDelete: () => void;
}
```

- [ ] **Step 2: Call `onNameBlur` on the name input blur**

```tsx
<div className="space-y-1">
  <Label>Name</Label>
  <Input
    type="text"
    value={layout.name}
    onChange={(e) => updateLayout('name', e.target.value)}
    onBlur={onNameBlur}
    placeholder="Layout name"
  />
</div>
```

- [ ] **Step 3: Wire the prop in LayoutDesigner**

```tsx
<PropertyPanel
  layout={activeLayout}
  onLayoutChange={setActiveLayout}
  onNameBlur={() => activeLayout?.id && handleRename(activeLayout.name)}
  element={selectedElement}
  onChange={handleUpdateElement}
  onDelete={handleDeleteElement}
/>
```

- [ ] **Step 4: Verify property panel renaming**

Select a layout, deselect any canvas element, edit the Name field in the right panel, blur the field. The toolbar and menu should reflect the new name.

- [ ] **Step 5: Commit**

```bash
git add adsbledmatrix/frontend/src/components/LayoutDesigner/PropertyPanel.tsx adsbledmatrix/frontend/src/components/LayoutDesigner/LayoutDesigner.tsx
git commit -m "feat: auto-save layout name from property panel"
```

---

### Task 6: Run automated checks

**Files:** none

- [ ] **Step 1: Run tests**

```bash
cd adsbledmatrix/frontend && npm run test
```

Expected: all tests pass, including the new `layoutName.test.ts`.

- [ ] **Step 2: Run linter**

```bash
cd adsbledmatrix/frontend && npm run lint
```

Expected: no errors.

- [ ] **Step 3: Run TypeScript check**

```bash
cd adsbledmatrix/frontend && npx tsc --noEmit
```

Expected: no type errors.

- [ ] **Step 4: Commit**

```bash
git commit -m "chore: verify layout rename UX with tests and lint"
```

---

### Task 7: Manual end-to-end verification

**Files:** none

- [ ] **Step 1: Start the dev stack**

```bash
cd adsbledmatrix/frontend && npm run dev
```

- [ ] **Step 2: Verify the user story**

1. Open `/designer`.
2. Click **+**, type "Test Layout", click **Create**.
3. Confirm "Test Layout" appears in the dropdown menu immediately, before pressing **Save**.
4. Edit the name in the toolbar to "Test Layout Renamed", blur.
5. Confirm the dropdown menu shows the new name and a success toast appears.
6. Add an element to the canvas.
7. Confirm the element is not persisted until **Save** is clicked.
8. Click **Save**, refresh the page, and confirm the renamed layout and element are still present.

- [ ] **Step 3: Commit verification notes (optional)**

No code change needed if verification passes.

---

## Self-Review

**Spec coverage:**
- New layout persists immediately → Task 2.
- New layout appears in menu → Task 2 (side effect of using `useLayouts.create`).
- Toolbar inline name editing → Tasks 3 and 4.
- Name changes auto-save on blur → Tasks 4 and 5.
- Save button still handles canvas/elements → unchanged `handleSave`.
- Empty-name fallback → Task 1 helper used in Tasks 2 and 4.

**Placeholder scan:**
- No TBD/TODO placeholders.
- All code snippets are complete and use real file paths.
- Exact commands and expected outputs are provided.

**Type consistency:**
- `normalizeLayoutName` signature is consistent everywhere.
- `onRename` prop signature matches between `LayoutDesigner` and `Toolbar`.
- `onNameBlur` prop is optional in `PropertyPanel` and provided by `LayoutDesigner`.
