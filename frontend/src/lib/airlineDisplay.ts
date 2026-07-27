/**
 * Short airline brand names for designer preview.
 * Mirrors backend logo_manager.airline_display_name: callsign prefix wins
 * over registered operator (e.g. QLK on Alliance metal → "QantasLink").
 */

const IATA_TO_ICAO: Record<string, string> = {
  QF: 'QFA',
  JQ: 'JST',
  VA: 'VOZ',
  ZL: 'RXA',
  QQ: 'UTY',
  TT: 'TGW',
  TR: 'TGW',
  NZ: 'ANZ',
  AA: 'AAL',
  UA: 'UAL',
  DL: 'DAL',
  BA: 'BAW',
  SQ: 'SIA',
  EK: 'UAE',
  QR: 'QTR',
  CX: 'CPA',
  MH: 'MAS',
  FJ: 'FJI',
};

const ICAO_OVERRIDES: Record<string, string> = {
  VA: 'VOZ',
  VIR: 'VOZ',
  JQ: 'JST',
  JJP: 'JST',
  TT: 'TGW',
  TGG: 'TGW',
  NZ: 'ANZ',
};

/** Short marketing names keyed by ICAO. */
const AIRLINE_DISPLAY_NAMES: Record<string, string> = {
  QFA: 'Qantas',
  QLK: 'QantasLink',
  JST: 'Jetstar',
  VOZ: 'Virgin Australia',
  RXA: 'Rex',
  UTY: 'Alliance Airlines',
  TGW: 'Tigerair',
  ANZ: 'Air New Zealand',
  NJS: 'National Jet Systems',
  SSQ: 'Sunstate',
  EAQ: 'Eastern Australia',
  NWK: 'Network Aviation',
  FJI: 'Fiji Airways',
  BAW: 'British Airways',
  UAL: 'United',
  AAL: 'American',
  DAL: 'Delta',
  SIA: 'Singapore Airlines',
  UAE: 'Emirates',
  QTR: 'Qatar Airways',
  CPA: 'Cathay Pacific',
  MAS: 'Malaysia Airlines',
  RFDS: 'Flying Doctor',
  ANO: 'Airnorth',
};

const LEGAL_SUFFIX_RE =
  /(?:,?\s+)?(Pty\.?\s*Ltd\.?|Limited|Ltd\.?|Incorporated|Inc\.?|Corporation|Corp\.?|Co\.?|LLC|L\.?L\.?C\.?|GmbH|AG|S\.?A\.?|N\.?V\.?|B\.?V\.?|PLC|Group)\s*$/i;

function callsignPrefixToIcao(callsign: string, registration?: string | null): string | null {
  const match = callsign.toUpperCase().trim().match(/^([A-Z]{2,3})/);
  if (!match) return null;
  const prefix = match[1];
  if (prefix === 'FD') {
    const reg = (registration || '').toUpperCase().trim();
    if (reg.startsWith('HS-')) return 'AIQ';
    if (reg.startsWith('VH-') || !reg) return 'RFDS';
  }
  return IATA_TO_ICAO[prefix] || prefix;
}

function shortenOperatorName(name: string): string {
  let cleaned = name.trim();
  for (let i = 0; i < 3; i++) {
    const next = cleaned.replace(LEGAL_SUFFIX_RE, '').replace(/[ ,.-]+$/g, '').trim();
    if (next === cleaned) break;
    cleaned = next;
  }
  return cleaned;
}

export function resolveAirlineDisplayName(opts: {
  callsign?: string | null;
  operatorIcao?: string | null;
  operatorName?: string | null;
  registration?: string | null;
}): string | undefined {
  const { callsign, operatorIcao, operatorName, registration } = opts;

  let brandIcao: string | null = null;
  if (callsign) {
    const prefix = callsignPrefixToIcao(callsign, registration);
    if (prefix) {
      brandIcao = ICAO_OVERRIDES[prefix] || prefix;
    }
  }
  if (!brandIcao && operatorIcao) {
    const icao = operatorIcao.toUpperCase().trim();
    brandIcao = ICAO_OVERRIDES[icao] || icao;
  }

  if (brandIcao && AIRLINE_DISPLAY_NAMES[brandIcao]) {
    return AIRLINE_DISPLAY_NAMES[brandIcao];
  }

  if (operatorName) {
    const cleaned = shortenOperatorName(operatorName);
    return cleaned || operatorName.trim() || undefined;
  }

  return undefined;
}
