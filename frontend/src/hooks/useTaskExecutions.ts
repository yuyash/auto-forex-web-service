// Task Execution hooks for data fetching
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { backtestTasksApi, tradingTasksApi } from '../services/api';
import { TaskType } from '../types';
import type { TaskExecution, PaginatedResponse } from '../types';

// Query key factories for cache invalidation
export const executionQueryKeys = {
  backtestExecutions: (taskId: number) => ['backtest-task-executions', taskId],
  tradingExecutions: (taskId: number) => ['trading-task-executions', taskId],
};

interface UseTaskExecutionsResult {
  data: PaginatedResponse<TaskExecution> | undefined;
  isLoading: boolean;
  error: Error | null;
  refetch: () => void;
}

/**
 * Hook to fetch execution history for a task
 */
export function useTaskExecutions(
  taskId: number,
  taskType: TaskType,
  params?: { page?: number; page_size?: number }
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
          ? { page: params.page, page_size: params.page_size }
          : undefined;

      return taskType === TaskType.BACKTEST
        ? await backtestTasksApi.getExecutions(taskId, fetchParams)
        : await tradingTasksApi.getExecutions(taskId, fetchParams);
    },
    staleTime: 5000, // Consider data fresh for 5 seconds
    refetchOnWindowFocus: true,
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
  taskId: number,
  executionId: number,
  taskType: TaskType
): UseTaskExecutionResult {
  const queryKey =
    taskType === TaskType.BACKTEST
      ? ['backtest-task-execution', taskId, executionId]
      : ['trading-task-execution', taskId, executionId];

  const { data, isLoading, error, refetch } = useQuery({
    queryKey,
    queryFn: async () => {
      return taskType === TaskType.BACKTEST
        ? await backtestTasksApi.getExecution(taskId, executionId)
        : await tradingTasksApi.getExecution(taskId, executionId);
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
    invalidateBacktestExecutions: (taskId: number) => {
      queryClient.invalidateQueries({
        queryKey: executionQueryKeys.backtestExecutions(taskId),
      });
    },
    invalidateTradingExecutions: (taskId: number) => {
      queryClient.invalidateQueries({
        queryKey: executionQueryKeys.tradingExecutions(taskId),
      });
    },
  };
}
