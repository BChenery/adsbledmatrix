export interface UpdateProgress {
  status:
    | 'idle'
    | 'checking'
    | 'downloading'
    | 'installing'
    | 'completed'
    | 'failed'
    | 'up_to_date'
    | 'already_running';
  progress: number;
  message: string;
  started_at?: string;
  completed_at?: string;
  error?: string;
}
