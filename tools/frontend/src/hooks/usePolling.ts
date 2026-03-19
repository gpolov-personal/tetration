import { useCallback, useEffect, useRef, useState } from 'react';

export function usePolling<T>(
  fetchFn: (signal: AbortSignal) => Promise<T>,
  intervalMs: number,
  enabled = true,
) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [loading, setLoading] = useState(true);
  const fetchRef = useRef(fetchFn);
  fetchRef.current = fetchFn;

  const tick = useCallback(async (signal: AbortSignal) => {
    try {
      const result = await fetchRef.current(signal);
      if (!signal.aborted) {
        setData(result);
        setError(null);
      }
    } catch (err) {
      if (!signal.aborted) {
        setError(err instanceof Error ? err : new Error(String(err)));
      }
    } finally {
      if (!signal.aborted) setLoading(false);
    }
  }, []);

  const [refreshKey, setRefreshKey] = useState(0);
  const refresh = useCallback(() => setRefreshKey((k) => k + 1), []);

  useEffect(() => {
    if (!enabled) return;

    const ac = new AbortController();
    tick(ac.signal);

    const id = setInterval(() => {
      if (document.visibilityState === 'hidden') return;
      tick(ac.signal);
    }, intervalMs);

    return () => {
      ac.abort();
      clearInterval(id);
    };
  }, [enabled, intervalMs, tick, refreshKey]);

  return { data, error, loading, refresh };
}
