/**
 * useTaskLogs Hook
 *
 * Fetches logs directly from task-based API endpoints.
 * Replaces execution-based log fetching.
 */

import { useState, useEffect, useCallback } from 'react';
import { TradingService } from '../api/generated/services/TradingService';
import { TaskType } from '../types/common';

export interface TaskLog {
  id: string;
  timestamp: string;
  level: string;
  component: string;
  message: string;
  details?: Record<string, unknown>;
}

interface UseTaskLogsOptions {
  taskId: string;
  taskType: TaskType;
  level?: string;
  limit?: number;
  offset?: number;
  enableRealTimeUpdates?: boolean;
  refreshInterval?: number;
}

interface UseTaskLogsResult {
  logs: TaskLog[];
  totalCount: number;
  hasNext: boolean;
  hasPrevious: boolean;
  isLoading: boolean;
  error: Error | null;
  refetch: () => Promise<void>;
}

export const useTaskLogs = ({
  taskId,
  taskType,
  level,
  limit = 100,
  offset = 0,
  enableRealTimeUpdates = false,
  refreshInterval = 5000,
}: UseTaskLogsOptions): UseTaskLogsResult => {
  const [logs, setLogs] = useState<TaskLog[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [hasNext, setHasNext] = useState(false);
  const [hasPrevious, setHasPrevious] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetchLogs = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);

      const response =
        taskType === TaskType.BACKTEST
          ? await TradingService.tradingTasksBacktestLogsList(
              taskId,
              level,
              limit,
              offset
            )
          : await TradingService.tradingTasksTradingLogsList(
              taskId,
              level,
              limit,
              offset
            );

      setLogs(response.results || []);
      setTotalCount(response.count || 0);
      setHasNext(Boolean(response.next));
      setHasPrevious(Boolean(response.previous));
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : 'Failed to load logs';
      setError(new Error(errorMessage));
    } finally {
      setIsLoading(false);
    }
  }, [taskId, taskType, level, limit, offset]);

  useEffect(() => {
    fetchLogs();
  }, [fetchLogs]);

  useEffect(() => {
    if (!enableRealTimeUpdates) return;

    const interval = setInterval(() => {
      fetchLogs();
    }, refreshInterval);

    return () => clearInterval(interval);
  }, [enableRealTimeUpdates, refreshInterval, fetchLogs]);

  return {
    logs,
    totalCount,
    hasNext,
    hasPrevious,
    isLoading,
    error,
    refetch: fetchLogs,
  };
};
