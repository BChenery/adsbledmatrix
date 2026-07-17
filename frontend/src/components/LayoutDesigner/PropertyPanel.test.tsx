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

  it('renders an Arrow Size input for heading_arrow and updates width and height', () => {
    const element: LayoutElement = {
      element_type: 'heading_arrow',
      x: 10,
      y: 10,
      z_index: 0,
      width: 40,
      height: 40,
      color: '#00ff88',
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

    const input = screen.getByLabelText('Arrow Size') as HTMLInputElement;
    expect(input).toBeDefined();
    expect(input.value).toBe('40');

    fireEvent.change(input, { target: { value: '64' } });

    expect(onChange).toHaveBeenCalledTimes(1);
    expect(onChange).toHaveBeenCalledWith({
      ...element,
      width: 64,
      height: 64,
    });
  });
});
