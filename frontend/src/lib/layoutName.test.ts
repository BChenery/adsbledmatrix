import { describe, it, expect } from 'vitest';
import { normalizeLayoutName, uniqueCopyName } from './layoutName';

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

describe('uniqueCopyName', () => {
  it('appends (copy) when free', () => {
    expect(uniqueCopyName('Flight Board', [])).toBe('Flight Board (copy)');
    expect(uniqueCopyName('Flight Board', ['Other'])).toBe('Flight Board (copy)');
  });

  it('increments when (copy) already exists', () => {
    expect(
      uniqueCopyName('Flight Board', ['Flight Board', 'Flight Board (copy)'])
    ).toBe('Flight Board (copy 2)');
  });

  it('skips taken numbered copies', () => {
    expect(
      uniqueCopyName('A', ['A (copy)', 'A (copy 2)', 'A (copy 3)'])
    ).toBe('A (copy 4)');
  });

  it('trims the base name before appending', () => {
    expect(uniqueCopyName('  Radar  ', [])).toBe('Radar (copy)');
  });

  it('falls back for blank base names', () => {
    expect(uniqueCopyName('   ', ['Untitled Layout (copy)'])).toBe(
      'Untitled Layout (copy 2)'
    );
  });
});
