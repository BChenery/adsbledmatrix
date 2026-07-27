import { describe, expect, it } from 'vitest';
import { resolveAirlineDisplayName } from './airlineDisplay';
import { getAircraftDisplayValue } from './layoutDisplay';
import type { Aircraft } from '@/types/aircraft';
import type { LayoutElement } from '@/types/layout';

describe('resolveAirlineDisplayName', () => {
  it('uses QantasLink for QLK callsign even when operator is Alliance', () => {
    expect(
      resolveAirlineDisplayName({
        callsign: 'QLK2341',
        operatorIcao: 'UTY',
        operatorName: 'Alliance Airlines Pty Limited',
      }),
    ).toBe('QantasLink');
  });

  it('uses short Qantas brand for QF/QFA callsigns', () => {
    expect(
      resolveAirlineDisplayName({
        callsign: 'QFA123',
        operatorIcao: 'QFA',
        operatorName: 'Qantas Airways Pty Ltd',
      }),
    ).toBe('Qantas');
  });

  it('uses Virgin Australia for VOZ callsign on Alliance metal', () => {
    expect(
      resolveAirlineDisplayName({
        callsign: 'VOZ99',
        operatorIcao: 'UTY',
        operatorName: 'Alliance Airlines Pty Limited',
      }),
    ).toBe('Virgin Australia');
  });

  it('shortens legal operator names when no callsign is present', () => {
    expect(
      resolveAirlineDisplayName({
        operatorName: 'Qantas Airways Pty Ltd',
      }),
    ).toBe('Qantas Airways');
  });
});

describe('layoutDisplay airline field', () => {
  it('renders {airline} from callsign brand when airline is not precomputed', () => {
    const ac = {
      hex_code: '7C7A01',
      last_seen: new Date().toISOString(),
      messages: 1,
      callsign: 'QLK2341',
      operator_icao: 'UTY',
      operator: 'Alliance Airlines Pty Limited',
    } as Aircraft;

    const el: LayoutElement = {
      element_type: 'data_field',
      x: 0,
      y: 0,
      z_index: 0,
      data_field: 'airline',
      format_str: '{airline}',
    };

    expect(getAircraftDisplayValue(ac, el)).toBe('QantasLink');
  });
});
