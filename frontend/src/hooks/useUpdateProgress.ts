import { useEffect, useState } from 'react';
import { api } from '@/api/client';
import { UpdateProgress } from '@/types/update';

const STATUS_POLL_INTERVAL = 2000;

export function useUpdateProgress(isActive: boolean) {
  const [progress, setProgress] = useState<UpdateProgress | null>(null);

  useEffect(() => {
    if (!isActive) {
      setProgress(null);
      return;
    }

    let cancelled = false;

    const fetchProgress = async () => {
      try {
        const data = await api.get<UpdateProgress>('/api/system/update-progress');
        if (!cancelled) setProgress(data);
      } catch {
        if (!cancelled) {
          setProgress({
            status: 'failed',
            progress: 0,
            message: 'Unable to read update progress.',
          });
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

  return progress;
}
