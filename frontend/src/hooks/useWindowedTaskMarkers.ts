import { useCallback, useEffect, useRef, useState } from 'react';
import { TaskType } from '../types/common';
import { type TaskEvent } from './useTaskEvents';
import {
  clampRange,
  type TimeRange,
  expandRange,
  mergeRanges,
  subtractLoadedRanges,
} from '../utils/windowedRanges';
import { getRetryAfterMsFromError } from '../utils/retryAfter';
import { fetchPaginatedTaskResource } from '../services/api/taskResources';
import { usePollingPolicy } from './usePollingPolicy';
import { useSequentialPolling } from './useSequentialPolling';

export interface WindowedTradeMarker {
  id: string;
  direction: 'buy' | 'sell' | 'long' | 'short' | null;
  units: number;
  price: string;
  execution_method?: string;
  timestamp: string;
  position_id?: string | null;
  updated_at?: string | null;
}

interface UseWindowedTaskMarkersOptions {
  taskId: string;
  taskType: TaskType;
  executionRunId?: string;
  enableRealTimeUpdates?: boolean;
  bounds?: Partial<TimeRange> | null;
  pollTrades?: boolean;
}

interface UseWindowedTaskMarkersResult {
  taskEvents: TaskEvent[];
  strategyEvents: TaskEvent[];
  trades: WindowedTradeMarker[];
  isLoading: boolean;
  ensureRange: (range: TimeRange) => Promise<void>;
}

type MarkerState<T> = {
  loadedRanges: TimeRange[];
  items: T[];
};

function mergeById<T extends { id: string }>(current: T[], incoming: T[]): T[] {
  const byId = new Map<string, T>();
  for (const item of current) byId.set(item.id, item);
  for (const item of incoming) byId.set(item.id, item);
  return Array.from(byId.values());
}

export function useWindowedTaskMarkers({
  taskId,
  taskType,
  executionRunId,
  enableRealTimeUpdates = false,
  bounds,
  pollTrades = true,
}: UseWindowedTaskMarkersOptions): UseWindowedTaskMarkersResult {
  const [taskState, setTaskState] = useState<MarkerState<TaskEvent>>({
    loadedRanges: [],
    items: [],
  });
  const [tradeState, setTradeState] = useState<
    MarkerState<WindowedTradeMarker>
  >({
    loadedRanges: [],
    items: [],
  });
  const [isLoading, setIsLoading] = useState(false);
  const latestTaskCreatedAtRef = useRef<string | null>(null);
  const latestTradeUpdatedAtRef = useRef<string | null>(null);
  const taskLoadedRangesRef = useRef<TimeRange[]>([]);
  const tradeLoadedRangesRef = useRef<TimeRange[]>([]);
  const backoffUntilRef = useRef<number>(0);

  const fetchEventsInRange = useCallback(
    async (
      endpoint: 'events' | 'strategy-events',
      params: Record<string, string>
    ) => {
      return fetchPaginatedTaskResource<TaskEvent>(
        taskType,
        taskId,
        endpoint,
        params
      );
    },
    [taskId, taskType]
  );

  const fetchTradesInRange = useCallback(
    async (params: Record<string, string>) => {
      return fetchPaginatedTaskResource<WindowedTradeMarker>(
        taskType,
        taskId,
        'trades',
        params
      );
    },
    [taskId, taskType]
  );

  const ensureRange = useCallback(
    async (range: TimeRange) => {
      if (Date.now() < backoffUntilRef.current) {
        return;
      }
      const buffered = clampRange(expandRange(range, 0.2), bounds);
      if (buffered.to < buffered.from) {
        return;
      }
      const missingTask = subtractLoadedRanges(
        buffered,
        taskLoadedRangesRef.current
      );
      const missingTrades = pollTrades
        ? subtractLoadedRanges(buffered, tradeLoadedRangesRef.current)
        : [];
      if (missingTask.length === 0 && missingTrades.length === 0) {
        return;
      }

      setIsLoading(true);
      try {
        for (const missing of missingTask) {
          const results = await fetchEventsInRange('events', {
            scope: 'task',
            ...(executionRunId ? { execution_id: executionRunId } : {}),
            created_from: new Date(missing.from * 1000).toISOString(),
            created_to: new Date(missing.to * 1000).toISOString(),
          });
          setTaskState((prev) => ({
            items: mergeById(prev.items, results),
            loadedRanges: mergeRanges([...prev.loadedRanges, missing]),
          }));
        }
        for (const missing of missingTrades) {
          const results = await fetchTradesInRange({
            ...(executionRunId ? { execution_id: executionRunId } : {}),
            timestamp_from: new Date(missing.from * 1000).toISOString(),
            timestamp_to: new Date(missing.to * 1000).toISOString(),
          });
          setTradeState((prev) => ({
            items: mergeById(prev.items, results),
            loadedRanges: mergeRanges([...prev.loadedRanges, missing]),
          }));
        }
      } catch (error) {
        const retryAfterMs = getRetryAfterMsFromError(error);
        if (retryAfterMs != null) {
          backoffUntilRef.current = Date.now() + retryAfterMs;
        }
      } finally {
        setIsLoading(false);
      }
    },
    [bounds, executionRunId, fetchEventsInRange, fetchTradesInRange, pollTrades]
  );

  useEffect(() => {
    taskLoadedRangesRef.current = taskState.loadedRanges;
  }, [taskState.loadedRanges]);

  useEffect(() => {
    tradeLoadedRangesRef.current = tradeState.loadedRanges;
  }, [tradeState.loadedRanges]);

  useEffect(() => {
    setTaskState({ loadedRanges: [], items: [] });
    setTradeState({ loadedRanges: [], items: [] });
    latestTaskCreatedAtRef.current = null;
    latestTradeUpdatedAtRef.current = null;
    taskLoadedRangesRef.current = [];
    tradeLoadedRangesRef.current = [];
  }, [executionRunId, taskId, taskType]);

  const refreshLatestMarkers = useCallback(async () => {
    if (document.visibilityState !== 'visible') return;
    if (Date.now() < backoffUntilRef.current) return;
    const commonParams: Record<string, string> = executionRunId
      ? { execution_id: executionRunId }
      : {};
    try {
      const [taskItems, tradeItems] = await Promise.all([
        fetchPaginatedTaskResource<TaskEvent>(taskType, taskId, 'events', {
          ...commonParams,
          scope: 'task',
          ...(latestTaskCreatedAtRef.current
            ? { since: latestTaskCreatedAtRef.current }
            : {}),
        }),
        pollTrades
          ? fetchPaginatedTaskResource<WindowedTradeMarker>(
              taskType,
              taskId,
              'trades',
              {
                ...commonParams,
                ...(latestTradeUpdatedAtRef.current
                  ? { since: latestTradeUpdatedAtRef.current }
                  : {}),
              }
            )
          : Promise.resolve([]),
      ]);

      if (taskItems.length > 0) {
        latestTaskCreatedAtRef.current = taskItems.reduce<string | null>(
          (latest, item) =>
            !latest || item.created_at > latest ? item.created_at : latest,
          latestTaskCreatedAtRef.current
        );
        setTaskState((prev) => ({
          ...prev,
          items: mergeById(prev.items, taskItems),
        }));
      }
      if (tradeItems.length > 0) {
        latestTradeUpdatedAtRef.current = tradeItems.reduce<string | null>(
          (latest, item) =>
            !latest || (item.updated_at ?? '') > latest
              ? (item.updated_at ?? latest)
              : latest,
          latestTradeUpdatedAtRef.current
        );
        setTradeState((prev) => ({
          ...prev,
          items: mergeById(prev.items, tradeItems),
        }));
      }
    } catch (error) {
      const retryAfterMs = getRetryAfterMsFromError(error);
      if (retryAfterMs != null) {
        backoffUntilRef.current = Date.now() + retryAfterMs;
      }
    }
  }, [executionRunId, pollTrades, taskId, taskType]);

  const pollingPolicy = usePollingPolicy({
    enabled: enableRealTimeUpdates,
    baseIntervalMs: 10000,
  });

  useSequentialPolling(refreshLatestMarkers, {
    enabled: pollingPolicy.isActive,
    intervalMs: pollingPolicy.intervalMs,
  });

  useEffect(() => {
    if (taskState.items.length > 0) {
      latestTaskCreatedAtRef.current = taskState.items.reduce<string | null>(
        (latest, item) =>
          !latest || item.created_at > latest ? item.created_at : latest,
        latestTaskCreatedAtRef.current
      );
    }
  }, [taskState.items]);

  return {
    taskEvents: taskState.items,
    strategyEvents: [],
    trades: tradeState.items,
    isLoading,
    ensureRange,
  };
}
