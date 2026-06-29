# Layout Creation & Renaming UX Design

## Problem

Two UX gaps in the Layout Designer feel like a single bug:

1. **New layouts do not appear in the layout menu.** Clicking the "+" modal's **Create** button only creates a local, unsaved `activeLayout`. The dropdown menu is rendered from the persisted `layouts` list fetched from `/api/layouts`, so the new layout is invisible there until the user presses **Save**.
2. **Layout names are hard to edit.** The Name input lives in the right-side **Layout Properties** panel, which is only visible when no canvas element is selected. As soon as the user selects an element, the name field disappears.

## Goals

- A newly created layout must appear in the layout menu immediately.
- The active layout's name must be editable at all times, in an obvious location.
- The existing **Save** button must keep its meaning for layout content (elements, dimensions).

## Non-Goals

- Adding layout deletion UI.
- Changing the backend API or data model.
- Auto-saving every canvas/element change.

## Decision Summary

| Choice | Decision |
|--------|----------|
| When does a new layout persist? | Immediately on modal **Create**. |
| Where is the name edited? | Inline in the toolbar, next to the layout dropdown. |
| When does a name change persist? | Immediately on blur (auto-save). |
| When do canvas/element changes persist? | On **Save** click (unchanged). |

## Design Details

### 1. New Layout Flow

1. User clicks the **+** toolbar button.
2. The existing "New Layout" modal opens and asks for a name.
3. On **Create**, `LayoutDesigner` calls `useLayouts.create(activeLayout)` immediately.
4. The returned persisted layout (with `id`) is set as `activeLayout`.
5. Because `useLayouts.create` appends the layout to the `layouts` state, the dropdown menu now includes it.

**Edge cases:**
- If the API call fails, show a toast error and keep the modal open so the user can retry.
- If the user leaves the name blank, fall back to `"New Layout"`.

### 2. Toolbar Name Editing

- The dropdown trigger button contains an inline `<Input>` to the left of the existing chevron icon.
- The input displays `activeLayout.name`.
- On `blur` (or `change` with debounce), if the name changed and a layout is active:
  1. Trim the value; if empty, revert to `"Untitled Layout"`.
  2. Call `useLayouts.update(activeLayout.id, { name })`.
  3. Update `activeLayout` and the `layouts` list with the returned layout.
- The dropdown arrow remains functional to open the layout menu.

**Visual behavior:**
- The input should look like plain text until focused, matching the existing dark toolbar style.
- When no layout is active, the trigger shows `"Select Layout"` as before.

### 3. Save Button

- The **Save** button continues to persist:
  - `elements`
  - `width`
  - `height`
  - `description`
  - `name` (as a fallback if the toolbar auto-save was skipped)
- For existing layouts, `update` is used.
- For brand-new layouts, create already happened, so the same `update` path is used.

### 4. Right-Side Property Panel

- The existing **Name** field in the Layout Properties panel is retained as a secondary, synced input.
- Changing it updates `activeLayout.name`, and a blur triggers the same immediate `update` call.
- This preserves discoverability for users who expect the name to live there.

## Files to Modify

- `adsbledmatrix/frontend/src/components/LayoutDesigner/LayoutDesigner.tsx`
- `adsbledmatrix/frontend/src/components/LayoutDesigner/Toolbar.tsx`
- `adsbledmatrix/frontend/src/components/LayoutDesigner/PropertyPanel.tsx` (optional sync only)

## API Surface

No backend changes are required. Existing endpoints are sufficient:

- `POST /api/layouts` — create a new layout immediately on modal submit.
- `PUT /api/layouts/{id}` — update the layout name and content.

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Accidental empty layout drafts in the DB | Acceptable; deletion UI can be added later if it becomes a problem. |
| Two name inputs getting out of sync | Both inputs write to the same `activeLayout.name` state and call the same update path. |
| Failed name update leaves stale UI | On error, revert the input to the last known name and show a toast. |

## Success Criteria

- [ ] After creating a new layout, it appears in the toolbar dropdown menu before **Save** is pressed.
- [ ] The active layout name is editable inline in the toolbar at all times, regardless of element selection.
- [ ] Name changes persist without requiring a **Save** click.
- [ ] Element/canvas changes still require a **Save** click.
