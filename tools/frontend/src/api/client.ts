import type {
  HealthResponse,
  TaskListResponse,
  TaskRequest,
  TaskResponse,
  TaskRunListResponse,
  TaskRunResponse,
  UsageResponse,
} from './types';

const BASE = '/api/v1';

async function request<T>(
  path: string,
  init?: RequestInit,
  signal?: AbortSignal,
): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { ...init, signal });
  if (!res.ok) {
    const body = await res.text().catch(() => '');
    throw new Error(`${res.status} ${res.statusText}: ${body}`);
  }
  return res.json();
}

function json(body: unknown): RequestInit {
  return {
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  };
}

export const api = {
  health(signal?: AbortSignal) {
    return request<HealthResponse>('/health', undefined, signal);
  },

  listTasks(signal?: AbortSignal) {
    return request<TaskListResponse>('/tasks', undefined, signal);
  },

  getTask(id: number, signal?: AbortSignal) {
    return request<TaskResponse>(`/tasks/${id}`, undefined, signal);
  },

  createTask(data: TaskRequest, signal?: AbortSignal) {
    return request<TaskResponse>('/tasks', { method: 'POST', ...json(data) }, signal);
  },

  updateTask(id: number, data: TaskRequest, signal?: AbortSignal) {
    return request<TaskResponse>(`/tasks/${id}`, { method: 'PUT', ...json(data) }, signal);
  },

  deleteTask(id: number, signal?: AbortSignal) {
    return request<{ success: boolean }>(`/tasks/${id}`, { method: 'DELETE' }, signal);
  },

  toggleTask(id: number, signal?: AbortSignal) {
    return request<TaskResponse>(`/tasks/${id}/toggle`, { method: 'POST' }, signal);
  },

  runTask(id: number, signal?: AbortSignal) {
    return request<{ success: boolean; message: string }>(
      `/tasks/${id}/run`,
      { method: 'POST' },
      signal,
    );
  },

  getTaskRuns(id: number, limit = 20, signal?: AbortSignal) {
    return request<TaskRunListResponse>(`/tasks/${id}/runs?limit=${limit}`, undefined, signal);
  },

  getLatestRun(id: number, signal?: AbortSignal) {
    return request<TaskRunResponse>(`/tasks/${id}/runs/latest`, undefined, signal);
  },

  getUsage(signal?: AbortSignal) {
    return request<UsageResponse>('/usage', undefined, signal);
  },
};
