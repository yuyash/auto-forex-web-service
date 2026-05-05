import { keepPreviousData, useQuery } from '@tanstack/react-query';
import type { TaskType } from '../types/common';
import type {
  StrategyHistoryResponse,
  StrategyMetricsResponse,
  StrategySnapshotResponse,
  SnowballNetChartResponse,
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
  center?: string;
  before_bars?: number;
  after_bars?: number;
  follow?: string;
  merge_markers?: string;
  account_id?: string | number;
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

export function useSnowballNetChart({
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
      'snowball-net-chart',
      queryParams,
    ],
    enabled: enabled && Boolean(taskId),
    queryFn: () =>
      fetchTaskResourceObject<SnowballNetChartResponse>(
        taskType,
        taskId,
        'strategy/net-chart',
        queryParams
      ),
    placeholderData: keepPreviousData,
    staleTime: 0,
    refetchInterval,
  });
}

export function useLossCutEvents({
  taskId,
  taskType,
  executionRunId,
  enabled = true,
  refetchInterval = false,
  since,
  until,
}: {
  taskId: string | number;
  taskType: TaskType;
  executionRunId?: string;
  enabled?: boolean;
  refetchInterval?: number | false;
  since?: string;
  until?: string;
}) {
  const queryParams = cleanParams({
    execution_id: executionRunId,
    since,
    until,
  });
  return useQuery({
    queryKey: [
      'strategy-data',
      taskType,
      String(taskId),
      'loss-cut-events',
      queryParams,
    ],
    enabled: enabled && Boolean(taskId),
    queryFn: () =>
      fetchTaskResourceObject<{
        execution_id: string | null;
        strategy_type: string;
        instrument: string | null;
        count: number;
        results: Array<{
          id: string;
          timestamp: string;
          time: number;
          units: number;
          direction: string | null;
          price: number | null;
          description: string;
          position_id: string | null;
        }>;
      }>(taskType, taskId, 'strategy/loss-cut-events', queryParams),
    placeholderData: keepPreviousData,
    staleTime: 0,
    refetchInterval,
  });
}
