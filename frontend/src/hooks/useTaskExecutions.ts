import { TaskType } from '../types';
import type { TaskExecution, PaginatedResponse } from '../types';
import {
  createTaskExecutionQuery,
  createTaskExecutionsQuery,
} from './taskResourceQueries';
import {
  refreshTaskExecution,
  refreshTaskExecutions,
} from './taskResourceCache';
import { usePollingPolicy } from './usePollingPolicy';
import { useTaskDetail, useTaskList } from './useTaskCollections';

interface UseTaskExecutionsResult {
  data: PaginatedResponse<TaskExecution> | undefined;
  isLoading: boolean;
  error: Error | null;
  refresh: () => Promise<unknown>;
  refetch: () => Promise<unknown>;
}

/**
 * Hook to fetch execution history for a task
 *
 * @param taskId - The task ID to fetch executions for
 * @param taskType - The type of task (backtest or trading)
 * @param params - Optional pagination parameters
 * @param options - Optional configuration options
 * @param options.enablePolling - Enable automatic polling for running executions (default: true)
 * @param options.pollingInterval - Polling interval in ms (default: 3000 for running, disabled otherwise)
 */
export function useTaskExecutions(
  taskId: string,
  taskType: TaskType,
  params?: { page?: number; page_size?: number; include_metrics?: boolean },
  options?: { enablePolling?: boolean; pollingInterval?: number }
): UseTaskExecutionsResult {
  const pollingPolicy = usePollingPolicy({
    enabled: options?.enablePolling !== false,
    baseIntervalMs: options?.pollingInterval ?? 3000,
  });
  const resource = useTaskList(
    createTaskExecutionsQuery(taskId, taskType, params, options),
    () => refreshTaskExecutions(taskId, taskType, params),
    {
      policy: pollingPolicy,
      shouldPoll: (data) =>
        Boolean(
          data?.results?.some((execution) => execution.status === 'running')
        ),
    }
  );

  return {
    ...resource,
    data: resource.data ?? undefined,
  };
}

interface UseTaskExecutionResult {
  data: TaskExecution | undefined;
  isLoading: boolean;
  error: Error | null;
  refresh: () => Promise<unknown>;
  refetch: () => Promise<unknown>;
}

/**
 * Hook to fetch a specific execution
 */
export function useTaskExecution(
  taskId: string,
  executionId: string,
  taskType: TaskType
): UseTaskExecutionResult {
  const resource = useTaskDetail(
    createTaskExecutionQuery(taskId, executionId, taskType),
    () => refreshTaskExecution(taskId, executionId, taskType)
  );

  return {
    ...resource,
    data: resource.data ?? undefined,
  };
}

/**
 * Hook to get a function that invalidates executions cache for a task
 */
export function useInvalidateExecutions() {
  return {
    invalidateBacktestExecutions: (taskId: string) =>
      refreshTaskExecutions(taskId, TaskType.BACKTEST),
    invalidateTradingExecutions: (taskId: string) =>
      refreshTaskExecutions(taskId, TaskType.TRADING),
  };
}
