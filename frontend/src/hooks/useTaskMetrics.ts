/**
 * useTaskMetrics Hook
 *
 * Fetches all metrics for a task execution and provides both the full
 * time-series data (for charts) and the latest snapshot (for overview).
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import type { TaskType } from '../types/common';
import { fetchPaginatedMetrics, type MetricPoint } from '../utils/fetchMetrics';

export interface UseTaskMetricsOptions {
  taskId: string;
  taskType: TaskType;
  executionRunId?: string;
  /** Aggregation interval in minutes (default: 1) */
  interval?: number;
  /** RFC3339 lower-bound timestamp */
  since?: string;
  /** RFC3339 upper-bound timestamp */
  until?: string;
  enabled?: boolean;
  /** Polling interval in ms (0 = no polling) */
  pollingInterval?: number;
}

export interface UseTaskMetricsResult {
  /** Full time-series data */
  data: MetricPoint[];
  /** Latest metric snapshot (last element of data) */
  latest: MetricPoint | null;
  dataSource: string;
  resumeCursorTimestamp: string | null;
  consistencyWarnings: Array<Record<string, unknown>>;
  isLoading: boolean;
  error: Error | null;
  refresh: () => Promise<void>;
}

export function useTaskMetrics({
  taskId,
  taskType,
  executionRunId,
  interval = 1,
  since,
  until,
  enabled = true,
  pollingInterval = 0,
}: UseTaskMetricsOptions): UseTaskMetricsResult {
  const [data, setData] = useState<MetricPoint[]>([]);
  const [dataSource, setDataSource] = useState('unknown');
  const [resumeCursorTimestamp, setResumeCursorTimestamp] = useState<
    string | null
  >(null);
  const [consistencyWarnings, setConsistencyWarnings] = useState<
    Array<Record<string, unknown>>
  >([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const mountedRef = useRef(true);

  const fetchData = useCallback(async () => {
    if (!taskId || !enabled) return;
    setIsLoading(true);
    setError(null);
    try {
      const page = await fetchPaginatedMetrics({
        taskId,
        taskType,
        executionRunId,
        interval: interval > 1 ? interval : undefined,
        since,
        until,
        pageSize: 500,
      });
      if (mountedRef.current) {
        setData(page.results);
        setDataSource(page.data_source);
        setResumeCursorTimestamp(page.resume_cursor_timestamp);
        setConsistencyWarnings(page.consistency_warnings);
      }
    } catch (err) {
      if (mountedRef.current) {
        setError(err instanceof Error ? err : new Error(String(err)));
      }
    } finally {
      if (mountedRef.current) {
        setIsLoading(false);
      }
    }
  }, [taskId, taskType, executionRunId, interval, since, until, enabled]);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    fetchData();
  }, [taskId, taskType, executionRunId, interval, since, until, enabled]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!pollingInterval || pollingInterval <= 0 || !enabled) return;
    const id = setInterval(fetchData, pollingInterval);
    return () => clearInterval(id);
  }, [pollingInterval, fetchData, enabled]);

  const latest = data.length > 0 ? data[data.length - 1] : null;

  return {
    data,
    latest,
    dataSource,
    resumeCursorTimestamp,
    consistencyWarnings,
    isLoading,
    error,
    refresh: fetchData,
  };
}
