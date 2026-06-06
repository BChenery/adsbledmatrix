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
  operator?: string;
  operator_icao?: string;
  route?: string;
  origin?: string;
  destination?: string;
}
