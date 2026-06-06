export interface UserConfig {
  latitude: number;
  longitude: number;
  distance_unit: string;
  altitude_unit: string;
  speed_unit: string;
  cycle_interval_sec: number;
  display_mode: string;
  active_layout_id?: number;
  idle_layout_id?: number;
  onboarding_complete: boolean;
  wifi_ssid?: string;
  auto_update: boolean;
  night_mode: boolean;
  night_mode_start?: string;
  night_mode_end?: string;
}
