import type {
  PaginatedResponse,
  TradingTask,
  TradingTaskListParams,
} from '../types';
import { TaskType } from '../types/common';
import {
  createTaskDetailQuery,
  createTaskListQuery,
  shouldPollTaskStatus,
} from './taskResourceQueries';
import { usePollingPolicy } from './usePollingPolicy';
import { useTaskDetail, useTaskList } from './useTaskCollections';
import type { QueryStateResult } from './useTaskCollections';

interface UseTaskOptions {
  enabled?: boolean;
  enablePolling?: boolean;
  pollingInterval?: number;
}

export function useTradingTasks(
  params?: TradingTaskListParams
): QueryStateResult<PaginatedResponse<TradingTask>> {
  return useTaskList<PaginatedResponse<TradingTask>>(
    createTaskListQuery<TradingTask>(TaskType.TRADING, params)
  );
}

export function useTradingTask(
  id?: string,
  options?: UseTaskOptions
): QueryStateResult<TradingTask> {
  const pollingPolicy = usePollingPolicy({
    enabled: Boolean(id) && options?.enablePolling === true,
    baseIntervalMs: options?.pollingInterval ?? 3000,
  });
  return useTaskDetail<TradingTask>(
    createTaskDetailQuery<TradingTask>(TaskType.TRADING, id, {
      ...options,
      enablePolling: pollingPolicy.isActive,
    }),
    undefined,
    {
      policy: pollingPolicy,
      shouldPoll: (task) => shouldPollTaskStatus(task?.status),
    }
  );
}
