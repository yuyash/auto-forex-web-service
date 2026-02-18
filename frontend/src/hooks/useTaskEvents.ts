/**
 * useTaskEvents Hook
 *
 * Fetches events from task-based API endpoints with DRF pagination.
 */

import { useState, useEffect, useCallback } from 'react';
import { TradingService } from '../api/generated/services/TradingService';
import { TaskType } from '../types/common';

export interface TaskEvent {
  id: string;
  event_type: string;
  event_type_display?: string;
  severity: string;
  description: string;
  details?: Record<string, unknown>;
  created_at: string;
}

interface UseTaskEventsOptions {
  taskId: string | number;
  taskType: TaskType;
  eventType?: string;
  severity?: string;
  page?: number;
  pageSize?: number;
  enableRealTimeUpdates?: boolean;
  refreshInterval?: number;
}

interface UseTaskEventsResult {
  events: TaskEvent[];
  totalCount: number;
  hasNext: boolean;
  hasPrevious: boolean;
  isLoading: boolean;
  error: Error | null;
  refetch: () => Promise<void>;
}

export const useTaskEvents = ({
  taskId,
  taskType,
  eventType,
  severity,
  page = 1,
  pageSize = 100,
  enableRealTimeUpdates = false,
  refreshInterval = 5000,
}: UseTaskEventsOptions): UseTaskEventsResult => {
  const [events, setEvents] = useState<TaskEvent[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [hasNext, setHasNext] = useState(false);
  const [hasPrevious, setHasPrevious] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetchEvents = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);

      const response =
        taskType === TaskType.BACKTEST
          ? await TradingService.tradingTasksBacktestEventsList(
              String(taskId),
              undefined, // celeryTaskId
              eventType,
              undefined, // ordering
              page,
              pageSize,
              undefined, // search
              severity
            )
          : await TradingService.tradingTasksTradingEventsList(
              String(taskId),
              undefined, // celeryTaskId
              eventType,
              undefined, // ordering
              page,
              pageSize,
              undefined, // search
              severity
            );

      setEvents((response.results || []) as unknown as TaskEvent[]);
      setTotalCount(response.count ?? 0);
      setHasNext(Boolean(response.next));
      setHasPrevious(Boolean(response.previous));
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : 'Failed to load events';
      setError(new Error(errorMessage));
    } finally {
      setIsLoading(false);
    }
  }, [taskId, taskType, eventType, severity, page, pageSize]);

  useEffect(() => {
    fetchEvents();
  }, [fetchEvents]);

  useEffect(() => {
    if (!enableRealTimeUpdates) return;
    const interval = setInterval(fetchEvents, refreshInterval);
    return () => clearInterval(interval);
  }, [enableRealTimeUpdates, refreshInterval, fetchEvents]);

  return {
    events,
    totalCount,
    hasNext,
    hasPrevious,
    isLoading,
    error,
    refetch: fetchEvents,
  };
};
