/**
 * useTaskEvents Hook
 *
 * Fetches events directly from task-based API endpoints.
 * Replaces execution-based event fetching.
 */

import { useState, useEffect, useCallback } from 'react';
import { TradingService } from '../api/generated/services/TradingService';
import { TaskType } from '../types/common';

export interface TaskEvent {
  id: number;
  event_type: string;
  severity: string;
  description: string;
  details?: Record<string, unknown>;
  created_at: string;
}

interface UseTaskEventsOptions {
  taskId: number;
  taskType: TaskType;
  eventType?: string;
  severity?: string;
  limit?: number;
  enableRealTimeUpdates?: boolean;
  refreshInterval?: number;
}

interface UseTaskEventsResult {
  events: TaskEvent[];
  isLoading: boolean;
  error: Error | null;
  refetch: () => Promise<void>;
}

export const useTaskEvents = ({
  taskId,
  taskType,
  eventType,
  severity,
  limit = 100,
  enableRealTimeUpdates = false,
  refreshInterval = 5000,
}: UseTaskEventsOptions): UseTaskEventsResult => {
  const [events, setEvents] = useState<TaskEvent[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetchEvents = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);

      const response =
        taskType === TaskType.BACKTEST
          ? await TradingService.tradingTasksBacktestEventsList(
              taskId,
              eventType,
              limit,
              undefined,
              undefined,
              undefined,
              severity
            )
          : await TradingService.tradingTasksTradingEventsList(
              taskId,
              eventType,
              limit,
              undefined,
              undefined,
              undefined,
              severity
            );

      const nextEvents = Array.isArray(response)
        ? response
        : Array.isArray(response?.results)
          ? response.results
          : [];
      setEvents(nextEvents as TaskEvent[]);
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : 'Failed to load events';
      setError(new Error(errorMessage));
    } finally {
      setIsLoading(false);
    }
  }, [taskId, taskType, eventType, severity, limit]);

  useEffect(() => {
    fetchEvents();
  }, [fetchEvents]);

  useEffect(() => {
    if (!enableRealTimeUpdates) return;

    const interval = setInterval(() => {
      fetchEvents();
    }, refreshInterval);

    return () => clearInterval(interval);
  }, [enableRealTimeUpdates, refreshInterval, fetchEvents]);

  return {
    events,
    isLoading,
    error,
    refetch: fetchEvents,
  };
};
