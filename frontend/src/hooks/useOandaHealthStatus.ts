import { useEffect } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '../config/reactQuery';
import { healthApi } from '../services/api';

interface UseOandaHealthStatusOptions {
  enabled: boolean;
  refreshIntervalMs: number;
  activeCheck?: boolean;
}

export function useOandaHealthStatus({
  enabled,
  refreshIntervalMs,
  activeCheck = false,
}: UseOandaHealthStatusOptions) {
  const queryClient = useQueryClient();

  const query = useQuery({
    queryKey: queryKeys.health.oanda(),
    queryFn: () => healthApi.getOandaStatus(),
    enabled,
    staleTime: refreshIntervalMs,
    retry: false,
  });

  useEffect(() => {
    if (!enabled || !activeCheck) {
      return;
    }

    let cancelled = false;

    const maybeRunActiveCheck = async () => {
      const current = queryClient.getQueryData<{
        status: { checked_at?: string } | null;
      }>(queryKeys.health.oanda());
      const checkedAt = current?.status?.checked_at
        ? new Date(current.status.checked_at)
        : null;
      const isStale =
        !checkedAt || Date.now() - checkedAt.getTime() > refreshIntervalMs;

      if (!isStale) {
        return;
      }

      try {
        const refreshed = await healthApi.checkOandaStatus();
        if (!cancelled) {
          queryClient.setQueryData(queryKeys.health.oanda(), refreshed);
        }
      } catch {
        // Leave the last known status in cache.
      }
    };

    void maybeRunActiveCheck();
    const intervalId = window.setInterval(() => {
      void maybeRunActiveCheck();
    }, refreshIntervalMs);

    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [activeCheck, enabled, queryClient, refreshIntervalMs]);

  return query;
}
