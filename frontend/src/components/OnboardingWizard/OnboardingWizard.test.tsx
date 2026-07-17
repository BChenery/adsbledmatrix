import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import OnboardingWizard from './OnboardingWizard';

vi.mock('@/api/client', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
  },
}));

import { api } from '@/api/client';
const mockGet = api.get as ReturnType<typeof vi.fn>;
const mockPost = api.post as ReturnType<typeof vi.fn>;
const mockPut = api.put as ReturnType<typeof vi.fn>;

const LAYOUTS = [
  { id: 7, name: 'Minimal', description: 'Just the essentials', is_default: false },
];

function mockApis({ applyFails = false }: { applyFails?: boolean } = {}) {
  const calls: string[] = [];
  mockGet.mockImplementation((path: string) => {
    if (path === '/api/layouts') return Promise.resolve(LAYOUTS);
    if (path === '/api/layouts/7') {
      return Promise.resolve({
        id: 7,
        name: 'Minimal',
        width: 256,
        height: 128,
        is_default: false,
        elements: [],
      });
    }
    if (path === '/api/system/wifi/networks') return Promise.resolve({ networks: [], error: null });
    return Promise.reject(new Error(`unexpected GET ${path}`));
  });
  mockPut.mockImplementation(() => {
    calls.push('put:/api/config');
    return Promise.resolve({ onboarding_complete: true });
  });
  mockPost.mockImplementation((path: string) => {
    calls.push(`post:${path}`);
    if (path === '/api/system/wifi/apply' && applyFails) {
      return Promise.reject(new Error('apply failed'));
    }
    return Promise.resolve({});
  });
  return calls;
}

async function walkToWifiStep() {
  fireEvent.click(screen.getByText('Get Started'));
  fireEvent.change(screen.getByLabelText('Latitude'), { target: { value: '51.5074' } });
  fireEvent.change(screen.getByLabelText('Longitude'), { target: { value: '-0.1278' } });
  fireEvent.click(screen.getByText('Continue'));
  fireEvent.click(await screen.findByText('Minimal'));
  fireEvent.click(screen.getByText('Continue'));
  await screen.findByLabelText('Network Name (SSID)');
}

function fillWifi() {
  fireEvent.change(screen.getByLabelText('Network Name (SSID)'), { target: { value: 'HomeNet' } });
  fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'supersecret' } });
}

describe('OnboardingWizard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it('shows an inline error for invalid coordinates instead of failing silently', () => {
    render(<OnboardingWizard config={null} />);
    fireEvent.click(screen.getByText('Get Started'));

    fireEvent.change(screen.getByLabelText('Latitude'), { target: { value: '123' } });
    fireEvent.change(screen.getByLabelText('Longitude'), { target: { value: '0' } });

    expect(screen.getByText(/between -90 and 90/i)).toBeDefined();
    expect((screen.getByText('Continue') as HTMLButtonElement).disabled).toBe(true);
  });

  it('requires a layout selection before continuing when layouts exist', async () => {
    mockApis();
    render(<OnboardingWizard config={null} />);
    fireEvent.click(screen.getByText('Get Started'));
    fireEvent.change(screen.getByLabelText('Latitude'), { target: { value: '51.5074' } });
    fireEvent.change(screen.getByLabelText('Longitude'), { target: { value: '-0.1278' } });
    fireEvent.click(screen.getByText('Continue'));

    await screen.findByText('Minimal');
    expect((screen.getByText('Continue') as HTMLButtonElement).disabled).toBe(true);

    fireEvent.click(screen.getByText('Minimal'));
    expect((screen.getByText('Continue') as HTMLButtonElement).disabled).toBe(false);
  });

  it('saves config (with layout) before triggering the WiFi switch, then shows All Set', async () => {
    const calls = mockApis();
    render(<OnboardingWizard config={null} />);
    await walkToWifiStep();
    fillWifi();

    fireEvent.click(screen.getByText('Finish Setup'));

    expect(await screen.findByText('All Set!')).toBeDefined();
    expect(calls.indexOf('put:/api/config')).toBeGreaterThanOrEqual(0);
    expect(calls.indexOf('put:/api/config')).toBeLessThan(calls.indexOf('post:/api/system/wifi/apply'));

    const putBody = mockPut.mock.calls[0][1] as Record<string, unknown>;
    expect(putBody.onboarding_complete).toBe(true);
    expect(putBody.active_layout_id).toBe(7);
    expect(putBody.wifi_ssid).toBe('HomeNet');
    // matrix live-preview was requested when the layout was picked
    expect(calls).toContain('post:/api/display/apply-layout');
  });

  it('returns to the WiFi step with an error if the network switch fails', async () => {
    mockApis({ applyFails: true });
    render(<OnboardingWizard config={null} />);
    await walkToWifiStep();
    fillWifi();

    fireEvent.click(screen.getByText('Finish Setup'));

    expect(await screen.findByText(/could not start/i)).toBeDefined();
    expect(screen.queryByText('All Set!')).toBeNull();
    expect(screen.getByText('Finish Setup')).toBeDefined();
  });
});
