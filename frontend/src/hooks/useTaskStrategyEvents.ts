import { refreshTaskStrategyEvents } from './taskResourceCache';
import { createTaskStrategyEventsQuery } from './taskResourceQueries';
import { TaskType } from '../types/common';
import type { StrategyVisualizationResponse } from '../types/strategyVisualization';
import { usePollingActivity } from './usePollingActivity';
import { usePolledTaskResource } from './useTaskCollections';

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
  const pollingEnabled = usePollingActivity(
    enableRealTimeUpdates && Boolean(taskId)
  );
  const refresh = () =>
    refreshTaskStrategyEvents(String(taskId), taskType, executionRunId);
  const resource = usePolledTaskResource(
    createTaskStrategyEventsQuery(taskId, taskType, executionRunId),
    refresh,
    { pollingEnabled, intervalMs: refreshInterval }
  );

  return {
    ...resource,
    data: resource.data ?? null,
  };
}
