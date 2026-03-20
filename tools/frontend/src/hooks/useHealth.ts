import { useCallback } from 'react';
import { api } from '../api/client';
import type { HealthResponse } from '../api/types';
import { usePolling } from './usePolling';

export function useHealth(intervalMs = 10000) {
  const fetcher = useCallback((signal: AbortSignal) => api.health(signal), []);
  const { data, error, loading } = usePolling<HealthResponse>(fetcher, intervalMs);
  return {
    healthy: data !== null && error === null,
    version: data?.version ?? null,
    error,
    loading,
  };
}
