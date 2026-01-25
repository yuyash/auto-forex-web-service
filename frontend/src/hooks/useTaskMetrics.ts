/**
 * useTaskMetrics Hook
 *
 * Fetches metrics directly from task-based API endpoints.
 * Replaces execution-based metrics fetching.
 */

import { useState, useEffect, useCallback } from 'react';
import { TradingService } from '../api/generated/services/TradingService';
import { TaskType } from '../types/common';

export interface TaskMetric {
  id: number;
  timestamp: string;
  metric_name: string;
  value: number;
  details?: Record<string, unknown>;
}

interface UseTaskMetricsOptions {
  taskId: number;
  taskType: TaskType;
  metricName?: string;
  startTime?: string;
  endTime?: string;
  enableRealTimeUpdates?: boolean;
  refreshInterval?: number;
}

interface UseTaskMetricsResult {
  metrics: TaskMetric[];
  isLoading: boolean;
  error: Error | null;
  refetch: () => Promise<void>;
}

export const useTaskMetrics = ({
  taskId,
  taskType,
  metricName,
  startTime,
  endTime,
  enableRealTimeUpdates = false,
  refreshInterval = 5000,
}: UseTaskMetricsOptions): UseTaskMetricsResult => {
  const [metrics, setMetrics] = useState<TaskMetric[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetchMetrics = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);

      const response =
        taskType === TaskType.BACKTEST
          ? await TradingService.tradingTasksBacktestMetricsList(
              taskId,
              endTime,
              metricName,
              startTime
            )
          : await TradingService.tradingTasksTradingMetricsList(
              taskId,
              endTime,
              metricName,
              startTime
            );

      setMetrics(response.results || []);
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : 'Failed to load metrics';
      setError(new Error(errorMessage));
    } finally {
      setIsLoading(false);
    }
  }, [taskId, taskType, metricName, startTime, endTime]);

  useEffect(() => {
    fetchMetrics();
  }, [fetchMetrics]);

  useEffect(() => {
    if (!enableRealTimeUpdates) return;

    const interval = setInterval(() => {
      fetchMetrics();
    }, refreshInterval);

    return () => clearInterval(interval);
  }, [enableRealTimeUpdates, refreshInterval, fetchMetrics]);

  return {
    metrics,
    isLoading,
    error,
    refetch: fetchMetrics,
  };
};
