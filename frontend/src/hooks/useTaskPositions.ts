/**
 * useTaskPositions Hook
 *
 * Fetches positions from task-based API endpoints with DRF pagination.
 * Supports incremental fetching via the `since` parameter — during polling
 * cycles only new/updated records are fetched and merged into the local cache,
 * dramatically reducing response sizes and backend load.
 *
 * Uses a monotonic request counter so that late-arriving responses from
 * earlier polling cycles never overwrite fresher data (race-condition fix).
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import axios from 'axios';
import { apiConfig, resolveToken } from '../api/apiConfig';
import { TaskType } from '../types/common';
import { handleAuthErrorStatus } from '../utils/authEvents';

export interface TaskPosition {
  id: string;
  instrument: string;
  direction: 'long' | 'short';
  units: number;
  entry_price: string;
  entry_time: string;
  exit_price?: string | null;
  exit_time?: string | null;
  unrealized_pnl?: string | null;
  is_open: boolean;
  layer_index?: number | null;
  retracement_count?: number | null;
  trade_ids?: string[];
  updated_at?: string | null;
}

interface UseTaskPositionsOptions {
  taskId: string | number;
  taskType: TaskType;
  /** Filter by celery execution ID. When omitted, returns all executions. */
  celeryTaskId?: string;
  status?: 'open' | 'closed';
  direction?: 'long' | 'short';
  page?: number;
  pageSize?: number;
  /** ISO 8601 timestamp — only return records updated after this time. */
  since?: string;
  enableRealTimeUpdates?: boolean;
  refreshInterval?: number;
}

interface UseTaskPositionsResult {
  positions: TaskPosition[];
  totalCount: number;
  hasNext: boolean;
  hasPrevious: boolean;
  isLoading: boolean;
  error: Error | null;
  refetch: () => Promise<void>;
}

/** Extract the latest updated_at from a list of positions. */
function getLatestUpdatedAt(positions: TaskPosition[]): string | null {
  let latest: string | null = null;
  for (const p of positions) {
    if (p.updated_at && (!latest || p.updated_at > latest)) {
      latest = p.updated_at;
    }
  }
  return latest;
}

async function getAuthHeaders(): Promise<Record<string, string>> {
  const headers: Record<string, string> = { Accept: 'application/json' };
  const token = await resolveToken();
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
}

export const useTaskPositions = ({
  taskId,
  taskType,
  celeryTaskId,
  status,
  direction,
  page = 1,
  pageSize = 100,
  since,
  enableRealTimeUpdates = false,
  refreshInterval = 5000,
}: UseTaskPositionsOptions): UseTaskPositionsResult => {
  const [positions, setPositions] = useState<TaskPosition[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [hasNext, setHasNext] = useState(false);
  const [hasPrevious, setHasPrevious] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  // Monotonic counter to discard stale responses.
  const latestRequestRef = useRef(0);

  // Track the latest updated_at for incremental polling.
  const sinceRef = useRef<string | null>(null);
  // Whether we have done the initial full fetch for this set of params.
  const hasInitialFetchRef = useRef(false);

  // Reset incremental state when key params change.
  const paramsKey = `${taskId}-${taskType}-${celeryTaskId}-${status}-${direction}-${page}-${pageSize}-${since ?? ''}`;
  const prevParamsKeyRef = useRef(paramsKey);
  if (paramsKey !== prevParamsKeyRef.current) {
    prevParamsKeyRef.current = paramsKey;
    sinceRef.current = null;
    hasInitialFetchRef.current = false;
  }

  const fetchPositions = useCallback(
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
        if (status) params.position_status = status;
        if (direction) params.direction = direction;
        // Use caller-provided `since` OR our tracked incremental timestamp.
        const effectiveSince = since ?? (incremental ? sinceRef.current : null);
        if (effectiveSince) params.since = effectiveSince;

        const url = `${apiConfig.BASE}${prefix}/${taskId}/positions/`;
        const headers = await getAuthHeaders();

        const response = await axios.get(url, {
          params,
          headers,
          withCredentials: apiConfig.WITH_CREDENTIALS,
        });

        // Discard stale responses.
        if (requestId !== latestRequestRef.current) return;

        const data = response.data;
        const incoming = (data.results || []) as TaskPosition[];

        if (incremental && incoming.length > 0) {
          // Merge: update existing records, append new ones.
          setPositions((prev) => {
            const map = new Map(prev.map((p) => [p.id, p]));
            for (const p of incoming) {
              map.set(p.id, p);
            }
            return Array.from(map.values());
          });
          // Update totalCount from server (it reflects the full count).
          setTotalCount(data.count ?? totalCount);
        } else {
          // Full replace (initial fetch or non-incremental).
          setPositions(incoming);
          setTotalCount(data.count ?? 0);
          setHasNext(Boolean(data.next));
          setHasPrevious(Boolean(data.previous));
        }

        // Track latest updated_at for next incremental poll.
        const latestTs = getLatestUpdatedAt(incoming);
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
            context: 'task_positions',
          });
        }
        const msg =
          err instanceof Error ? err.message : 'Failed to load positions';
        setError(new Error(msg));
      } finally {
        if (requestId === latestRequestRef.current) {
          setIsLoading(false);
        }
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [taskId, taskType, celeryTaskId, status, direction, page, pageSize, since]
  );

  // Initial full fetch.
  useEffect(() => {
    fetchPositions(false);
  }, [fetchPositions]);

  // Incremental polling while task is running.
  useEffect(() => {
    if (!enableRealTimeUpdates) return;
    const interval = setInterval(() => {
      if (hasInitialFetchRef.current) {
        fetchPositions(true);
      }
    }, refreshInterval);
    return () => clearInterval(interval);
  }, [enableRealTimeUpdates, refreshInterval, fetchPositions]);

  // When real-time updates stop (task finished), do one final full refetch.
  const prevRealTimeRef = useRef(enableRealTimeUpdates);
  useEffect(() => {
    if (prevRealTimeRef.current && !enableRealTimeUpdates) {
      sinceRef.current = null;
      hasInitialFetchRef.current = false;
      fetchPositions(false);
    }
    prevRealTimeRef.current = enableRealTimeUpdates;
  }, [enableRealTimeUpdates, fetchPositions]);

  return {
    positions,
    totalCount,
    hasNext,
    hasPrevious,
    isLoading,
    error,
    refetch: () => fetchPositions(false),
  };
};
