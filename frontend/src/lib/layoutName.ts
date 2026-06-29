export function normalizeLayoutName(
  name: string,
  fallback = 'Untitled Layout'
): string {
  const trimmed = name.trim();
  return trimmed || fallback;
}
