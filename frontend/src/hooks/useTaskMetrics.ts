/**
 * useTaskMetrics Hook
 *
 * Fetches all metrics for a task execution and provides both the full
 * time-series data (for charts) and the latest snapshot (for overview).
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import type { TaskType } from '../types/common';
import {
  fetchLatestMetrics,
  fetchPaginatedMetrics,
  type MetricPoint,
} from '../utils/fetchMetrics';

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
  /** Fetch the full chart series. Keep false outside the metrics tab. */
  fetchSeries?: boolean;
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
  fetchSeries = true,
  pollingInterval = 0,
}: UseTaskMetricsOptions): UseTaskMetricsResult {
  const [data, setData] = useState<MetricPoint[]>([]);
  const [latest, setLatest] = useState<MetricPoint | null>(null);
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
  const latestTimestampRef = useRef<string | undefined>(undefined);
  const inFlightRef = useRef(false);
  const dataRef = useRef<MetricPoint[]>([]);

  useEffect(() => {
    dataRef.current = data;
  }, [data]);

  const fetchData = useCallback(
    async (incremental = false) => {
      if (!taskId || !enabled) return;
      if (inFlightRef.current) return;
      inFlightRef.current = true;
      setIsLoading(true);
      setError(null);
      try {
        if (!fetchSeries) {
          const latestPage = await fetchLatestMetrics({
            taskId,
            taskType,
            executionRunId,
          });
          if (mountedRef.current) {
            setLatest(latestPage.result);
            setDataSource(latestPage.data_source);
            setResumeCursorTimestamp(latestPage.resume_cursor_timestamp);
            setConsistencyWarnings(latestPage.consistency_warnings);
          }
          return;
        }

        const effectiveSince =
          incremental && !since ? latestTimestampRef.current : since;
        const page = await fetchPaginatedMetrics({
          taskId,
          taskType,
          executionRunId,
          interval: interval > 1 ? interval : undefined,
          since: effectiveSince,
          until,
          pageSize: 500,
          maxPages: incremental ? 2 : 20,
          existingResults: incremental ? dataRef.current : undefined,
        });
        if (mountedRef.current) {
          const deduped = new Map<number, MetricPoint>();
          for (const point of page.results) {
            deduped.set(point.t, point);
          }
          const nextData = Array.from(deduped.values()).sort(
            (a, b) => a.t - b.t
          );
          const nextLatest =
            nextData.length > 0 ? nextData[nextData.length - 1] : null;
          latestTimestampRef.current = nextLatest
            ? new Date(nextLatest.t * 1000).toISOString()
            : latestTimestampRef.current;
          setData(nextData);
          setLatest(nextLatest);
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
        inFlightRef.current = false;
      }
    },
    [
      taskId,
      taskType,
      executionRunId,
      interval,
      since,
      until,
      enabled,
      fetchSeries,
    ]
  );

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    latestTimestampRef.current = undefined;
    if (!fetchSeries) {
      setData([]);
    }
    fetchData();
  }, [
    taskId,
    taskType,
    executionRunId,
    interval,
    since,
    until,
    enabled,
    fetchSeries,
  ]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!pollingInterval || pollingInterval <= 0 || !enabled) return;
    const id = setInterval(() => fetchData(true), pollingInterval);
    return () => clearInterval(id);
  }, [pollingInterval, fetchData, enabled]);

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
