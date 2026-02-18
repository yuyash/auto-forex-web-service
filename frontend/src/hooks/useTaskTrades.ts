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
  direction: 'buy' | 'sell';
  units: string;
  price: string;
  layer_index?: number | null;
  execution_method?: string;
  pnl?: string;
  commission?: string;
  details?: Record<string, unknown>;
  open_price?: string | null;
  open_timestamp?: string | null;
  close_price?: string | null;
  close_timestamp?: string | null;
}

interface UseTaskTradesOptions {
  taskId: string | number;
  taskType: TaskType;
  direction?: 'buy' | 'sell';
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

      const response =
        taskType === TaskType.BACKTEST
          ? await TradingService.tradingTasksBacktestTradesList(
              String(taskId),
              undefined, // celeryTaskId
              direction,
              undefined, // ordering
              page,
              pageSize
            )
          : await TradingService.tradingTasksTradingTradesList(
              String(taskId),
              undefined, // celeryTaskId
              direction,
              undefined, // ordering
              page,
              pageSize
            );

      setTrades((response.results || []) as unknown as TaskTrade[]);
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
