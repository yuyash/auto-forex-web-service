import { TaskType } from '../types/common';
import type {
  BacktestTask,
  BacktestTaskListParams,
  PaginatedResponse,
} from '../types';
import {
  createTaskDetailQuery,
  createTaskListQuery,
  shouldPollTaskStatus,
} from './taskResourceQueries';
import { usePollingPolicy } from './usePollingPolicy';
import { useTaskList, useTaskDetail } from './useTaskCollections';

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
  return useTaskList<BacktestTask, BacktestTaskListParams>(
    createTaskListQuery<BacktestTask>(TaskType.BACKTEST, params)
  );
}

export function useBacktestTask(
  id?: string,
  options?: UseBacktestTaskOptions
): UseBacktestTaskResult {
  const pollingPolicy = usePollingPolicy({
    enabled: Boolean(id) && options?.enablePolling === true,
    baseIntervalMs: options?.pollingInterval ?? 3000,
  });
  return useTaskDetail<BacktestTask>(
    createTaskDetailQuery<BacktestTask>(TaskType.BACKTEST, id, {
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
