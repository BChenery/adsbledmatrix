import { useEffect, useRef, useState } from 'react';
import { api } from '@/api/client';
import { UpdateProgress } from '@/types/update';

const STATUS_POLL_INTERVAL = 1000;
const TERMINAL = new Set(['completed', 'failed', 'up_to_date']);

const STARTING_PROGRESS: UpdateProgress = {
  status: 'checking',
  progress: 0,
  message: 'Starting update...',
};

function isStaleTerminal(data: UpdateProgress, sessionStartedAt: string | null): boolean {
  if (!TERMINAL.has(data.status)) return false;
  if (!sessionStartedAt) return false;
  if (!data.started_at) return true;
  return data.started_at < sessionStartedAt;
}

export function useUpdateProgress(
  isActive: boolean,
  sessionStartedAt: string | null = null,
) {
  const [progress, setProgress] = useState<UpdateProgress | null>(null);
  const [unreachable, setUnreachable] = useState(false);
  const sessionRef = useRef(sessionStartedAt);
  sessionRef.current = sessionStartedAt;

  useEffect(() => {
    if (!isActive) {
      setProgress(null);
      setUnreachable(false);
      return;
    }

    setProgress(STARTING_PROGRESS);
    setUnreachable(false);
    let cancelled = false;
    let consecutiveFailures = 0;

    const fetchProgress = async () => {
      try {
        const data = await api.get<UpdateProgress>('/api/system/update-progress');
        if (cancelled) return;

        consecutiveFailures = 0;
        setUnreachable(false);

        if (isStaleTerminal(data, sessionRef.current)) {
          // Prior run left a finished status; keep showing "starting" until the new run writes.
          setProgress((prev) => prev ?? STARTING_PROGRESS);
          return;
        }

        setProgress(data);
      } catch {
        if (cancelled) return;
        consecutiveFailures += 1;
        // During install the app restarts — expect brief outages.
        if (consecutiveFailures >= 2) {
          setUnreachable(true);
          setProgress((prev) => ({
            status: prev?.status === 'installing' || prev?.status === 'downloading'
              ? prev.status
              : 'installing',
            progress: Math.max(prev?.progress ?? 70, 70),
            message: 'Device is restarting. Waiting for the app to come back online...',
            started_at: prev?.started_at ?? sessionRef.current ?? undefined,
          }));
        }
      }
    };

    fetchProgress();
    const id = setInterval(fetchProgress, STATUS_POLL_INTERVAL);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [isActive]);

  return { progress, unreachable };
}
