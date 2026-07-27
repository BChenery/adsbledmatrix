/**
 * Type-aware aircraft silhouettes for the designer radar preview.
 * Mirrors backend/app/services/aircraft_icons.py so LED + web stay aligned.
 */

export type AircraftIconClass =
  | 'helicopter'
  | 'light_ga'
  | 'turboprop'
  | 'jet'
  | 'heavy'
  | 'jumbo';

export type Point = [number, number];

const TYPE_OVERRIDES: Record<string, AircraftIconClass> = {
  R22: 'helicopter',
  R44: 'helicopter',
  R66: 'helicopter',
  B06: 'helicopter',
  B06T: 'helicopter',
  B407: 'helicopter',
  B412: 'helicopter',
  B429: 'helicopter',
  EC20: 'helicopter',
  EC25: 'helicopter',
  EC30: 'helicopter',
  EC35: 'helicopter',
  EC45: 'helicopter',
  EC55: 'helicopter',
  EC75: 'helicopter',
  A109: 'helicopter',
  A119: 'helicopter',
  A139: 'helicopter',
  A169: 'helicopter',
  A189: 'helicopter',
  H60: 'helicopter',
  S92: 'helicopter',
  S76: 'helicopter',
  AS50: 'helicopter',
  AS55: 'helicopter',
  AS65: 'helicopter',
  H160: 'helicopter',
  MI8: 'helicopter',
  MI17: 'helicopter',
  C150: 'light_ga',
  C152: 'light_ga',
  C170: 'light_ga',
  C172: 'light_ga',
  C177: 'light_ga',
  C182: 'light_ga',
  C185: 'light_ga',
  C206: 'light_ga',
  C207: 'light_ga',
  C210: 'light_ga',
  PA28: 'light_ga',
  PA32: 'light_ga',
  PA38: 'light_ga',
  PA46: 'light_ga',
  P28A: 'light_ga',
  P28B: 'light_ga',
  P28R: 'light_ga',
  BE33: 'light_ga',
  BE35: 'light_ga',
  BE36: 'light_ga',
  M20P: 'light_ga',
  SR20: 'light_ga',
  SR22: 'light_ga',
  DA40: 'light_ga',
  DA20: 'light_ga',
  RV7: 'light_ga',
  RV8: 'light_ga',
  RV10: 'light_ga',
  RV12: 'light_ga',
  C208: 'turboprop',
  PC12: 'turboprop',
  TBM7: 'turboprop',
  TBM8: 'turboprop',
  TBM9: 'turboprop',
  BE20: 'turboprop',
  BE30: 'turboprop',
  B350: 'turboprop',
  DH8A: 'turboprop',
  DH8B: 'turboprop',
  DH8C: 'turboprop',
  DH8D: 'turboprop',
  AT43: 'turboprop',
  AT45: 'turboprop',
  AT72: 'turboprop',
  AT73: 'turboprop',
  AT75: 'turboprop',
  AT76: 'turboprop',
  SF34: 'turboprop',
  E120: 'turboprop',
  D328: 'turboprop',
  JS32: 'turboprop',
  JS41: 'turboprop',
  B762: 'heavy',
  B763: 'heavy',
  B764: 'heavy',
  B772: 'heavy',
  B773: 'heavy',
  B77L: 'heavy',
  B77W: 'heavy',
  B778: 'heavy',
  B779: 'heavy',
  B788: 'heavy',
  B789: 'heavy',
  B78X: 'heavy',
  A306: 'heavy',
  A30B: 'heavy',
  A310: 'heavy',
  A332: 'heavy',
  A333: 'heavy',
  A338: 'heavy',
  A339: 'heavy',
  A342: 'heavy',
  A343: 'heavy',
  A345: 'heavy',
  A346: 'heavy',
  A359: 'heavy',
  A35K: 'heavy',
  IL96: 'heavy',
  B741: 'jumbo',
  B742: 'jumbo',
  B743: 'jumbo',
  B744: 'jumbo',
  B748: 'jumbo',
  B74R: 'jumbo',
  B74S: 'jumbo',
  A124: 'jumbo',
  A225: 'jumbo',
  A380: 'jumbo',
  A388: 'jumbo',
  A3ST: 'jumbo',
};

/** Unrotated polygons (nose = up / heading 0°). */
const SYMBOLS: Record<AircraftIconClass, Point[]> = {
  jet: [
    [0, -4],
    [-3, 2],
    [-1, 1],
    [0, 3],
    [1, 1],
    [3, 2],
  ],
  light_ga: [
    [0, -5],
    [-1, -3],
    [-4, -1],
    [-1, -1],
    [-1, 3],
    [-2, 4],
    [0, 3],
    [2, 4],
    [1, 3],
    [1, -1],
    [4, -1],
    [1, -3],
  ],
  turboprop: [
    [0, -4],
    [-1, -2],
    [-4, 0],
    [-5, 1],
    [-3, 1],
    [-1, 0],
    [-1, 3],
    [-2, 4],
    [0, 3],
    [2, 4],
    [1, 3],
    [1, 0],
    [3, 1],
    [5, 1],
    [4, 0],
    [1, -2],
  ],
  heavy: [
    [0, -5],
    [-5, 2],
    [-1, 1],
    [-1, 3],
    [0, 5],
    [1, 3],
    [1, 1],
    [5, 2],
  ],
  jumbo: [
    [0, -5],
    [-1, -3],
    [-5, 1],
    [-4, 0],
    [-3, 1],
    [-1, 0],
    [-1, 3],
    [-2, 5],
    [0, 4],
    [2, 5],
    [1, 3],
    [1, 0],
    [3, 1],
    [4, 0],
    [5, 1],
    [1, -3],
  ],
  helicopter: [
    [0, -2],
    [-1, -1],
    [-5, 0],
    [-1, 0],
    [-1, 3],
    [-2, 4],
    [0, 5],
    [2, 4],
    [1, 3],
    [1, 0],
    [5, 0],
    [1, -1],
  ],
};

const HELI_NAME_RE = /helicopter|rotorcraft|gyroplane|gyrocopter|autogyro/i;
const JUMBO_NAME_RE = /\b(747|a380|an-?124|an-?225)\b/i;
const HEAVY_NAME_RE = /\b(777|787|a330|a340|a350|a300|a310|il-?96|md-?11|dc-?10)\b/i;

export function classifyAircraftIcon(
  typeCode?: string | null,
  typeName?: string | null,
): AircraftIconClass {
  const code = (typeCode || '').trim().toUpperCase();
  const name = (typeName || '').trim();

  if (code && TYPE_OVERRIDES[code]) {
    return TYPE_OVERRIDES[code];
  }

  if (name && HELI_NAME_RE.test(name)) {
    return 'helicopter';
  }

  if (name && JUMBO_NAME_RE.test(name)) {
    return 'jumbo';
  }
  if (name && HEAVY_NAME_RE.test(name)) {
    return 'heavy';
  }

  if (code) {
    if (/^(B74|A38|A12|A22)/.test(code)) return 'jumbo';
    if (/^(B77|B78|B76|A33|A34|A35|A30)/.test(code)) return 'heavy';
    if (/^(C15|C17|C18|C20|C21|PA2|P28|SR2|DA4)/.test(code)) return 'light_ga';
    if (/^(DH8|AT7|AT4|BE2|SF3|JS3|JS4|PC1|TBM)/.test(code)) return 'turboprop';
    if (/^(EC|AS5|AS6|R2|R4|R6|B40|B41|H6)/.test(code)) return 'helicopter';
    // Common narrowbody jet codes → generic jet.
    if (/^(A31|A32|A20|A21|B73|B38|B39|E17|E19|E29|CRJ|BCS)/.test(code)) return 'jet';
  }

  return 'jet';
}

export function aircraftIconPolygon(
  typeCode?: string | null,
  typeName?: string | null,
  iconClass?: AircraftIconClass | null,
): Point[] {
  const cls = iconClass || classifyAircraftIcon(typeCode, typeName);
  return SYMBOLS[cls] ?? SYMBOLS.jet;
}
