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
