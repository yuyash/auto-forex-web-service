import { useQuery } from '@tanstack/react-query';
import type { TaskType } from '../types/common';
import type {
  StrategyHistoryResponse,
  StrategyMetricsResponse,
  StrategySnapshotResponse,
} from '../types/strategyVisualization';
import { fetchTaskResourceObject } from '../services/api/taskResources';

export interface StrategyDataParams {
  execution_id?: string;
  since?: string;
  until?: string;
  granularity?: string;
  page?: number;
  page_size?: number;
  ordering?: string;
  category?: string;
  metric_keys?: string;
}

function cleanParams(params?: StrategyDataParams) {
  return Object.fromEntries(
    Object.entries(params ?? {}).filter(
      ([, value]) => value !== undefined && value !== ''
    )
  ) as Record<string, string | number | undefined>;
}

export function useStrategySnapshot({
  taskId,
  taskType,
  executionRunId,
  enabled = true,
  refetchInterval = false,
}: {
  taskId: string | number;
  taskType: TaskType;
  executionRunId?: string;
  enabled?: boolean;
  refetchInterval?: number | false;
}) {
  return useQuery({
    queryKey: [
      'strategy-data',
      taskType,
      String(taskId),
      'snapshot',
      executionRunId ?? null,
    ],
    enabled: enabled && Boolean(taskId),
    queryFn: () =>
      fetchTaskResourceObject<StrategySnapshotResponse>(
        taskType,
        taskId,
        'strategy/snapshot',
        cleanParams({ execution_id: executionRunId })
      ),
    staleTime: 0,
    refetchInterval,
  });
}

export function useStrategyHistory({
  taskId,
  taskType,
  executionRunId,
  params,
  enabled = true,
  refetchInterval = false,
}: {
  taskId: string | number;
  taskType: TaskType;
  executionRunId?: string;
  params?: StrategyDataParams;
  enabled?: boolean;
  refetchInterval?: number | false;
}) {
  const queryParams = cleanParams({ ...params, execution_id: executionRunId });
  return useQuery({
    queryKey: [
      'strategy-data',
      taskType,
      String(taskId),
      'history',
      queryParams,
    ],
    enabled: enabled && Boolean(taskId),
    queryFn: () =>
      fetchTaskResourceObject<StrategyHistoryResponse>(
        taskType,
        taskId,
        'strategy/history',
        queryParams
      ),
    staleTime: 0,
    refetchInterval,
  });
}

export function useStrategyMetrics({
  taskId,
  taskType,
  executionRunId,
  params,
  enabled = true,
  refetchInterval = false,
}: {
  taskId: string | number;
  taskType: TaskType;
  executionRunId?: string;
  params?: StrategyDataParams;
  enabled?: boolean;
  refetchInterval?: number | false;
}) {
  const queryParams = cleanParams({ ...params, execution_id: executionRunId });
  return useQuery({
    queryKey: [
      'strategy-data',
      taskType,
      String(taskId),
      'metrics',
      queryParams,
    ],
    enabled: enabled && Boolean(taskId),
    queryFn: () =>
      fetchTaskResourceObject<StrategyMetricsResponse>(
        taskType,
        taskId,
        'strategy/metrics',
        queryParams
      ),
    staleTime: 0,
    refetchInterval,
  });
}
