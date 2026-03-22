import { useCallback } from 'react';
import { useQuery } from '@tanstack/react-query';
import { queryKeys } from '../config/reactQuery';
import { useSequentialPolling } from './useSequentialPolling';
import { refreshTaskStrategyEvents } from './taskResourceCache';
import { TaskType } from '../types/common';
import type { StrategyVisualizationResponse } from '../types/strategyVisualization';
import { handleAuthErrorStatus } from '../utils/authEvents';
import {
  fetchTaskResourceObject,
  isApiErrorWithStatus,
} from '../services/api/taskResources';

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
  const fetchData = useCallback(async () => {
    if (!taskId) {
      return null;
    }

    try {
      return await fetchTaskResourceObject<StrategyVisualizationResponse>(
        taskType,
        taskId,
        'strategy-events',
        executionRunId ? { execution_id: executionRunId } : undefined
      );
    } catch (err) {
      if (isApiErrorWithStatus(err)) {
        handleAuthErrorStatus(err.status, {
          source: 'http',
          status: err.status,
          context: 'task_strategy_events',
        });
      }
      throw new Error(
        err instanceof Error
          ? err.message
          : 'Failed to load strategy visualization'
      );
    }
  }, [executionRunId, taskId, taskType]);

  const query = useQuery({
    queryKey: queryKeys.taskResources.strategyEvents(
      taskType,
      String(taskId),
      executionRunId
    ),
    queryFn: fetchData,
    enabled: Boolean(taskId),
  });

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
