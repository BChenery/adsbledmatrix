export function normalizeLayoutName(
  name: string,
  fallback = 'Untitled Layout'
): string {
  const trimmed = name.trim();
  return trimmed || fallback;
}

/**
 * Build a unique name for a duplicated layout.
 * "Flight Board" → "Flight Board (copy)" → "Flight Board (copy 2)" …
 */
export function uniqueCopyName(
  baseName: string,
  existingNames: Iterable<string>
): string {
  const names = new Set(existingNames);
  const base = normalizeLayoutName(baseName, 'Untitled Layout');
  const first = `${base} (copy)`;
  if (!names.has(first)) return first;
  let n = 2;
  while (names.has(`${base} (copy ${n})`)) {
    n += 1;
  }
  return `${base} (copy ${n})`;
}
