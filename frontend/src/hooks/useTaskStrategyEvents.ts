import { refreshTaskStrategyEvents } from './taskResourceCache';
import { createTaskStrategyEventsQuery } from './taskResourceQueries';
import { TaskType } from '../types/common';
import type { StrategyCyclesResponse } from '../types/strategyVisualization';
import { usePollingPolicy } from './usePollingPolicy';
import { usePolledTaskResource } from './useTaskCollections';

interface UseTaskStrategyEventsOptions {
  taskId: string | number;
  taskType: TaskType;
  executionRunId?: string;
  enableRealTimeUpdates?: boolean;
  refreshInterval?: number;
}

interface UseTaskStrategyEventsResult {
  data: StrategyCyclesResponse | null;
  isLoading: boolean;
  error: Error | null;
  refresh: () => Promise<unknown>;
}

export function useTaskStrategyEvents({
  taskId,
  taskType,
  executionRunId,
  enableRealTimeUpdates = false,
  refreshInterval = 10_000,
}: UseTaskStrategyEventsOptions): UseTaskStrategyEventsResult {
  const pollingPolicy = usePollingPolicy({
    enabled: enableRealTimeUpdates && Boolean(taskId),
    baseIntervalMs: refreshInterval,
  });
  const refresh = () =>
    refreshTaskStrategyEvents(String(taskId), taskType, executionRunId);
  const resource = usePolledTaskResource(
    createTaskStrategyEventsQuery(taskId, taskType, executionRunId),
    refresh,
    {
      pollingEnabled: pollingPolicy.isActive,
      intervalMs: pollingPolicy.intervalMs,
    }
  );

  return {
    ...resource,
    data: resource.data ?? null,
  };
}
