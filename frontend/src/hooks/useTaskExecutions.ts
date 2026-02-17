// Task Execution hooks for data fetching
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { backtestTasksApi, tradingTasksApi } from '../services/api';
import { TaskType } from '../types';
import type { TaskExecution, PaginatedResponse } from '../types';

// Query key factories for cache invalidation
export const executionQueryKeys = {
  backtestExecutions: (taskId: string) => ['backtest-task-executions', taskId],
  tradingExecutions: (taskId: string) => ['trading-task-executions', taskId],
};

interface UseTaskExecutionsResult {
  data: PaginatedResponse<TaskExecution> | undefined;
  isLoading: boolean;
  error: Error | null;
  refetch: () => void;
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
  const queryKey =
    taskType === TaskType.BACKTEST
      ? ['backtest-task-executions', taskId, params]
      : ['trading-task-executions', taskId, params];

  const { data, isLoading, error, refetch } = useQuery({
    queryKey,
    queryFn: async () => {
      const fetchParams =
        params?.page || params?.page_size
          ? {
              page: params.page,
              page_size: params.page_size,
              include_metrics: params.include_metrics,
            }
          : undefined;

      return taskType === TaskType.BACKTEST
        ? await backtestTasksApi.getExecutions(taskId, fetchParams)
        : await tradingTasksApi.getExecutions(taskId, fetchParams);
    },
    staleTime: 2000, // Consider data fresh for 2 seconds
    refetchOnWindowFocus: true,
    // Enable automatic polling for running executions to get live logs
    // The callback receives the current query data as parameter
    refetchInterval: (query) => {
      // Check if any execution is running
      const queryData = query.state.data as
        | PaginatedResponse<TaskExecution>
        | undefined;
      const hasRunningExecution = queryData?.results?.some(
        (exec) => exec.status === 'running'
      );
      // If polling is enabled and there's a running execution, poll every 3 seconds
      if (options?.enablePolling !== false && hasRunningExecution) {
        return options?.pollingInterval ?? 3000;
      }
      return false; // Disable polling when no running executions
    },
  });

  return {
    data,
    isLoading,
    error: error as Error | null,
    refetch,
  };
}

interface UseTaskExecutionResult {
  data: TaskExecution | undefined;
  isLoading: boolean;
  error: Error | null;
  refetch: () => void;
}

/**
 * Hook to fetch a specific execution
 */
export function useTaskExecution(
  taskId: string,
  executionId: string,
  taskType: TaskType
): UseTaskExecutionResult {
  const queryKey =
    taskType === TaskType.BACKTEST
      ? ['backtest-task-execution', taskId, executionId]
      : ['trading-task-execution', taskId, executionId];

  const { data, isLoading, error, refetch } = useQuery({
    queryKey,
    queryFn: async () => {
      const pageSize = 1000;
      const response =
        taskType === TaskType.BACKTEST
          ? await backtestTasksApi.getExecutions(taskId, {
              page_size: pageSize,
            })
          : await tradingTasksApi.getExecutions(taskId, {
              page_size: pageSize,
            });

      const execution = response.results?.find((e) => e.id === executionId);
      if (!execution) {
        throw new Error('Execution not found');
      }

      return execution;
    },
    staleTime: 10000, // Consider data fresh for 10 seconds
  });

  return {
    data,
    isLoading,
    error: error as Error | null,
    refetch,
  };
}

/**
 * Hook to get a function that invalidates executions cache for a task
 */
export function useInvalidateExecutions() {
  const queryClient = useQueryClient();

  return {
    invalidateBacktestExecutions: (taskId: string) => {
      queryClient.invalidateQueries({
        queryKey: executionQueryKeys.backtestExecutions(taskId),
      });
    },
    invalidateTradingExecutions: (taskId: string) => {
      queryClient.invalidateQueries({
        queryKey: executionQueryKeys.tradingExecutions(taskId),
      });
    },
  };
}
