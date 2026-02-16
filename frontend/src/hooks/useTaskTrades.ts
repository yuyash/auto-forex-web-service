/**
 * useTaskTrades Hook
 *
 * Fetches trades directly from task-based API endpoints.
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
}

interface UseTaskTradesOptions {
  taskId: number;
  taskType: TaskType;
  direction?: 'buy' | 'sell';
  enableRealTimeUpdates?: boolean;
  refreshInterval?: number;
}

interface UseTaskTradesResult {
  trades: TaskTrade[];
  isLoading: boolean;
  error: Error | null;
  refetch: () => Promise<void>;
}

export const useTaskTrades = ({
  taskId,
  taskType,
  direction,
  enableRealTimeUpdates = false,
  refreshInterval = 5000,
}: UseTaskTradesOptions): UseTaskTradesResult => {
  const [trades, setTrades] = useState<TaskTrade[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetchTrades = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);

      const response =
        taskType === TaskType.BACKTEST
          ? await TradingService.tradingTasksBacktestTradesList(
              taskId,
              direction
            )
          : await TradingService.tradingTasksTradingTradesList(
              taskId,
              direction
            );

      const nextTrades = Array.isArray(response)
        ? response
        : Array.isArray(response?.results)
          ? response.results
          : [];
      setTrades(nextTrades as TaskTrade[]);
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : 'Failed to load trades';
      setError(new Error(errorMessage));
    } finally {
      setIsLoading(false);
    }
  }, [taskId, taskType, direction]);

  useEffect(() => {
    fetchTrades();
  }, [fetchTrades]);

  useEffect(() => {
    if (!enableRealTimeUpdates) return;

    const interval = setInterval(() => {
      fetchTrades();
    }, refreshInterval);

    return () => clearInterval(interval);
  }, [enableRealTimeUpdates, refreshInterval, fetchTrades]);

  return {
    trades,
    isLoading,
    error,
    refetch: fetchTrades,
  };
};
