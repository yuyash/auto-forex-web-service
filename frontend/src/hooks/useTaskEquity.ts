/**
 * useTaskEquity Hook
 *
 * Fetches equity curve directly from task-based API endpoints.
 */

import { useState, useEffect, useCallback } from 'react';
import { TradingService } from '../api/generated/services/TradingService';
import { TaskType } from '../types/common';

export interface TaskEquityPoint {
  timestamp: string;
  balance: string;
  equity: string;
  realized_pnl: string;
  unrealized_pnl: string;
}

interface UseTaskEquityOptions {
  taskId: number;
  taskType: TaskType;
  enableRealTimeUpdates?: boolean;
  refreshInterval?: number;
}

interface UseTaskEquityResult {
  equityPoints: TaskEquityPoint[];
  isLoading: boolean;
  error: Error | null;
  refetch: () => Promise<void>;
}

export const useTaskEquity = ({
  taskId,
  taskType,
  enableRealTimeUpdates = false,
  refreshInterval = 5000,
}: UseTaskEquityOptions): UseTaskEquityResult => {
  const [equityPoints, setEquityPoints] = useState<TaskEquityPoint[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetchEquity = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);

      const response =
        taskType === TaskType.BACKTEST
          ? await TradingService.tradingTasksBacktestEquitiesList(taskId)
          : await TradingService.tradingTasksTradingEquitiesList(taskId);

      setEquityPoints(Array.isArray(response) ? response : []);
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : 'Failed to load equity data';
      setError(new Error(errorMessage));
    } finally {
      setIsLoading(false);
    }
  }, [taskId, taskType]);

  useEffect(() => {
    fetchEquity();
  }, [fetchEquity]);

  useEffect(() => {
    if (!enableRealTimeUpdates) return;

    const interval = setInterval(() => {
      fetchEquity();
    }, refreshInterval);

    return () => clearInterval(interval);
  }, [enableRealTimeUpdates, refreshInterval, fetchEquity]);

  return {
    equityPoints,
    isLoading,
    error,
    refetch: fetchEquity,
  };
};
