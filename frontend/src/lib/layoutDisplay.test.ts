import { describe, it, expect } from 'vitest';
import { getAircraftDisplayValue } from './layoutDisplay';
import type { Aircraft } from '@/types/aircraft';
import type { LayoutElement } from '@/types/layout';

describe('getAircraftDisplayValue', () => {
  it('handles null distance_km in a data_field without crashing', () => {
    const ac = {
      hex_code: 'NULLDIST',
      last_seen: new Date().toISOString(),
      messages: 0,
      distance_km: null,
    } as unknown as Aircraft;

    const el: LayoutElement = {
      element_type: 'data_field',
      x: 0,
      y: 0,
      z_index: 0,
      data_field: 'distance',
      format_str: '{distance}',
    };

    expect(() => getAircraftDisplayValue(ac, el)).not.toThrow();
    expect(getAircraftDisplayValue(ac, el)).toBe('');
  });
});
