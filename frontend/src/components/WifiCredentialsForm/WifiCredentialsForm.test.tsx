import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import WifiCredentialsForm from './WifiCredentialsForm';

vi.mock('@/api/client', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
  },
}));

import { api } from '@/api/client';
const mockGet = api.get as ReturnType<typeof vi.fn>;

function renderForm(props: Partial<Parameters<typeof WifiCredentialsForm>[0]> = {}) {
  const defaults = {
    ssid: '',
    password: '',
    onSsidChange: vi.fn(),
    onPasswordChange: vi.fn(),
  };
  return render(<WifiCredentialsForm {...defaults} {...props} />);
}

describe('WifiCredentialsForm', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it('renders scanned networks and fills the SSID on tap', async () => {
    mockGet.mockResolvedValue({
      networks: [{ ssid: 'HomeNet', signal: 82, secured: true }],
      error: null,
    });
    const onSsidChange = vi.fn();
    renderForm({ onSsidChange });

    const network = await screen.findByText('HomeNet');
    fireEvent.click(network);
    expect(onSsidChange).toHaveBeenCalledWith('HomeNet');
  });

  it('falls back to manual entry when the scan fails', async () => {
    mockGet.mockRejectedValue(new Error('boom'));
    renderForm();

    expect(await screen.findByText(/type your network name below/i)).toBeDefined();
  });

  it('shows an inline error for passwords under 8 characters', () => {
    renderForm({ password: 'abc' });
    expect(screen.getByText(/at least 8 characters/i)).toBeDefined();
  });

  it('does not complain about an empty password (hint only on submit)', () => {
    renderForm({ password: '' });
    expect(screen.queryByText(/at least 8 characters/i)).toBeNull();
  });

  it('toggles password visibility', () => {
    renderForm({ password: 'supersecret' });
    const input = screen.getByLabelText('Password') as HTMLInputElement;
    expect(input.type).toBe('password');

    fireEvent.click(screen.getByLabelText('Show password'));
    expect(input.type).toBe('text');

    fireEvent.click(screen.getByLabelText('Hide password'));
    expect(input.type).toBe('password');
  });
});
