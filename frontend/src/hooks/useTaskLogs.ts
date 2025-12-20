// useTaskLogs - React hook for fetching and managing task logs with pagination

import { useState, useEffect, useCallback, useRef } from 'react';
import { apiClient } from '../services/api/client';
import type { ExecutionLog } from '../types';
import type { TaskType } from '../services/polling/TaskPollingService';

export interface TaskLogsParams {
  execution_id?: number;
  level?: 'INFO' | 'WARNING' | 'ERROR' | 'DEBUG';
  limit?: number;
  offset?: number;
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
  hasMore: boolean;
  fetchLogs: (params?: TaskLogsParams) => Promise<void>;
  loadMore: () => Promise<void>;
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
 * const { logs, isLoading, loadMore, hasMore } = useTaskLogs(
 *   taskId,
 *   'backtest',
 *   { enabled: true, initialParams: { limit: 100 } }
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
    initialParams = { limit: 100, offset: 0 },
  } = options;

  const [logs, setLogs] = useState<ExecutionLog[]>([]);
  const [totalCount, setTotalCount] = useState<number>(0);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<Error | null>(null);
  const [currentParams, setCurrentParams] =
    useState<TaskLogsParams>(initialParams);
  const [hasMore, setHasMore] = useState<boolean>(false);
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

        // If offset is 0, replace logs; otherwise append
        if (queryParams.offset === 0) {
          setLogs(response.results);
        } else {
          setLogs((prevLogs) => [...prevLogs, ...response.results]);
        }

        setTotalCount(response.count);
        setHasMore(response.next !== null);
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
   * Load more logs (pagination)
   */
  const loadMore = useCallback(async (): Promise<void> => {
    if (!hasMore || isLoading) {
      return;
    }

    const nextOffset =
      (currentParams.offset || 0) + (currentParams.limit || 100);
    await fetchLogs({
      ...currentParams,
      offset: nextOffset,
    });
  }, [hasMore, isLoading, currentParams, fetchLogs]);

  /**
   * Refresh logs from the beginning
   */
  const refresh = useCallback(async (): Promise<void> => {
    await fetchLogs({
      ...currentParams,
      offset: 0,
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
        offset: 0, // Reset to first page when filtering
      }));
      // Fetch with new filter
      fetchLogs({
        ...currentParams,
        level: level as 'INFO' | 'WARNING' | 'ERROR' | 'DEBUG' | undefined,
        offset: 0,
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
    hasMore,
    fetchLogs,
    loadMore,
    refresh,
    setFilter,
    currentFilter,
  };
}
