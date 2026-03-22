import { useQuery } from '@tanstack/react-query';
import { queryClient, queryKeys } from '../config/reactQuery';
import type {
  PaginatedResponse,
  TradingTask,
  TradingTaskListParams,
} from '../types';
import { TaskType } from '../types/common';
import {
  createTaskDetailQuery,
  createTaskListQuery,
} from './taskResourceQueries';
import { usePollingActivity } from './usePollingActivity';

interface UseTradingTasksResult {
  data: PaginatedResponse<TradingTask> | null;
  isLoading: boolean;
  error: Error | null;
  refresh: () => Promise<unknown>;
}

interface UseTradingTaskResult {
  data: TradingTask | null;
  isLoading: boolean;
  error: Error | null;
  refresh: () => Promise<unknown>;
}

interface UseTradingTaskOptions {
  enabled?: boolean;
  enablePolling?: boolean;
  pollingInterval?: number;
}

export function useTradingTasks(
  params?: TradingTaskListParams
): UseTradingTasksResult {
  const query = useQuery(
    createTaskListQuery<TradingTask>(TaskType.TRADING, params)
  );

  return {
    data: query.data ?? null,
    isLoading: query.isLoading,
    error: (query.error as Error | null) ?? null,
    refresh: () =>
      queryClient.invalidateQueries({
        queryKey: queryKeys.tradingTasks.list(params),
      }),
  };
}

export function useTradingTask(
  id?: string,
  options?: UseTradingTaskOptions
): UseTradingTaskResult {
  const pollingEnabled = usePollingActivity(
    Boolean(id) && options?.enablePolling === true
  );
  const query = useQuery(
    createTaskDetailQuery<TradingTask>(TaskType.TRADING, id, {
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
            queryKey: queryKeys.tradingTasks.detail(id),
          })
        : Promise.resolve(),
  };
}
