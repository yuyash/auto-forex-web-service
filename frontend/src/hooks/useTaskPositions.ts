/**
 * useTaskPositions Hook
 *
 * Fetches positions from task-based API endpoints with DRF pagination.
 * Supports incremental fetching via the `since` parameter.
 */

import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { OpenAPI } from '../api/generated/core/OpenAPI';
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
}

interface UseTaskPositionsOptions {
  taskId: string | number;
  taskType: TaskType;
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

export const useTaskPositions = ({
  taskId,
  taskType,
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

  const fetchPositions = useCallback(async () => {
    if (!taskId) {
      setIsLoading(false);
      return;
    }
    try {
      setIsLoading(true);
      setError(null);

      const prefix =
        taskType === TaskType.BACKTEST
          ? '/api/trading/tasks/backtest'
          : '/api/trading/tasks/trading';

      const params: Record<string, string> = {
        page: String(page),
        page_size: String(pageSize),
      };
      if (status) params.position_status = status;
      if (direction) params.direction = direction;
      if (since) params.since = since;

      const url = `${OpenAPI.BASE}${prefix}/${taskId}/positions/`;

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
      setPositions((data.results || []) as TaskPosition[]);
      setTotalCount(data.count ?? 0);
      setHasNext(Boolean(data.next));
      setHasPrevious(Boolean(data.previous));
    } catch (err) {
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
      setIsLoading(false);
    }
  }, [taskId, taskType, status, direction, page, pageSize, since]);

  useEffect(() => {
    fetchPositions();
  }, [fetchPositions]);

  useEffect(() => {
    if (!enableRealTimeUpdates) return;
    const interval = setInterval(fetchPositions, refreshInterval);
    return () => clearInterval(interval);
  }, [enableRealTimeUpdates, refreshInterval, fetchPositions]);

  return {
    positions,
    totalCount,
    hasNext,
    hasPrevious,
    isLoading,
    error,
    refetch: fetchPositions,
  };
};
