import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import axios, { type AxiosResponse } from 'axios';
import { apiConfig, resolveToken } from '../api/apiConfig';
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

async function getHeaders(): Promise<Record<string, string>> {
  const headers: Record<string, string> = { Accept: 'application/json' };
  const token = await resolveToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  return headers;
}

function mergeById<T extends { id: string }>(current: T[], incoming: T[]): T[] {
  const byId = new Map<string, T>();
  for (const item of current) byId.set(item.id, item);
  for (const item of incoming) byId.set(item.id, item);
  return Array.from(byId.values());
}

async function fetchAllPages<
  T extends { next?: string | null; results?: U[] },
  U,
>(
  url: string,
  params: Record<string, string>,
  headers: Record<string, string>
): Promise<U[]> {
  const items: U[] = [];
  let nextUrl: string | null = url;
  let nextParams: Record<string, string> | undefined = params;

  while (nextUrl) {
    const response: AxiosResponse<T> = await axios.get<T>(nextUrl, {
      params: nextParams,
      headers,
      withCredentials: apiConfig.WITH_CREDENTIALS,
    });
    const data: T = response.data;
    if (Array.isArray(data?.results)) {
      items.push(...data.results);
    }
    nextUrl = data?.next ?? null;
    nextParams = undefined;
  }

  return items;
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
  const [strategyState, setStrategyState] = useState<MarkerState<TaskEvent>>({
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
  const latestStrategyCreatedAtRef = useRef<string | null>(null);
  const latestTradeUpdatedAtRef = useRef<string | null>(null);
  const taskLoadedRangesRef = useRef<TimeRange[]>([]);
  const strategyLoadedRangesRef = useRef<TimeRange[]>([]);
  const tradeLoadedRangesRef = useRef<TimeRange[]>([]);
  const strategyFullyLoadedRef = useRef(false);
  const backoffUntilRef = useRef<number>(0);

  const prefix = useMemo(
    () =>
      taskType === TaskType.BACKTEST
        ? `${apiConfig.BASE}/api/trading/tasks/backtest/${taskId}`
        : `${apiConfig.BASE}/api/trading/tasks/trading/${taskId}`,
    [taskId, taskType]
  );

  const fetchEventsInRange = useCallback(
    async (
      endpoint: 'events' | 'strategy-events',
      params: Record<string, string>
    ) => {
      const headers = await getHeaders();
      return fetchAllPages<
        { next?: string | null; results?: TaskEvent[] },
        TaskEvent
      >(`${prefix}/${endpoint}/`, params, headers);
    },
    [prefix]
  );

  const fetchTradesInRange = useCallback(
    async (params: Record<string, string>) => {
      const headers = await getHeaders();
      return fetchAllPages<
        { next?: string | null; results?: WindowedTradeMarker[] },
        WindowedTradeMarker
      >(`${prefix}/trades/`, params, headers);
    },
    [prefix]
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
      const missingStrategy = subtractLoadedRanges(
        buffered,
        strategyFullyLoadedRef.current
          ? [buffered]
          : strategyLoadedRangesRef.current
      );
      const missingTrades = pollTrades
        ? subtractLoadedRanges(buffered, tradeLoadedRangesRef.current)
        : [];
      if (
        missingTask.length === 0 &&
        missingStrategy.length === 0 &&
        missingTrades.length === 0
      ) {
        return;
      }

      setIsLoading(true);
      try {
        for (const missing of missingTask) {
          const results = await fetchEventsInRange('events', {
            scope: 'task',
            page_size: '5000',
            ...(executionRunId ? { execution_id: executionRunId } : {}),
            created_from: new Date(missing.from * 1000).toISOString(),
            created_to: new Date(missing.to * 1000).toISOString(),
          });
          setTaskState((prev) => ({
            items: mergeById(prev.items, results),
            loadedRanges: mergeRanges([...prev.loadedRanges, missing]),
          }));
        }

        if (missingStrategy.length > 0 && !strategyFullyLoadedRef.current) {
          const results = await fetchEventsInRange('strategy-events', {
            page_size: '5000',
            ...(executionRunId ? { execution_id: executionRunId } : {}),
          });
          strategyFullyLoadedRef.current = true;
          setStrategyState((prev) => ({
            items: mergeById(prev.items, results),
            loadedRanges:
              bounds?.from != null || bounds?.to != null
                ? [
                    clampRange(
                      {
                        from: bounds?.from ?? Number.MIN_SAFE_INTEGER,
                        to: bounds?.to ?? Number.MAX_SAFE_INTEGER,
                      },
                      bounds
                    ),
                  ]
                : [buffered],
          }));
        }

        for (const missing of missingTrades) {
          const results = await fetchTradesInRange({
            page_size: '5000',
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
    strategyLoadedRangesRef.current = strategyState.loadedRanges;
  }, [strategyState.loadedRanges]);

  useEffect(() => {
    tradeLoadedRangesRef.current = tradeState.loadedRanges;
  }, [tradeState.loadedRanges]);

  useEffect(() => {
    setTaskState({ loadedRanges: [], items: [] });
    setStrategyState({ loadedRanges: [], items: [] });
    setTradeState({ loadedRanges: [], items: [] });
    latestTaskCreatedAtRef.current = null;
    latestStrategyCreatedAtRef.current = null;
    latestTradeUpdatedAtRef.current = null;
    taskLoadedRangesRef.current = [];
    strategyLoadedRangesRef.current = [];
    tradeLoadedRangesRef.current = [];
    strategyFullyLoadedRef.current = false;
  }, [executionRunId, taskId, taskType]);

  useEffect(() => {
    if (!enableRealTimeUpdates) return;
    const id = window.setInterval(async () => {
      if (document.visibilityState !== 'visible') return;
      if (Date.now() < backoffUntilRef.current) return;
      const headers = await getHeaders();
      const commonParams: Record<string, string> = executionRunId
        ? { execution_id: executionRunId }
        : {};
      try {
        const [taskItems, strategyItems, tradeItems] = await Promise.all([
          fetchAllPages<
            { next?: string | null; results?: TaskEvent[] },
            TaskEvent
          >(
            `${prefix}/events/`,
            {
              ...commonParams,
              scope: 'task',
              page_size: '5000',
              ...(latestTaskCreatedAtRef.current
                ? { since: latestTaskCreatedAtRef.current }
                : {}),
            },
            headers
          ),
          fetchAllPages<
            { next?: string | null; results?: TaskEvent[] },
            TaskEvent
          >(
            `${prefix}/strategy-events/`,
            {
              ...commonParams,
              page_size: '5000',
              ...(latestStrategyCreatedAtRef.current
                ? { since: latestStrategyCreatedAtRef.current }
                : {}),
            },
            headers
          ),
          pollTrades
            ? fetchAllPages<
                { next?: string | null; results?: WindowedTradeMarker[] },
                WindowedTradeMarker
              >(
                `${prefix}/trades/`,
                {
                  ...commonParams,
                  page_size: '5000',
                  ...(latestTradeUpdatedAtRef.current
                    ? { since: latestTradeUpdatedAtRef.current }
                    : {}),
                },
                headers
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
        if (strategyItems.length > 0) {
          latestStrategyCreatedAtRef.current = strategyItems.reduce<
            string | null
          >(
            (latest, item) =>
              !latest || item.created_at > latest ? item.created_at : latest,
            latestStrategyCreatedAtRef.current
          );
          setStrategyState((prev) => ({
            ...prev,
            items: mergeById(prev.items, strategyItems),
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
    }, 10000);
    return () => window.clearInterval(id);
  }, [enableRealTimeUpdates, executionRunId, pollTrades, prefix]);

  useEffect(() => {
    if (taskState.items.length > 0) {
      latestTaskCreatedAtRef.current = taskState.items.reduce<string | null>(
        (latest, item) =>
          !latest || item.created_at > latest ? item.created_at : latest,
        latestTaskCreatedAtRef.current
      );
    }
  }, [taskState.items]);

  useEffect(() => {
    if (strategyState.items.length > 0) {
      latestStrategyCreatedAtRef.current = strategyState.items.reduce<
        string | null
      >(
        (latest, item) =>
          !latest || item.created_at > latest ? item.created_at : latest,
        latestStrategyCreatedAtRef.current
      );
    }
  }, [strategyState.items]);

  return {
    taskEvents: taskState.items,
    strategyEvents: strategyState.items,
    trades: tradeState.items,
    isLoading,
    ensureRange,
  };
}
