export interface Aircraft {
  hex_code: string;
  callsign?: string;
  latitude?: number;
  longitude?: number;
  altitude?: number;
  ground_speed?: number;
  heading?: number;
  vertical_rate?: number;
  squawk?: string;
  distance_km?: number;
  distance_display?: string;
  bearing?: number;
  last_seen: string;
  messages: number;
  registration?: string;
  manufacturer?: string;
  model?: string;
  type_code?: string;
  type_name?: string;
  operator?: string;
  operator_icao?: string;
  /** Short brand name (callsign-first). Prefer over full legal operator. */
  airline?: string;
  route?: string;
  origin?: string;
  destination?: string;
  /** 3-letter IATA for origin (e.g. BNE from YBBN). */
  origin_iata?: string;
  /** 3-letter IATA for destination. */
  destination_iata?: string;
  /** City name for origin (e.g. Brisbane). */
  origin_city?: string;
  /** City name for destination. */
  destination_city?: string;
}
