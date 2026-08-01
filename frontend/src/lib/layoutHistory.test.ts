import { describe, expect, it } from 'vitest';
import {
  cloneLayout,
  emptyLayoutHistory,
  pushLayoutHistory,
  redoLayout,
  undoLayout,
  reselectElement,
  isEditableKeyboardTarget,
} from './layoutHistory';
import type { Layout } from '@/types/layout';

const base: Layout = {
  name: 'Test',
  width: 256,
  height: 128,
  is_default: false,
  elements: [
    { element_type: 'text', x: 0, y: 0, z_index: 0, format_str: 'A' },
    { element_type: 'text', x: 10, y: 10, z_index: 1, format_str: 'B' },
  ],
};

describe('layoutHistory', () => {
  it('cloneLayout deep-copies elements', () => {
    const copy = cloneLayout(base);
    expect(copy).toEqual(base);
    expect(copy).not.toBe(base);
    expect(copy.elements).not.toBe(base.elements);
    copy.elements[0].x = 99;
    expect(base.elements[0].x).toBe(0);
  });

  it('undo restores previous layout and enables redo', () => {
    let history = emptyLayoutHistory();
    const v1 = base;
    const v2 = { ...base, name: 'Edited' };

    history = pushLayoutHistory(history, v1);
    const undone = undoLayout(history, v2);
    expect(undone).not.toBeNull();
    expect(undone!.layout.name).toBe('Test');
    expect(undone!.history.past).toHaveLength(0);
    expect(undone!.history.future).toHaveLength(1);

    const redone = redoLayout(undone!.history, undone!.layout);
    expect(redone).not.toBeNull();
    expect(redone!.layout.name).toBe('Edited');
  });

  it('push clears the redo stack', () => {
    let history = emptyLayoutHistory();
    history = pushLayoutHistory(history, base);
    const mid = undoLayout(history, { ...base, name: 'B' })!;
    history = pushLayoutHistory(mid.history, mid.layout);
    expect(history.future).toHaveLength(0);
  });

  it('reselectElement keeps the same index after restore', () => {
    const el = base.elements[1];
    const restored: Layout = {
      ...base,
      elements: base.elements.map((e) => ({ ...e, x: e.x + 1 })),
    };
    const picked = reselectElement(restored, el, base);
    expect(picked).toBe(restored.elements[1]);
    expect(picked?.x).toBe(11);
  });

  it('isEditableKeyboardTarget detects inputs', () => {
    const input = document.createElement('input');
    expect(isEditableKeyboardTarget(input)).toBe(true);
    expect(isEditableKeyboardTarget(document.createElement('div'))).toBe(false);
  });
});
