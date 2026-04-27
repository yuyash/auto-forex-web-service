import { refreshTaskStrategyEvents } from './taskResourceCache';
import { createTaskStrategyEventsQuery } from './taskResourceQueries';
import type { TaskType } from '../types/common';
import type { StrategyCyclesResponse } from '../types/strategyVisualization';
import { usePollingPolicy } from './usePollingPolicy';
import { usePolledTaskResource } from './useTaskCollections';

interface UseTaskStrategyEventsOptions {
  taskId: string | number;
  taskType: TaskType;
  executionRunId?: string;
  cycleId?: string;
  enabled?: boolean;
  enableRealTimeUpdates?: boolean;
  refreshInterval?: number;
  params?: Record<string, string | number | undefined>;
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
  cycleId,
  enabled = true,
  enableRealTimeUpdates = false,
  refreshInterval = 10_000,
  params,
}: UseTaskStrategyEventsOptions): UseTaskStrategyEventsResult {
  const pollingPolicy = usePollingPolicy({
    enabled: enabled && enableRealTimeUpdates && Boolean(taskId),
    baseIntervalMs: refreshInterval,
  });
  const refresh = () =>
    refreshTaskStrategyEvents(
      String(taskId),
      taskType,
      executionRunId,
      cycleId
    );
  const resource = usePolledTaskResource(
    createTaskStrategyEventsQuery(taskId, taskType, executionRunId, cycleId, {
      enabled,
      params,
    }),
    refresh,
    {
      pollingEnabled: enabled && pollingPolicy.isActive,
      intervalMs: pollingPolicy.intervalMs,
    }
  );

  return {
    ...resource,
    data: resource.data ?? null,
  };
}
