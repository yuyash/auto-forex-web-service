import { useCallback, useEffect, useRef, useState } from 'react';
import { backtestTasksApi } from '../services/api/backtestTasks';
import { tradingTasksApi } from '../services/api/tradingTasks';
import type { TaskResults } from '../types/results';
import { TaskStatus, TaskType } from '../types/common';

interface UseTaskResultsOptions {
  enabled?: boolean;
  interval?: number;
}

interface UseTaskResultsResult {
  results: TaskResults | null;
  isLoading: boolean;
  error: Error | null;
  isPolling: boolean;
  refetch: () => void;
}

function usePollingResults(
  fetcher: () => Promise<TaskResults>,
  enabled: boolean,
  pollingEnabled: boolean,
  interval: number
): UseTaskResultsResult {
  const [results, setResults] = useState<TaskResults | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [isPolling, setIsPolling] = useState(false);

  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const isMountedRef = useRef(true);

  const fetchOnce = useCallback(async () => {
    try {
      const data = await fetcher();
      if (isMountedRef.current) {
        setResults(data);
        setError(null);
      }
    } catch (err) {
      if (isMountedRef.current) {
        setError(
          err instanceof Error ? err : new Error('Failed to fetch results')
        );
      }
    } finally {
      if (isMountedRef.current) {
        setIsLoading(false);
      }
    }
  }, [fetcher]);

  const refetch = useCallback(() => {
    setIsLoading(true);
    fetchOnce();
  }, [fetchOnce]);

  useEffect(() => {
    isMountedRef.current = true;

    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }

    if (!enabled) {
      setIsPolling(false);
      return () => {
        isMountedRef.current = false;
      };
    }

    // Always fetch once when enabled
    setIsLoading(true);
    fetchOnce();

    // Only poll when requested
    if (pollingEnabled) {
      setIsPolling(true);
      intervalRef.current = setInterval(fetchOnce, interval);
    } else {
      setIsPolling(false);
    }

    return () => {
      isMountedRef.current = false;
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [enabled, pollingEnabled, fetchOnce, interval]);

  return { results, isLoading, error, isPolling, refetch };
}

export function useBacktestResults(
  taskId: number | undefined,
  taskStatus: TaskStatus | undefined,
  options: UseTaskResultsOptions = {}
): UseTaskResultsResult {
  const interval = options.interval ?? 5000;
  const shouldPoll = taskStatus === TaskStatus.RUNNING;
  const enabled = options.enabled ?? !!taskId;

  const fetcher = useCallback(() => {
    if (!taskId) {
      return Promise.reject(new Error('Missing taskId'));
    }
    return backtestTasksApi.getResults(taskId);
  }, [taskId]);

  return usePollingResults(fetcher, enabled && !!taskId, shouldPoll, interval);
}

export function useTradingResults(
  taskId: number | undefined,
  taskStatus: TaskStatus | undefined,
  options: UseTaskResultsOptions = {}
): UseTaskResultsResult {
  const interval = options.interval ?? 5000;
  const shouldPoll =
    taskStatus === TaskStatus.RUNNING || taskStatus === TaskStatus.PAUSED;
  const enabled = options.enabled ?? !!taskId;

  const fetcher = useCallback(() => {
    if (!taskId) {
      return Promise.reject(new Error('Missing taskId'));
    }
    return tradingTasksApi.getResults(taskId);
  }, [taskId]);

  return usePollingResults(fetcher, enabled && !!taskId, shouldPoll, interval);
}

export function getTaskTypeResultsFetcher(taskType: TaskType, taskId: number) {
  return taskType === TaskType.BACKTEST
    ? () => backtestTasksApi.getResults(taskId)
    : () => tradingTasksApi.getResults(taskId);
}
