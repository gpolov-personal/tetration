import { useCallback } from 'react';
import { api } from '../api/client';
import type { TaskListResponse } from '../api/types';
import { usePolling } from './usePolling';

export function useTasks(intervalMs = 5000) {
  const fetcher = useCallback((signal: AbortSignal) => api.listTasks(signal), []);
  const { data, error, loading, refresh } = usePolling<TaskListResponse>(fetcher, intervalMs);
  return {
    tasks: data?.tasks ?? [],
    total: data?.total ?? 0,
    error,
    loading,
    refresh,
  };
}
