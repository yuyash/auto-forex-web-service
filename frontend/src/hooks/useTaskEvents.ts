/**
 * useTaskEvents Hook
 *
 * Fetches events from task-based API endpoints with DRF pagination.
 * Supports incremental fetching via the `since` parameter — during polling
 * cycles only new records are fetched and merged into the local cache.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import axios from 'axios';
import { OpenAPI } from '../api/generated/core/OpenAPI';
import { TaskType } from '../types/common';
import { handleAuthErrorStatus } from '../utils/authEvents';

export interface TaskEvent {
  id: string;
  event_type: string;
  event_type_display?: string;
  severity: string;
  description: string;
  details?: Record<string, unknown>;
  created_at: string;
}

interface UseTaskEventsOptions {
  taskId: string | number;
  taskType: TaskType;
  /** Filter by celery execution ID. When omitted, returns all executions. */
  celeryTaskId?: string;
  eventType?: string;
  severity?: string;
  page?: number;
  pageSize?: number;
  enableRealTimeUpdates?: boolean;
  refreshInterval?: number;
}

interface UseTaskEventsResult {
  events: TaskEvent[];
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

function getLatestCreatedAt(events: TaskEvent[]): string | null {
  let latest: string | null = null;
  for (const e of events) {
    if (e.created_at && (!latest || e.created_at > latest)) {
      latest = e.created_at;
    }
  }
  return latest;
}

export const useTaskEvents = ({
  taskId,
  taskType,
  celeryTaskId,
  eventType,
  severity,
  page = 1,
  pageSize = 100,
  enableRealTimeUpdates = false,
  refreshInterval = 5000,
}: UseTaskEventsOptions): UseTaskEventsResult => {
  const [events, setEvents] = useState<TaskEvent[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [hasNext, setHasNext] = useState(false);
  const [hasPrevious, setHasPrevious] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const latestRequestRef = useRef(0);
  const sinceRef = useRef<string | null>(null);
  const hasInitialFetchRef = useRef(false);

  const paramsKey = `${taskId}-${taskType}-${celeryTaskId}-${eventType}-${severity}-${page}-${pageSize}`;
  const prevParamsKeyRef = useRef(paramsKey);
  if (paramsKey !== prevParamsKeyRef.current) {
    prevParamsKeyRef.current = paramsKey;
    sinceRef.current = null;
    hasInitialFetchRef.current = false;
  }

  const fetchEvents = useCallback(
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
        if (celeryTaskId) params.celery_task_id = celeryTaskId;
        if (eventType) params.event_type = eventType;
        if (severity) params.severity = severity;
        const effectiveSince = incremental ? sinceRef.current : null;
        if (effectiveSince) params.since = effectiveSince;

        const url = `${OpenAPI.BASE}${prefix}/${taskId}/events/`;
        const headers = await getAuthHeaders();

        const response = await axios.get(url, {
          params,
          headers,
          withCredentials: OpenAPI.WITH_CREDENTIALS,
        });

        if (requestId !== latestRequestRef.current) return;

        const data = response.data;
        const incoming = (data.results || []) as TaskEvent[];

        if (incremental && incoming.length > 0) {
          setEvents((prev) => {
            const map = new Map(prev.map((e) => [e.id, e]));
            for (const e of incoming) {
              map.set(e.id, e);
            }
            return Array.from(map.values());
          });
          setTotalCount(data.count ?? totalCount);
        } else if (!incremental) {
          setEvents(incoming);
          setTotalCount(data.count ?? 0);
          setHasNext(Boolean(data.next));
          setHasPrevious(Boolean(data.previous));
        }

        const latestTs = getLatestCreatedAt(incoming);
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
            context: 'task_events',
          });
        }
        const msg =
          err instanceof Error ? err.message : 'Failed to load events';
        setError(new Error(msg));
      } finally {
        if (requestId === latestRequestRef.current) {
          setIsLoading(false);
        }
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [taskId, taskType, celeryTaskId, eventType, severity, page, pageSize]
  );

  useEffect(() => {
    fetchEvents(false);
  }, [fetchEvents]);

  useEffect(() => {
    if (!enableRealTimeUpdates) return;
    const interval = setInterval(() => {
      if (hasInitialFetchRef.current) {
        fetchEvents(true);
      }
    }, refreshInterval);
    return () => clearInterval(interval);
  }, [enableRealTimeUpdates, refreshInterval, fetchEvents]);

  const prevRealTimeRef = useRef(enableRealTimeUpdates);
  useEffect(() => {
    if (prevRealTimeRef.current && !enableRealTimeUpdates) {
      sinceRef.current = null;
      hasInitialFetchRef.current = false;
      fetchEvents(false);
    }
    prevRealTimeRef.current = enableRealTimeUpdates;
  }, [enableRealTimeUpdates, fetchEvents]);

  return {
    events,
    totalCount,
    hasNext,
    hasPrevious,
    isLoading,
    error,
    refetch: () => fetchEvents(false),
  };
};
