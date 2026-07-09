export type UpdateProgressStatus =
  | 'idle'
  | 'checking'
  | 'downloading'
  | 'installing'
  | 'completed'
  | 'failed'
  | 'up_to_date'
  | 'already_running';

export interface UpdateProgress {
  status: UpdateProgressStatus;
  progress: number;
  message: string;
  started_at?: string;
  completed_at?: string;
  error?: string;
}

export const UPDATE_STAGES: { key: UpdateProgressStatus; label: string; min: number }[] = [
  { key: 'checking', label: 'Check', min: 0 },
  { key: 'downloading', label: 'Download', min: 25 },
  { key: 'installing', label: 'Install', min: 40 },
  { key: 'completed', label: 'Done', min: 100 },
];
