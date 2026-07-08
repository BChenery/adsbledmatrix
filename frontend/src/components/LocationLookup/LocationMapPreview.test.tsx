import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import LocationMapPreview from './LocationMapPreview';

describe('LocationMapPreview', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('shows placeholder for unset 0,0 coordinates', () => {
    render(<LocationMapPreview latitude={0} longitude={0} />);
    expect(
      screen.getByText(/Enter a valid latitude and longitude/i),
    ).toBeDefined();
    expect(screen.queryByTitle('Receiver location map')).toBeNull();
  });

  it('renders map iframe after debounce for valid coordinates', () => {
    render(<LocationMapPreview latitude={-33.8688} longitude={151.2093} />);

    act(() => {
      vi.advanceTimersByTime(450);
    });

    const iframe = screen.getByTitle('Receiver location map') as HTMLIFrameElement;
    expect(iframe).toBeDefined();
    expect(iframe.src).toContain('openstreetmap.org/export/embed.html');
    expect(iframe.src).toContain(encodeURIComponent('-33.8688,151.2093'));
  });
});
