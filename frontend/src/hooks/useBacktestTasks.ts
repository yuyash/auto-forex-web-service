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
  const pollingEnabled = usePollingActivity(
    Boolean(id) && options?.enablePolling === true
  );
  return useTaskDetail<BacktestTask>(
    createTaskDetailQuery<BacktestTask>(TaskType.BACKTEST, id, {
      ...options,
      enablePolling: pollingEnabled,
    })
  );
}
