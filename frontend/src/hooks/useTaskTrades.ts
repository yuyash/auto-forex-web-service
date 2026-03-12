/**
 * useTaskTrades Hook
 *
 * Fetches trades from task-based API endpoints with DRF pagination.
 * Supports incremental fetching via the `since` parameter — during polling
 * cycles only new/updated records are fetched and merged into the local cache.
 *
 * Uses axios directly (consistent with useTaskPositions / useTaskOrders)
 * so that the `since` query parameter is sent without depending on the
 * generated OpenAPI client being regenerated.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import axios from 'axios';
import { apiConfig, resolveToken } from '../api/apiConfig';
import { TaskType } from '../types/common';
import { handleAuthErrorStatus } from '../utils/authEvents';

export interface TaskTrade {
  id: number | string;
  sequence: number;
  timestamp: string;
  instrument: string;
  direction: 'long' | 'short' | null | '';
  units: string;
  price: string;
  layer_index?: number | null;
  retracement_count?: number | null;
  execution_method?: string;
  execution_method_display?: string;
  description?: string;
  commission?: string;
  updated_at?: string | null;
}

interface UseTaskTradesOptions {
  taskId: string | number;
  taskType: TaskType;
  /** Filter by execution run ID. When omitted, uses the latest execution run. */
  executionRunId?: string;
  direction?: 'long' | 'short';
  page?: number;
  pageSize?: number;
  /** ISO 8601 timestamp — only return records updated after this time. */
  since?: string;
  enableRealTimeUpdates?: boolean;
  refreshInterval?: number;
}

interface UseTaskTradesResult {
  trades: TaskTrade[];
  totalCount: number;
  hasNext: boolean;
  hasPrevious: boolean;
  isLoading: boolean;
  error: Error | null;
  refetch: () => Promise<void>;
}

async function getAuthHeaders(): Promise<Record<string, string>> {
  const headers: Record<string, string> = { Accept: 'application/json' };
  const token = await resolveToken();
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
}

function getLatestUpdatedAt(trades: TaskTrade[]): string | null {
  let latest: string | null = null;
  for (const t of trades) {
    if (t.updated_at && (!latest || t.updated_at > latest)) {
      latest = t.updated_at;
    }
  }
  return latest;
}

/** Map API direction (buy/sell) to frontend direction (long/short). */
function mapTradeResults(
  rawResults: Array<Record<string, unknown>>,
  page: number,
  pageSize: number
): TaskTrade[] {
  return rawResults.map((t, index) => {
    const rawDir = t.direction;
    let mappedDir: string | null;
    if (rawDir == null || rawDir === '') {
      mappedDir = null;
    } else {
      const dir = String(rawDir).toLowerCase();
      mappedDir = dir === 'buy' ? 'long' : dir === 'sell' ? 'short' : dir;
    }
    const syntheticId =
      t.id ??
      `${(page - 1) * pageSize + index}-${t.timestamp ?? ''}-${t.price ?? ''}`;
    return {
      ...t,
      id: syntheticId,
      direction: mappedDir,
    } as unknown as TaskTrade;
  });
}

export const useTaskTrades = ({
  taskId,
  taskType,
  executionRunId,
  direction,
  page = 1,
  pageSize = 100,
  since,
  enableRealTimeUpdates = false,
  refreshInterval = 10_000,
}: UseTaskTradesOptions): UseTaskTradesResult => {
  const [trades, setTrades] = useState<TaskTrade[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [hasNext, setHasNext] = useState(false);
  const [hasPrevious, setHasPrevious] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const latestRequestRef = useRef(0);
  const sinceRef = useRef<string | null>(null);
  const hasInitialFetchRef = useRef(false);

  // Reset incremental state when key params change.
  const paramsKey = `${taskId}-${taskType}-${executionRunId ?? ''}-${direction}-${page}-${pageSize}-${since ?? ''}`;
  const prevParamsKeyRef = useRef(paramsKey);
  if (paramsKey !== prevParamsKeyRef.current) {
    prevParamsKeyRef.current = paramsKey;
    sinceRef.current = null;
    hasInitialFetchRef.current = false;
  }

  const fetchTrades = useCallback(
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

        const apiDirection =
          direction === 'long'
            ? 'buy'
            : direction === 'short'
              ? 'sell'
              : undefined;

        const params: Record<string, string> = {
          page: String(page),
          page_size: String(pageSize),
        };
        if (executionRunId != null) {
          params.execution_id = String(executionRunId);
        }
        if (apiDirection) params.direction = apiDirection;
        const effectiveSince = since ?? (incremental ? sinceRef.current : null);
        if (effectiveSince) params.since = effectiveSince;

        const url = `${apiConfig.BASE}${prefix}/${taskId}/trades/`;
        const headers = await getAuthHeaders();

        const response = await axios.get(url, {
          params,
          headers,
          withCredentials: apiConfig.WITH_CREDENTIALS,
        });

        if (requestId !== latestRequestRef.current) return;

        const data = response.data;
        const rawResults = (data.results || []) as Array<
          Record<string, unknown>
        >;
        const incoming = mapTradeResults(rawResults, page, pageSize);

        if (incremental && incoming.length > 0) {
          setTrades((prev) => {
            const map = new Map(prev.map((t) => [t.id, t]));
            for (const t of incoming) {
              map.set(t.id, t);
            }
            return Array.from(map.values());
          });
          setTotalCount(data.count ?? totalCount);
        } else if (!incremental) {
          setTrades(incoming);
          setTotalCount(data.count ?? 0);
          setHasNext(Boolean(data.next));
          setHasPrevious(Boolean(data.previous));
        }

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
            context: 'task_trades',
          });
        }
        const errorMessage =
          err instanceof Error ? err.message : 'Failed to load trades';
        setError(new Error(errorMessage));
      } finally {
        if (requestId === latestRequestRef.current) {
          setIsLoading(false);
        }
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [taskId, taskType, executionRunId, direction, page, pageSize, since]
  );

  useEffect(() => {
    fetchTrades(false);
  }, [fetchTrades]);

  useEffect(() => {
    if (!enableRealTimeUpdates) return;
    const interval = setInterval(() => {
      if (hasInitialFetchRef.current) {
        fetchTrades(true);
      }
    }, refreshInterval);
    return () => clearInterval(interval);
  }, [enableRealTimeUpdates, refreshInterval, fetchTrades]);

  // Final full refetch when real-time updates stop.
  const prevRealTimeRef = useRef(enableRealTimeUpdates);
  useEffect(() => {
    if (prevRealTimeRef.current && !enableRealTimeUpdates) {
      sinceRef.current = null;
      hasInitialFetchRef.current = false;
      fetchTrades(false);
    }
    prevRealTimeRef.current = enableRealTimeUpdates;
  }, [enableRealTimeUpdates, fetchTrades]);

  return {
    trades,
    totalCount,
    hasNext,
    hasPrevious,
    isLoading,
    error,
    refetch: () => fetchTrades(false),
  };
};
