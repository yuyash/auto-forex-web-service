// Task Execution hooks for data fetching
import { useState, useEffect, useCallback } from 'react';
import { backtestTasksApi, tradingTasksApi } from '../services/api';
import { TaskType } from '../types';
import type { TaskExecution, PaginatedResponse } from '../types';

interface UseTaskExecutionsResult {
  data: PaginatedResponse<TaskExecution> | null;
  isLoading: boolean;
  error: Error | null;
  refetch: () => Promise<void>;
}

/**
 * Hook to fetch execution history for a task
 */
export function useTaskExecutions(
  taskId: number,
  taskType: TaskType,
  params?: { page?: number; page_size?: number }
): UseTaskExecutionsResult {
  const [data, setData] = useState<PaginatedResponse<TaskExecution> | null>(
    null
  );
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetchData = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);
      const result =
        taskType === TaskType.BACKTEST
          ? await backtestTasksApi.getExecutions(taskId, params)
          : await tradingTasksApi.getExecutions(taskId, params);
      setData(result);
    } catch (err) {
      setError(err as Error);
    } finally {
      setIsLoading(false);
    }
  }, [taskId, taskType, params]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return {
    data,
    isLoading,
    error,
    refetch: fetchData,
  };
}

interface UseTaskExecutionResult {
  data: TaskExecution | null;
  isLoading: boolean;
  error: Error | null;
  refetch: () => Promise<void>;
}

/**
 * Hook to fetch a specific execution
 */
export function useTaskExecution(
  taskId: number,
  executionId: number,
  taskType: TaskType
): UseTaskExecutionResult {
  const [data, setData] = useState<TaskExecution | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetchData = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);
      const result =
        taskType === TaskType.BACKTEST
          ? await backtestTasksApi.getExecution(taskId, executionId)
          : await tradingTasksApi.getExecution(taskId, executionId);
      setData(result);
    } catch (err) {
      setError(err as Error);
    } finally {
      setIsLoading(false);
    }
  }, [taskId, executionId, taskType]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return {
    data,
    isLoading,
    error,
    refetch: fetchData,
  };
}
