/**
 * Hook for fetching trading task results with polling support.
 */

import { useState, useEffect, useRef } from 'react';
import { tradingTasksApi } from '../services/api/tradingTasks';
import { TaskStatus } from '../types/common';
import type { ExecutionMetrics, ExecutionSummary } from '../types/execution';

interface TradingResults {
  execution: ExecutionSummary | null;
  metrics: ExecutionMetrics | null;
}

interface UseTradingResultsOptions {
  interval?: number;
}

interface UseTradingResultsReturn {
  results: TradingResults | null;
  isLoading: boolean;
  error: Error | null;
}

export function useTradingResults(
  taskId: string,
  status: string,
  options: UseTradingResultsOptions = {}
): UseTradingResultsReturn {
  const { interval = 10000 } = options;
  const [results, setResults] = useState<TradingResults | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const cancelledRef = useRef(false);

  useEffect(() => {
    cancelledRef.current = false;

    const fetchResults = async () => {
      try {
        const task = await tradingTasksApi.get(taskId);
        if (cancelledRef.current) return;

        const execution: ExecutionSummary | null = task.latest_execution
          ? (task.latest_execution as unknown as ExecutionSummary)
          : null;

        setResults({
          execution,
          metrics: execution
            ? (execution as unknown as ExecutionMetrics)
            : null,
        });
        setError(null);
      } catch (err) {
        if (cancelledRef.current) return;
        setError(
          err instanceof Error ? err : new Error('Failed to fetch results')
        );
      } finally {
        if (!cancelledRef.current) {
          setIsLoading(false);
        }
      }
    };

    fetchResults();

    let intervalId: number | null = null;
    if (status === TaskStatus.RUNNING) {
      intervalId = window.setInterval(fetchResults, interval);
    }

    return () => {
      cancelledRef.current = true;
      if (intervalId !== null) window.clearInterval(intervalId);
    };
  }, [taskId, status, interval]);

  return { results, isLoading, error };
}
