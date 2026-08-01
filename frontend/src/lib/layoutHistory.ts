import type { Layout, LayoutElement } from '@/types/layout';

const MAX_HISTORY = 50;

export function cloneLayout(layout: Layout): Layout {
  return JSON.parse(JSON.stringify(layout)) as Layout;
}

export type LayoutHistory = {
  past: Layout[];
  future: Layout[];
};

export function emptyLayoutHistory(): LayoutHistory {
  return { past: [], future: [] };
}

/** Push current layout onto the undo stack and clear redo. */
export function pushLayoutHistory(history: LayoutHistory, current: Layout): LayoutHistory {
  return {
    past: [...history.past, cloneLayout(current)].slice(-MAX_HISTORY),
    future: [],
  };
}

export type UndoResult = {
  history: LayoutHistory;
  layout: Layout;
} | null;

export function undoLayout(history: LayoutHistory, current: Layout): UndoResult {
  if (history.past.length === 0) return null;
  const previous = history.past[history.past.length - 1];
  return {
    layout: previous,
    history: {
      past: history.past.slice(0, -1),
      future: [...history.future, cloneLayout(current)],
    },
  };
}

export function redoLayout(history: LayoutHistory, current: Layout): UndoResult {
  if (history.future.length === 0) return null;
  const next = history.future[history.future.length - 1];
  return {
    layout: next,
    history: {
      past: [...history.past, cloneLayout(current)].slice(-MAX_HISTORY),
      future: history.future.slice(0, -1),
    },
  };
}

/** Prefer the element at the same index after an undo/redo restore. */
export function reselectElement(
  layout: Layout,
  previousSelected: LayoutElement | null,
  previousLayout: Layout | null,
): LayoutElement | null {
  if (!previousSelected || !previousLayout) return null;
  const idx = previousLayout.elements.indexOf(previousSelected);
  if (idx >= 0 && idx < layout.elements.length) {
    return layout.elements[idx];
  }
  return null;
}

/** True when Ctrl/Cmd+Z should be handled by the browser (text field), not the designer. */
export function isEditableKeyboardTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  const tag = target.tagName;
  if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return true;
  if (target.isContentEditable) return true;
  return Boolean(target.closest('[contenteditable="true"]'));
}
