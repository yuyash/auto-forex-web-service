import { useQuery } from '@tanstack/react-query';
import { useSequentialPolling } from './useSequentialPolling';
import { refreshTaskStrategyEvents } from './taskResourceCache';
import { createTaskStrategyEventsQuery } from './taskResourceQueries';
import { TaskType } from '../types/common';
import type { StrategyVisualizationResponse } from '../types/strategyVisualization';

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

  useSequentialPolling(
    () => {
      if (!query.isFetching) {
        return query.refetch();
      }
      return Promise.resolve();
    },
    {
      enabled: enableRealTimeUpdates && Boolean(taskId),
      intervalMs: refreshInterval,
    }
  );

  return {
    data: query.data ?? null,
    isLoading: query.isLoading,
    error: (query.error as Error | null) ?? null,
    refetch: () =>
      refreshTaskStrategyEvents(String(taskId), taskType, executionRunId),
  };
}
