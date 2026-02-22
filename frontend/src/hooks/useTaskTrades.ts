/**
 * useTaskTrades Hook
 *
 * Fetches trades from task-based API endpoints with DRF pagination.
 * Supports incremental fetching via the `since` parameter.
 *
 * Uses axios directly (consistent with useTaskPositions / useTaskOrders)
 * so that the `since` query parameter is sent without depending on the
 * generated OpenAPI client being regenerated.
 */

import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { OpenAPI } from '../api/generated/core/OpenAPI';
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
  commission?: string;
}

interface UseTaskTradesOptions {
  taskId: string | number;
  taskType: TaskType;
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

export const useTaskTrades = ({
  taskId,
  taskType,
  direction,
  page = 1,
  pageSize = 100,
  since,
  enableRealTimeUpdates = false,
  refreshInterval = 5000,
}: UseTaskTradesOptions): UseTaskTradesResult => {
  const [trades, setTrades] = useState<TaskTrade[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [hasNext, setHasNext] = useState(false);
  const [hasPrevious, setHasPrevious] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetchTrades = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);

      const prefix =
        taskType === TaskType.BACKTEST
          ? '/api/trading/tasks/backtest'
          : '/api/trading/tasks/trading';

      // Map long/short to buy/sell for the API
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
      if (apiDirection) params.direction = apiDirection;
      if (since) params.since = since;

      const url = `${OpenAPI.BASE}${prefix}/${taskId}/trades/`;

      const headers: Record<string, string> = {
        Accept: 'application/json',
      };
      if (OpenAPI.TOKEN) {
        const token =
          typeof OpenAPI.TOKEN === 'function'
            ? await (OpenAPI.TOKEN as (options: unknown) => Promise<string>)({})
            : OpenAPI.TOKEN;
        if (token) {
          headers['Authorization'] = `Bearer ${token}`;
        }
      }

      const response = await axios.get(url, {
        params,
        headers,
        withCredentials: OpenAPI.WITH_CREDENTIALS,
      });

      const data = response.data;
      const rawResults = (data.results || []) as Array<Record<string, unknown>>;

      // Map buy/sell from API response to long/short
      const mapped = rawResults.map((t, index) => {
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
        return { ...t, id: syntheticId, direction: mappedDir };
      });

      setTrades(mapped as unknown as TaskTrade[]);
      setTotalCount(data.count ?? 0);
      setHasNext(Boolean(data.next));
      setHasPrevious(Boolean(data.previous));
    } catch (err) {
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
      setIsLoading(false);
    }
  }, [taskId, taskType, direction, page, pageSize, since]);

  useEffect(() => {
    fetchTrades();
  }, [fetchTrades]);

  useEffect(() => {
    if (!enableRealTimeUpdates) return;
    const interval = setInterval(fetchTrades, refreshInterval);
    return () => clearInterval(interval);
  }, [enableRealTimeUpdates, refreshInterval, fetchTrades]);

  return {
    trades,
    totalCount,
    hasNext,
    hasPrevious,
    isLoading,
    error,
    refetch: fetchTrades,
  };
};
