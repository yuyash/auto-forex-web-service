import { useQuery } from '@tanstack/react-query';
import { queryClient, queryKeys } from '../config/reactQuery';
import { TaskType } from '../types/common';
import type {
  BacktestTask,
  BacktestTaskListParams,
  PaginatedResponse,
} from '../types';
import {
  createTaskDetailQuery,
  createTaskListQuery,
} from './taskResourceQueries';
import { usePollingActivity } from './usePollingActivity';

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
  const query = useQuery(
    createTaskListQuery<BacktestTask>(TaskType.BACKTEST, params)
  );

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
  const pollingEnabled = usePollingActivity(
    Boolean(id) && options?.enablePolling === true
  );
  const query = useQuery(
    createTaskDetailQuery<BacktestTask>(TaskType.BACKTEST, id, {
      ...options,
      enablePolling: pollingEnabled,
    })
  );

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
