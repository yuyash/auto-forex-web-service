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
import type { QueryStateResult } from './useTaskCollections';
import { useTaskEventStream } from './useTaskEventStream';

interface UseTaskOptions {
  enabled?: boolean;
  enablePolling?: boolean;
  pollingInterval?: number;
}

export function useBacktestTasks(
  params?: BacktestTaskListParams
): QueryStateResult<PaginatedResponse<BacktestTask>> {
  return useTaskList<PaginatedResponse<BacktestTask>>(
    createTaskListQuery<BacktestTask>(TaskType.BACKTEST, params)
  );
}

export function useBacktestTask(
  id?: string,
  options?: UseTaskOptions
): QueryStateResult<BacktestTask> {
  const pollingPolicy = usePollingPolicy({
    enabled: Boolean(id) && options?.enablePolling === true,
    baseIntervalMs: options?.pollingInterval ?? 3000,
  });
  const state = useTaskDetail<BacktestTask>(
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
  useTaskEventStream<BacktestTask>({
    taskType: TaskType.BACKTEST,
    taskId: id,
    enabled: Boolean(id) && options?.enablePolling === true,
  });
  return state;
}
