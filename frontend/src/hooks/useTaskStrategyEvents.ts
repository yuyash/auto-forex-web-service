import { useQuery } from '@tanstack/react-query';
import { useSequentialPolling } from './useSequentialPolling';
import { refreshTaskStrategyEvents } from './taskResourceCache';
import { createTaskStrategyEventsQuery } from './taskResourceQueries';
import { TaskType } from '../types/common';
import type { StrategyVisualizationResponse } from '../types/strategyVisualization';
import { usePollingActivity } from './usePollingActivity';

interface UseTaskStrategyEventsOptions {
  taskId: string | number;
  taskType: TaskType;
  executionRunId?: string;
  enableRealTimeUpdates?: boolean;
  refreshInterval?: number;
}

interface UseTaskStrategyEventsResult {
  data: StrategyVisualizationResponse | null;
  isLoading: boolean;
  error: Error | null;
  refresh: () => Promise<unknown>;
  refetch: () => Promise<unknown>;
}

export function useTaskStrategyEvents({
  taskId,
  taskType,
  executionRunId,
  enableRealTimeUpdates = false,
  refreshInterval = 10_000,
}: UseTaskStrategyEventsOptions): UseTaskStrategyEventsResult {
  const query = useQuery(
    createTaskStrategyEventsQuery(taskId, taskType, executionRunId)
  );
  const pollingEnabled = usePollingActivity(
    enableRealTimeUpdates && Boolean(taskId)
  );

  useSequentialPolling(
    () => {
      if (!query.isFetching) {
        return query.refetch();
      }
      return Promise.resolve();
    },
    {
      enabled: pollingEnabled,
      intervalMs: refreshInterval,
    }
  );

  const refresh = () =>
    refreshTaskStrategyEvents(String(taskId), taskType, executionRunId);

  return {
    data: query.data ?? null,
    isLoading: query.isLoading,
    error: (query.error as Error | null) ?? null,
    refresh,
    refetch: refresh,
  };
}
