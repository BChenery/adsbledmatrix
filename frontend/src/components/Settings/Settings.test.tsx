import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import Settings from './Settings';
import * as apiModule from '@/api/client';
import type { UserConfig } from '@/types/config';

const mockConfig: UserConfig = {
  receiver_source: 'local',
  network_readsb_host: '',
  network_readsb_port: 30005,
  led_matrix_brightness: 50,
  display_mode: 'closest',
  cycle_interval_sec: 5,
  cycle_count: 3,
  proximity_focus_enabled: false,
  proximity_focus_km: 3,
  proximity_focus_layout_id: null,
  layout_rotation_enabled: false,
  layout_playlist_ids: [],
  layout_rotation_interval_sec: 30,
  interesting_alerts_enabled: true,
  interesting_record_range_km: 50,
  interesting_rare_sightings: 3,
  interesting_absent_days: 30,
  interesting_warmup_days: 7,
  interesting_layout_id: null,
  interesting_hold_sec: 8,
  active_layout_id: 1,
  idle_layout_id: 2,
  latitude: -33.8688,
  longitude: 151.2093,
  distance_unit: 'km',
  altitude_unit: 'ft',
  speed_unit: 'kts',
  night_mode: false,
  night_mode_start: '22:00',
  night_mode_end: '06:00',
  sleep_mode: false,
  sleep_mode_start: '23:00',
  sleep_mode_end: '06:00',
  auto_update: false,
  onboarding_complete: true,
  timezone: 'Australia/Sydney',
};

vi.mock('@/api/client', () => ({
  api: {
    get: vi.fn(),
    put: vi.fn(),
    post: vi.fn(),
  },
}));

vi.mock('@/hooks/useDisplayStatus', () => ({
  useDisplayStatus: () => null,
}));

vi.mock('@/hooks/useDisplayPreview', () => ({
  useDisplayPreview: () => ({ url: null, error: null }),
}));

vi.mock('@/hooks/useDisplayDiagnostics', () => ({
  useDisplayDiagnostics: () => null,
}));

vi.mock('@/hooks/useLayout', () => ({
  useLayouts: () => ({ layouts: [], loading: false, error: null, refresh: vi.fn() }),
}));

vi.mock('@/hooks/useAircraft', () => ({
  useAircraft: () => [],
}));

vi.mock('@/hooks/useReceiverStatus', () => ({
  useReceiverStatus: () => null,
}));

vi.mock('@/hooks/useUpdateProgress', () => ({
  useUpdateProgress: () => ({ progress: null, unreachable: false }),
}));

vi.mock('@/components/LocationLookup/LocationLookup', () => ({
  default: () => <div data-testid="location-lookup">LocationLookup</div>,
}));

describe('Settings', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(apiModule.api.get).mockImplementation((url: string) => {
      if (url === '/api/config') {
        return Promise.resolve(mockConfig);
      }
      if (url === '/api/system/update') {
        return Promise.resolve({
          current_version: '1.0.0',
          latest_version: '1.0.0',
          update_available: false,
        });
      }
      return Promise.reject(new Error('Unknown URL'));
    });
  });

  it('renders settings sections and save button', async () => {
    render(<Settings />);

    expect(await screen.findByRole('heading', { name: /Settings/i })).toBeDefined();
    expect(screen.getByText('LED Matrix Status')).toBeDefined();
    expect(screen.getByText('Receiver')).toBeDefined();
    expect(screen.getByText('Display')).toBeDefined();
    expect(screen.getByText('Location & Units')).toBeDefined();
    expect(screen.getByText('Night Mode')).toBeDefined();
    expect(screen.getByText('System')).toBeDefined();
    expect(screen.getByRole('button', { name: /Save Settings/i })).toBeDefined();
  });

  it('shows cycle count when cycle mode is selected', async () => {
    vi.mocked(apiModule.api.get).mockImplementation((url: string) => {
      if (url === '/api/config') {
        return Promise.resolve({ ...mockConfig, display_mode: 'cycle' });
      }
      if (url === '/api/system/update') {
        return Promise.resolve({
          current_version: '1.0.0',
          latest_version: '1.0.0',
          update_available: false,
        });
      }
      return Promise.reject(new Error('Unknown URL'));
    });

    render(<Settings />);
    expect(await screen.findByText('Number of aircraft to cycle')).toBeDefined();
    expect(screen.getByText('Switch aircraft every')).toBeDefined();
  });

  it('shows proximity distance when proximity focus is enabled', async () => {
    vi.mocked(apiModule.api.get).mockImplementation((url: string) => {
      if (url === '/api/config') {
        return Promise.resolve({ ...mockConfig, proximity_focus_enabled: true });
      }
      if (url === '/api/system/update') {
        return Promise.resolve({
          current_version: '1.0.0',
          latest_version: '1.0.0',
          update_available: false,
        });
      }
      return Promise.reject(new Error('Unknown URL'));
    });

    render(<Settings />);
    expect(await screen.findByText('Focus distance')).toBeDefined();
    expect(screen.getByText('Focus layout (optional)')).toBeDefined();
  });
});
