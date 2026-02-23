/**
 * useTaskLogs Hook
 *
 * Fetches logs from task-based API endpoints with DRF pagination.
 * Supports incremental fetching via the `since` parameter — during polling
 * cycles only new records are fetched and merged into the local cache.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import axios from 'axios';
import { OpenAPI } from '../api/generated/core/OpenAPI';
import { TaskType } from '../types/common';
import { handleAuthErrorStatus } from '../utils/authEvents';

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
  page?: number;
  pageSize?: number;
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

async function getAuthHeaders(): Promise<Record<string, string>> {
  const headers: Record<string, string> = { Accept: 'application/json' };
  if (OpenAPI.TOKEN) {
    const token =
      typeof OpenAPI.TOKEN === 'function'
        ? await (OpenAPI.TOKEN as (options: unknown) => Promise<string>)({})
        : OpenAPI.TOKEN;
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
  }
  return headers;
}

function getLatestTimestamp(logs: TaskLog[]): string | null {
  let latest: string | null = null;
  for (const l of logs) {
    if (l.timestamp && (!latest || l.timestamp > latest)) {
      latest = l.timestamp;
    }
  }
  return latest;
}

export const useTaskLogs = ({
  taskId,
  taskType,
  level,
  page = 1,
  pageSize = 100,
  enableRealTimeUpdates = false,
  refreshInterval = 5000,
}: UseTaskLogsOptions): UseTaskLogsResult => {
  const [logs, setLogs] = useState<TaskLog[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [hasNext, setHasNext] = useState(false);
  const [hasPrevious, setHasPrevious] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const latestRequestRef = useRef(0);
  const sinceRef = useRef<string | null>(null);
  const hasInitialFetchRef = useRef(false);

  const paramsKey = `${taskId}-${taskType}-${level}-${page}-${pageSize}`;
  const prevParamsKeyRef = useRef(paramsKey);
  if (paramsKey !== prevParamsKeyRef.current) {
    prevParamsKeyRef.current = paramsKey;
    sinceRef.current = null;
    hasInitialFetchRef.current = false;
  }

  const fetchLogs = useCallback(
    async (incremental = false) => {
      if (!taskId) {
        setIsLoading(false);
        return;
      }

      const requestId = ++latestRequestRef.current;

      try {
        if (!incremental) setIsLoading(true);
        setError(null);

        const prefix =
          taskType === TaskType.BACKTEST
            ? '/api/trading/tasks/backtest'
            : '/api/trading/tasks/trading';

        const params: Record<string, string> = {
          page: String(page),
          page_size: String(pageSize),
        };
        if (level) params.level = level;
        const effectiveSince = incremental ? sinceRef.current : null;
        if (effectiveSince) params.since = effectiveSince;

        const url = `${OpenAPI.BASE}${prefix}/${taskId}/logs/`;
        const headers = await getAuthHeaders();

        const response = await axios.get(url, {
          params,
          headers,
          withCredentials: OpenAPI.WITH_CREDENTIALS,
        });

        if (requestId !== latestRequestRef.current) return;

        const data = response.data;
        const incoming = (data.results || []) as TaskLog[];

        if (incremental && incoming.length > 0) {
          setLogs((prev) => {
            const map = new Map(prev.map((l) => [l.id, l]));
            for (const l of incoming) {
              map.set(l.id, l);
            }
            return Array.from(map.values());
          });
          setTotalCount(data.count ?? totalCount);
        } else if (!incremental) {
          setLogs(incoming);
          setTotalCount(data.count ?? 0);
          setHasNext(Boolean(data.next));
          setHasPrevious(Boolean(data.previous));
        }

        const latestTs = getLatestTimestamp(incoming);
        if (latestTs && (!sinceRef.current || latestTs > sinceRef.current)) {
          sinceRef.current = latestTs;
        }
        hasInitialFetchRef.current = true;
      } catch (err) {
        if (requestId !== latestRequestRef.current) return;

        if (axios.isAxiosError(err) && err.response) {
          handleAuthErrorStatus(err.response.status, {
            source: 'http',
            status: err.response.status,
            context: 'task_logs',
          });
        }
        const msg = err instanceof Error ? err.message : 'Failed to load logs';
        setError(new Error(msg));
      } finally {
        if (requestId === latestRequestRef.current) {
          setIsLoading(false);
        }
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [taskId, taskType, level, page, pageSize]
  );

  useEffect(() => {
    fetchLogs(false);
  }, [fetchLogs]);

  useEffect(() => {
    if (!enableRealTimeUpdates) return;
    const interval = setInterval(() => {
      if (hasInitialFetchRef.current) {
        fetchLogs(true);
      }
    }, refreshInterval);
    return () => clearInterval(interval);
  }, [enableRealTimeUpdates, refreshInterval, fetchLogs]);

  const prevRealTimeRef = useRef(enableRealTimeUpdates);
  useEffect(() => {
    if (prevRealTimeRef.current && !enableRealTimeUpdates) {
      sinceRef.current = null;
      hasInitialFetchRef.current = false;
      fetchLogs(false);
    }
    prevRealTimeRef.current = enableRealTimeUpdates;
  }, [enableRealTimeUpdates, fetchLogs]);

  return {
    logs,
    totalCount,
    hasNext,
    hasPrevious,
    isLoading,
    error,
    refetch: () => fetchLogs(false),
  };
};
