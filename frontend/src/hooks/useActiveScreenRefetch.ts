import { useCallback } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useAppSettings } from './useAppSettings';
import { usePollingPolicy } from './usePollingPolicy';
import { useSequentialPolling } from './useSequentialPolling';

/**
 * Periodically refresh every active query on the current protected screen.
 *
 * Individual task resources may still have narrower polling for low-latency
 * updates, but this hook provides a baseline guarantee that visible page
 * content is refetched at the user-configured task polling interval.
 */
export function useActiveScreenRefetch(): void {
  const queryClient = useQueryClient();
  const { settings } = useAppSettings();
  const intervalMs = Math.max(1, settings.taskPollingIntervalSeconds) * 1000;
  const pollingPolicy = usePollingPolicy({
    enabled: true,
    baseIntervalMs: intervalMs,
  });

  const refetchActiveQueries = useCallback(async () => {
    await queryClient.refetchQueries(
      {
        type: 'active',
      },
      {
        cancelRefetch: false,
      }
    );
  }, [queryClient]);

  useSequentialPolling(refetchActiveQueries, {
    enabled: pollingPolicy.isActive,
    intervalMs: pollingPolicy.intervalMs,
    onError: pollingPolicy.registerFailure,
  });
}
