import { useEffect } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '../config/reactQuery';
import { healthApi } from '../services/api';
import { createOandaHealthStatusQuery } from './miscQueries';
import { mapQueryStateFields, useSimpleQueryState } from './useTaskCollections';

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

  const query = useSimpleQueryState(
    createOandaHealthStatusQuery({
      enabled,
      staleTime: refreshIntervalMs,
    })
  );

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

  return mapQueryStateFields(query, (data) => ({
    status: data?.status ?? null,
    isAvailable: Boolean(data?.status?.is_available),
    checkedAt: data?.status?.checked_at ?? null,
  }));
}
