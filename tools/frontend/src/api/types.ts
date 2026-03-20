export interface TaskRequest {
  name: string;
  prompt: string;
  cron_expr: string;
  scheduled_at?: string;
  working_dir: string;
  discord_webhook?: string;
  slack_webhook?: string;
  enabled: boolean;
}

export interface TaskResponse {
  id: number;
  name: string;
  prompt: string;
  cron_expr: string;
  scheduled_at?: string;
  working_dir: string;
  discord_webhook?: string;
  slack_webhook?: string;
  enabled: boolean;
  is_one_off: boolean;
  created_at: string;
  updated_at: string;
  last_run_at?: string;
  next_run_at?: string;
  last_run_status?: string;
}

export interface TaskRunResponse {
  id: number;
  task_id: number;
  started_at: string;
  ended_at?: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  output: string;
  error?: string;
  duration_ms?: number;
}

export interface TaskListResponse {
  tasks: TaskResponse[];
  total: number;
}

export interface TaskRunListResponse {
  runs: TaskRunResponse[];
  total: number;
}

export interface HealthResponse {
  status: string;
  version: string;
}

export interface UsageResponse {
  five_hour: { utilization: number; resets_at: string };
  seven_day: { utilization: number; resets_at: string };
}
