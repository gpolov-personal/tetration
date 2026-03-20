import { useCallback } from 'react';
import { api } from '../api/client';
import type { TaskResponse, TaskRunResponse } from '../api/types';
import { usePolling } from './usePolling';

export function useTaskDetail(taskId: number | null) {
  const taskFetcher = useCallback(
    (signal: AbortSignal) => api.getTask(taskId!, signal),
    [taskId],
  );
  const runFetcher = useCallback(
    (signal: AbortSignal) => api.getLatestRun(taskId!, signal),
    [taskId],
  );

  const enabled = taskId !== null;
  const task = usePolling<TaskResponse>(taskFetcher, 5000, enabled);
  const latestRun = usePolling<TaskRunResponse>(runFetcher, 3000, enabled);

  return { task, latestRun };
}
