/**
 * useTaskTrades Hook
 *
 * Fetches trades from task-based API endpoints with DRF pagination.
 */

import { useState, useEffect, useCallback } from 'react';
import { TradingService } from '../api/generated/services/TradingService';
import { TaskType } from '../types/common';

export interface TaskTrade {
  sequence: number;
  timestamp: string;
  instrument: string;
  direction: 'long' | 'short';
  units: string;
  price: string;
  layer_index?: number | null;
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

      // Map long/short back to buy/sell for the API
      const apiDirection =
        direction === 'long'
          ? 'buy'
          : direction === 'short'
            ? 'sell'
            : undefined;

      const response =
        taskType === TaskType.BACKTEST
          ? await TradingService.tradingTasksBacktestTradesList(
              String(taskId),
              undefined, // celeryTaskId
              apiDirection,
              undefined, // ordering
              page,
              pageSize
            )
          : await TradingService.tradingTasksTradingTradesList(
              String(taskId),
              undefined, // celeryTaskId
              apiDirection,
              undefined, // ordering
              page,
              pageSize
            );

      // Map buy/sell from API response to long/short
      const rawResults = (response.results || []) as Array<
        Record<string, unknown>
      >;
      const mapped = rawResults.map((t) => {
        const dir = String(t.direction || '').toLowerCase();
        return {
          ...t,
          direction: dir === 'buy' ? 'long' : dir === 'sell' ? 'short' : dir,
        };
      });
      setTrades(mapped as unknown as TaskTrade[]);
      setTotalCount(response.count ?? 0);
      setHasNext(Boolean(response.next));
      setHasPrevious(Boolean(response.previous));
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : 'Failed to load trades';
      setError(new Error(errorMessage));
    } finally {
      setIsLoading(false);
    }
  }, [taskId, taskType, direction, page, pageSize]);

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
