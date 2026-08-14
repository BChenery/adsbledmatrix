import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { useAircraft } from './useAircraft';
import { api } from '@/api/client';

vi.mock('@/api/client', () => ({
  api: {
    get: vi.fn(),
  },
}));

type Listener = (event?: unknown) => void;

class FakeWebSocket {
  static instances: FakeWebSocket[] = [];
  static readonly OPEN = 1;
  readyState = FakeWebSocket.OPEN;
  onmessage: Listener | null = null;
  onerror: Listener | null = null;
  onclose: Listener | null = null;

  constructor(public url: string) {
    FakeWebSocket.instances.push(this);
  }

  close() {
    this.onclose?.({});
  }

  emitAircraft(data: unknown[]) {
    this.onmessage?.({ data: JSON.stringify({ type: 'aircraft', data }) });
  }
}

describe('useAircraft', () => {
  const originalWebSocket = globalThis.WebSocket;

  beforeEach(() => {
    FakeWebSocket.instances = [];
    vi.mocked(api.get).mockReset();
    // @ts-expect-error test double
    globalThis.WebSocket = FakeWebSocket;
  });

  afterEach(() => {
    globalThis.WebSocket = originalWebSocket;
  });

  it('seeds the live list from the REST API', async () => {
    vi.mocked(api.get).mockResolvedValue([
      { hex_code: '7C78A8', callsign: 'QLK1516', last_seen: '2026-08-14T21:36:06', messages: 3 },
    ]);

    const { result, unmount } = renderHook(() => useAircraft());

    await waitFor(() => {
      expect(result.current).toHaveLength(1);
    });
    expect(result.current[0].callsign).toBe('QLK1516');
    expect(api.get).toHaveBeenCalledWith('/api/aircraft/live');
    expect(FakeWebSocket.instances[0].url).toContain('/ws/aircraft');
    unmount();
  });

  it('replaces the list when the websocket pushes aircraft', async () => {
    vi.mocked(api.get).mockResolvedValue([]);

    const { result, unmount } = renderHook(() => useAircraft());
    await waitFor(() => {
      expect(FakeWebSocket.instances).toHaveLength(1);
    });

    act(() => {
      FakeWebSocket.instances[0].emitAircraft([
        { hex_code: 'ABC123', callsign: 'QFA10', last_seen: '2026-08-14T21:36:06', messages: 1 },
      ]);
    });

    await waitFor(() => {
      expect(result.current[0].callsign).toBe('QFA10');
    });
    unmount();
  });
});
