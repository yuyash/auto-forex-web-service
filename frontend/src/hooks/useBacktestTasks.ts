import { useQuery } from '@tanstack/react-query';
import { queryClient, queryKeys } from '../config/reactQuery';
import { backtestTasksApi } from '../services/api';
import type {
  BacktestTask,
  BacktestTaskListParams,
  PaginatedResponse,
} from '../types';

interface UseBacktestTasksResult {
  data: PaginatedResponse<BacktestTask> | null;
  isLoading: boolean;
  error: Error | null;
  refresh: () => Promise<unknown>;
}

interface UseBacktestTaskResult {
  data: BacktestTask | null;
  isLoading: boolean;
  error: Error | null;
  refresh: () => Promise<unknown>;
}

interface UseBacktestTaskOptions {
  enabled?: boolean;
  enablePolling?: boolean;
  pollingInterval?: number;
}

export function useBacktestTasks(
  params?: BacktestTaskListParams
): UseBacktestTasksResult {
  const query = useQuery({
    queryKey: queryKeys.backtestTasks.list(params),
    queryFn: () => backtestTasksApi.list(params),
    enabled: params !== undefined,
  });

  return {
    data: query.data ?? null,
    isLoading: query.isLoading,
    error: (query.error as Error | null) ?? null,
    refresh: () =>
      queryClient.invalidateQueries({
        queryKey: queryKeys.backtestTasks.list(params),
      }),
  };
}

export function useBacktestTask(
  id?: string,
  options?: UseBacktestTaskOptions
): UseBacktestTaskResult {
  const query = useQuery({
    queryKey: id
      ? queryKeys.backtestTasks.detail(id)
      : ['backtest-task', 'empty'],
    queryFn: () => backtestTasksApi.get(id!),
    enabled: Boolean(id) && options?.enabled !== false,
    refetchInterval: (queryContext) => {
      if (options?.enablePolling !== true) {
        return false;
      }
      const currentTask = queryContext.state.data as BacktestTask | undefined;
      const status = currentTask?.status;
      return status === 'starting' || status === 'running'
        ? (options.pollingInterval ?? 3000)
        : false;
    },
  });

  return {
    data: query.data ?? null,
    isLoading: query.isLoading,
    error: (query.error as Error | null) ?? null,
    refresh: () =>
      id
        ? queryClient.invalidateQueries({
            queryKey: queryKeys.backtestTasks.detail(id),
          })
        : Promise.resolve(),
  };
}
