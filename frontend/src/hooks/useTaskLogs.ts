// useTaskLogs - React hook for fetching and managing task logs with pagination

import { useState, useEffect, useCallback, useRef } from 'react';
import { apiClient } from '../services/api/client';
import type { ExecutionLog } from '../types';
import type { TaskType } from '../services/polling/TaskPollingService';

export interface TaskLogsParams {
  execution_id?: number;
  level?: 'INFO' | 'WARNING' | 'ERROR' | 'DEBUG';
  // Pagination mode: page/page_size
  page?: number;
  page_size?: number;
}

export interface TaskLogsResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: ExecutionLog[];
}

export interface UseTaskLogsOptions {
  enabled?: boolean; // Whether to fetch logs immediately
  autoRefresh?: boolean; // Whether to auto-refresh logs
  refreshInterval?: number; // Auto-refresh interval in milliseconds
  initialParams?: TaskLogsParams;
}

export interface UseTaskLogsResult {
  logs: ExecutionLog[];
  totalCount: number;
  isLoading: boolean;
  error: Error | null;
  fetchLogs: (params?: TaskLogsParams) => Promise<void>;
  refresh: () => Promise<void>;
  setFilter: (level?: string) => void;
  currentFilter: string | undefined;
}

/**
 * useTaskLogs - Custom hook for fetching task logs with pagination
 *
 * @param taskId - The ID of the task
 * @param taskType - The type of task ('backtest' or 'trading')
 * @param options - Configuration options
 *
 * @returns Object containing logs, loading state, and control functions
 *
 * @example
 * ```tsx
 * const { logs, isLoading, refresh } = useTaskLogs(
 *   taskId,
 *   'backtest',
 *   { enabled: true, initialParams: { page: 1, page_size: 100 } }
 * );
 * ```
 */
export function useTaskLogs(
  taskId: number | undefined,
  taskType: TaskType,
  options: UseTaskLogsOptions = {}
): UseTaskLogsResult {
  const {
    enabled = true,
    autoRefresh = false,
    refreshInterval = 5000,
    initialParams = { page: 1, page_size: 100 },
  } = options;

  const [logs, setLogs] = useState<ExecutionLog[]>([]);
  const [totalCount, setTotalCount] = useState<number>(0);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<Error | null>(null);
  const [currentParams, setCurrentParams] =
    useState<TaskLogsParams>(initialParams);
  const [currentFilter, setCurrentFilter] = useState<string | undefined>(
    initialParams.level
  );

  const refreshIntervalRef = useRef<number | null>(null);
  const isMountedRef = useRef<boolean>(true);

  /**
   * Fetch logs from API
   */
  const fetchLogs = useCallback(
    async (params?: TaskLogsParams): Promise<void> => {
      if (!taskId) {
        return;
      }

      setIsLoading(true);
      setError(null);

      try {
        // Backend routes are namespaced under /trading/...
        const endpoint = `/trading/${taskType}-tasks/${taskId}/logs/`;
        const queryParams = params || currentParams;

        const response = await apiClient.get<TaskLogsResponse>(
          endpoint,
          queryParams as Record<string, unknown>
        );

        if (!isMountedRef.current) {
          return;
        }

        // Always replace in page/page_size mode.
        setLogs(response.results);

        setTotalCount(response.count);
        setCurrentParams(queryParams);
      } catch (err) {
        if (!isMountedRef.current) {
          return;
        }
        setError(err as Error);
      } finally {
        if (isMountedRef.current) {
          setIsLoading(false);
        }
      }
    },
    [taskId, taskType, currentParams]
  );

  /**
   * Refresh logs from the beginning
   */
  const refresh = useCallback(async (): Promise<void> => {
    await fetchLogs({
      ...currentParams,
    });
  }, [currentParams, fetchLogs]);

  /**
   * Set log level filter
   */
  const setFilter = useCallback(
    (level?: string): void => {
      setCurrentFilter(level);
      setCurrentParams((prev) => ({
        ...prev,
        level: level as 'INFO' | 'WARNING' | 'ERROR' | 'DEBUG' | undefined,
        page: 1, // Reset to first page when filtering
      }));
      // Fetch with new filter
      fetchLogs({
        ...currentParams,
        level: level as 'INFO' | 'WARNING' | 'ERROR' | 'DEBUG' | undefined,
        page: 1,
      });
    },
    [currentParams, fetchLogs]
  );

  /**
   * Effect: Initial fetch when enabled
   */
  useEffect(() => {
    isMountedRef.current = true;

    if (!taskId || !enabled) {
      return;
    }

    fetchLogs(initialParams);

    return () => {
      isMountedRef.current = false;
    };
  }, [taskId, enabled, fetchLogs, initialParams]); // Include all dependencies

  /**
   * Effect: Auto-refresh logs
   */
  useEffect(() => {
    if (!autoRefresh || !taskId || !enabled) {
      return;
    }

    refreshIntervalRef.current = window.setInterval(() => {
      refresh();
    }, refreshInterval);

    return () => {
      if (refreshIntervalRef.current !== null) {
        window.clearInterval(refreshIntervalRef.current);
        refreshIntervalRef.current = null;
      }
    };
  }, [autoRefresh, taskId, enabled, refreshInterval, refresh]);

  return {
    logs,
    totalCount,
    isLoading,
    error,
    fetchLogs,
    refresh,
    setFilter,
    currentFilter,
  };
}
