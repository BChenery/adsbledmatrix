import { useEffect, useState } from 'react';
import { Aircraft } from '@/types/aircraft';

export function useAircraft() {
  const [aircraft, setAircraft] = useState<Aircraft[]>([]);

  useEffect(() => {
    const ws = new WebSocket(`${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws/aircraft`);
    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      if (msg.type === 'aircraft') {
        setAircraft(msg.data);
      }
    };
    ws.onerror = (err) => console.error('WebSocket error', err);
    return () => ws.close();
  }, []);

  return aircraft;
}
