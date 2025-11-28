/**
 * useBacktestLiveResults - Hook for polling live/intermediate results during backtest execution
 *
 * This hook polls the backend for live results while a backtest is running,
 * allowing the UI to show progressive updates (equity curve, trades, metrics)
 * without waiting for task completion.
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import { backtestTasksApi } from '../services/api/backtestTasks';
import { TaskStatus } from '../types/common';
import type { BacktestLiveResults } from '../types/backtestTask';

interface UseBacktestLiveResultsOptions {
  /** Whether to enable polling (default: true when task is running) */
  enabled?: boolean;
  /** Polling interval in milliseconds (default: 5000) */
  interval?: number;
}

interface UseBacktestLiveResultsResult {
  /** Live results data from the running backtest */
  liveResults: BacktestLiveResults | null;
  /** Whether the initial fetch is loading */
  isLoading: boolean;
  /** Error if fetch failed */
  error: Error | null;
  /** Whether polling is active */
  isPolling: boolean;
  /** Manually trigger a refetch */
  refetch: () => void;
}

/**
 * Custom hook for polling live backtest results
 *
 * @param taskId - The ID of the backtest task
 * @param taskStatus - Current status of the task
 * @param options - Polling configuration
 * @returns Live results data and control functions
 *
 * @example
 * ```tsx
 * const { liveResults, isLoading } = useBacktestLiveResults(
 *   taskId,
 *   task.status,
 *   { interval: 3000 }
 * );
 *
 * // Pass liveResults to TaskOverviewTab when task is running
 * <TaskOverviewTab task={task} liveResults={liveResults} />
 * ```
 */
export function useBacktestLiveResults(
  taskId: number | undefined,
  taskStatus: TaskStatus | undefined,
  options: UseBacktestLiveResultsOptions = {}
): UseBacktestLiveResultsResult {
  const { interval = 5000 } = options;

  // Only poll when task is running
  const shouldPoll = taskStatus === TaskStatus.RUNNING;
  const enabled = options.enabled !== undefined ? options.enabled : shouldPoll;

  const [liveResults, setLiveResults] = useState<BacktestLiveResults | null>(
    null
  );
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<Error | null>(null);
  const [isPolling, setIsPolling] = useState<boolean>(false);

  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const isMountedRef = useRef<boolean>(true);

  /**
   * Fetch live results from the API
   */
  const fetchLiveResults = useCallback(async () => {
    if (!taskId) return;

    try {
      const results = await backtestTasksApi.getLiveResults(taskId);

      if (isMountedRef.current) {
        setLiveResults(results);
        setError(null);
        setIsLoading(false);
      }
    } catch (err) {
      if (isMountedRef.current) {
        // Only set error if it's not a 404 (no results yet)
        const isNotFound = err instanceof Error && err.message.includes('404');
        if (!isNotFound) {
          setError(
            err instanceof Error
              ? err
              : new Error('Failed to fetch live results')
          );
        }
        setIsLoading(false);
      }
    }
  }, [taskId]);

  /**
   * Manual refetch
   */
  const refetch = useCallback(() => {
    fetchLiveResults();
  }, [fetchLiveResults]);

  /**
   * Effect: Start/stop polling based on enabled state
   */
  useEffect(() => {
    isMountedRef.current = true;

    // Clear any existing interval first
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }

    if (enabled && taskId) {
      // Initial loading state
      // Note: Using direct setState in useEffect is fine for setup/initialization
      setIsLoading(true); // eslint-disable-line react-hooks/set-state-in-effect
      setIsPolling(true);

      // Initial fetch
      fetchLiveResults();

      // Set up interval for polling
      intervalRef.current = setInterval(fetchLiveResults, interval);
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
  }, [enabled, taskId, fetchLiveResults, interval]);

  /**
   * Effect: Clear results when task status changes away from RUNNING
   */
  useEffect(() => {
    if (taskStatus !== TaskStatus.RUNNING) {
      setLiveResults(null); // eslint-disable-line react-hooks/set-state-in-effect
    }
  }, [taskStatus]);

  return {
    liveResults,
    isLoading,
    error,
    isPolling,
    refetch,
  };
}
