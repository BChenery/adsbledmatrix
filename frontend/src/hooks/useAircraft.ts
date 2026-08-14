import { useEffect, useState } from 'react';
import { api } from '@/api/client';
import { Aircraft } from '@/types/aircraft';

const RECONNECT_MS = 2000;
const REST_POLL_MS = 4000;

function websocketUrl(): string {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${protocol}//${window.location.host}/ws/aircraft`;
}

export function useAircraft() {
  const [aircraft, setAircraft] = useState<Aircraft[]>([]);

  useEffect(() => {
    let cancelled = false;
    let ws: WebSocket | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | undefined;

    const applyList = (data: unknown) => {
      if (!cancelled && Array.isArray(data)) {
        setAircraft(data as Aircraft[]);
      }
    };

    const loadRest = async () => {
      try {
        const data = await api.get<Aircraft[]>('/api/aircraft/live');
        applyList(data);
      } catch {
        // Live traffic may still arrive over the websocket.
      }
    };

    const connect = () => {
      if (cancelled) {
        return;
      }
      const socket = new WebSocket(websocketUrl());
      ws = socket;
      socket.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.type === 'aircraft') {
            applyList(msg.data);
          }
        } catch (err) {
          console.error('WebSocket parse error', err);
        }
      };
      socket.onerror = (err) => {
        console.error('WebSocket error', err);
        socket.close();
      };
      socket.onclose = () => {
        if (ws === socket) {
          ws = null;
        }
        if (!cancelled) {
          reconnectTimer = setTimeout(connect, RECONNECT_MS);
        }
      };
    };

    void loadRest();
    connect();
    const poll = setInterval(() => {
      void loadRest();
    }, REST_POLL_MS);

    return () => {
      cancelled = true;
      clearInterval(poll);
      if (reconnectTimer) {
        clearTimeout(reconnectTimer);
      }
      if (ws) {
        ws.onclose = null;
        ws.close();
      }
    };
  }, []);

  return aircraft;
}
