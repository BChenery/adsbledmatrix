import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import WhatsNew from './WhatsNew';
import * as apiModule from '@/api/client';
import type { ChangelogResponse } from '@/types/changelog';

vi.mock('@/api/client', () => ({
  api: {
    get: vi.fn(),
    put: vi.fn(),
    post: vi.fn(),
  },
}));

const sample: ChangelogResponse = {
  current_version: '0.1.40',
  entries: [
    {
      version: '0.1.40',
      date: '2026-07-15',
      sections: [
        {
          title: 'Added',
          items: ['Apply vs Save in the designer', 'Text clips like the LED matrix'],
        },
      ],
    },
    {
      version: '0.1.39',
      date: '2026-07-14',
      sections: [{ title: 'Fixed', items: ['Pause yellow flashes'] }],
    },
  ],
};

function renderPage() {
  return render(
    <MemoryRouter>
      <WhatsNew />
    </MemoryRouter>,
  );
}

describe('WhatsNew', () => {
  beforeEach(() => {
    vi.mocked(apiModule.api.get).mockReset();
  });

  it('renders changelog entries from the API', async () => {
    vi.mocked(apiModule.api.get).mockResolvedValue(sample);

    renderPage();

    await waitFor(() => {
      expect(screen.getByText("What's new")).toBeTruthy();
    });

    expect(screen.getByText('v0.1.40')).toBeTruthy();
    expect(screen.getByText('Installed')).toBeTruthy();
    expect(screen.getByText('Apply vs Save in the designer')).toBeTruthy();
    expect(screen.getByText('running v0.1.40')).toBeTruthy();
    expect(apiModule.api.get).toHaveBeenCalledWith('/api/system/changelog');
  });

  it('shows an empty state when there are no entries', async () => {
    vi.mocked(apiModule.api.get).mockResolvedValue({
      current_version: '0.1.0',
      entries: [],
    });

    renderPage();

    await waitFor(() => {
      expect(screen.getByText('No release notes yet')).toBeTruthy();
    });
  });

  it('shows an error when the API fails', async () => {
    vi.mocked(apiModule.api.get).mockRejectedValue(new Error('network'));

    renderPage();

    await waitFor(() => {
      expect(screen.getByText(/Could not load release notes/i)).toBeTruthy();
    });
  });
});
