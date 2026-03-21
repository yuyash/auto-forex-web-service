import { useQuery } from '@tanstack/react-query';
import { queryClient, queryKeys } from '../config/reactQuery';
import { tradingTasksApi } from '../services/api';
import type {
  PaginatedResponse,
  TradingTask,
  TradingTaskListParams,
} from '../types';

interface UseTradingTasksResult {
  data: PaginatedResponse<TradingTask> | null;
  isLoading: boolean;
  error: Error | null;
  refetch: () => Promise<void>;
}

interface UseTradingTaskResult {
  data: TradingTask | null;
  isLoading: boolean;
  error: Error | null;
  refetch: () => Promise<void>;
}

export function invalidateTradingTasksCache(): void {
  void queryClient.invalidateQueries({ queryKey: queryKeys.tradingTasks.all });
}

export function useTradingTasks(
  params?: TradingTaskListParams
): UseTradingTasksResult {
  const query = useQuery({
    queryKey: queryKeys.tradingTasks.list(params),
    queryFn: () => tradingTasksApi.list(params),
    enabled: params !== undefined,
  });

  return {
    data: query.data ?? null,
    isLoading: query.isLoading,
    error: (query.error as Error | null) ?? null,
    refetch: async () => {
      await query.refetch();
    },
  };
}

export function useTradingTask(
  id?: string,
  options?: { enabled?: boolean }
): UseTradingTaskResult {
  const query = useQuery({
    queryKey: id
      ? queryKeys.tradingTasks.detail(id)
      : ['trading-task', 'empty'],
    queryFn: () => tradingTasksApi.get(id!),
    enabled: Boolean(id) && options?.enabled !== false,
  });

  return {
    data: query.data ?? null,
    isLoading: query.isLoading,
    error: (query.error as Error | null) ?? null,
    refetch: async () => {
      await query.refetch();
    },
  };
}

export function useTradingTaskPolling(
  id: string,
  enabled: boolean = true,
  interval: number = 5000
): UseTradingTaskResult {
  const query = useQuery({
    queryKey: queryKeys.tradingTasks.detail(id),
    queryFn: () => tradingTasksApi.get(id),
    enabled: enabled && Boolean(id),
    refetchInterval: enabled ? interval : false,
  });

  return {
    data: query.data ?? null,
    isLoading: query.isLoading,
    error: (query.error as Error | null) ?? null,
    refetch: async () => {
      await query.refetch();
    },
  };
}
