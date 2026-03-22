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
import { useTaskDetail, useTaskList } from './useTaskCollections';

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
  return useTaskList<TradingTask, TradingTaskListParams>(
    createTaskListQuery<TradingTask>(TaskType.TRADING, params)
  );
}

export function useTradingTask(
  id?: string,
  options?: UseTradingTaskOptions
): UseTradingTaskResult {
  const pollingEnabled = usePollingActivity(
    Boolean(id) && options?.enablePolling === true
  );
  return useTaskDetail<TradingTask>(
    createTaskDetailQuery<TradingTask>(TaskType.TRADING, id, {
      ...options,
      enablePolling: pollingEnabled,
    })
  );
}
