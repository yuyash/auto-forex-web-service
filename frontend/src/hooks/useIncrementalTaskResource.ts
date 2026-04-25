import { useCallback, useEffect, useRef, useState } from 'react';
import type { TaskType } from '../types/common';
import { handleAuthErrorStatus } from '../utils/authEvents';
import { logger } from '../utils/logger';
import { usePollingPolicy } from './usePollingPolicy';
import { useSequentialPolling } from './useSequentialPolling';
import { toRefreshActions } from './useTaskCollections';
import {
  fetchTaskResourcePage,
  isApiErrorWithStatus,
} from '../services/api/taskResources';

interface UseIncrementalTaskResourceOptions<TApiItem, TItem> {
  taskId: string | number;
  taskType: TaskType;
  endpoint: string;
  paramsKey: string;
  enabled?: boolean;
  page: number;
  pageSize: number;
  since?: string;
  enableRealTimeUpdates?: boolean;
  refreshInterval?: number;
  errorContext: string;
  fallbackErrorMessage: string;
  buildParams: () => Record<string, string>;
  getLatestCursor: (items: TItem[]) => string | null;
  getItemId: (item: TItem) => string | number;
  mapResults?: (results: TApiItem[]) => TItem[];
  canUseIncrementalPolling?: boolean;
  shouldRefetchIncremental?: (args: {
    serverCount: number | undefined;
    currentItems: TItem[];
    incoming: TItem[];
  }) => boolean;
  mergeIncremental?: (args: {
    currentItems: TItem[];
    incoming: TItem[];
    serverCount: number | undefined;
  }) => TItem[];
}

interface UseIncrementalTaskResourceResult<TItem> {
  items: TItem[];
  totalCount: number;
  hasNext: boolean;
  hasPrevious: boolean;
  isLoading: boolean;
  error: Error | null;
  refresh: () => Promise<unknown>;
}

export function useIncrementalTaskResource<TApiItem, TItem = TApiItem>({
  taskId,
  taskType,
  endpoint,
  paramsKey,
  enabled = true,
  page,
  pageSize,
  since,
  enableRealTimeUpdates = false,
  refreshInterval = 10_000,
  errorContext,
  fallbackErrorMessage,
  buildParams,
  getLatestCursor,
  getItemId,
  mapResults,
  canUseIncrementalPolling = true,
  shouldRefetchIncremental,
  mergeIncremental,
}: UseIncrementalTaskResourceOptions<
  TApiItem,
  TItem
>): UseIncrementalTaskResourceResult<TItem> {
  const [items, setItems] = useState<TItem[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [hasNext, setHasNext] = useState(false);
  const [hasPrevious, setHasPrevious] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const latestRequestRef = useRef(0);
  const sinceRef = useRef<string | null>(null);
  const hasInitialFetchRef = useRef(false);
  const prevParamsKeyRef = useRef(paramsKey);
  const buildParamsRef = useRef(buildParams);
  const getLatestCursorRef = useRef(getLatestCursor);
  const getItemIdRef = useRef(getItemId);
  const mapResultsRef = useRef(mapResults);
  const shouldRefetchIncrementalRef = useRef(shouldRefetchIncremental);
  const mergeIncrementalRef = useRef(mergeIncremental);
  const itemsRef = useRef(items);

  useEffect(() => {
    itemsRef.current = items;
  }, [items]);

  useEffect(() => {
    buildParamsRef.current = buildParams;
  }, [buildParams]);

  useEffect(() => {
    getLatestCursorRef.current = getLatestCursor;
  }, [getLatestCursor]);

  useEffect(() => {
    getItemIdRef.current = getItemId;
  }, [getItemId]);

  useEffect(() => {
    mapResultsRef.current = mapResults;
  }, [mapResults]);

  useEffect(() => {
    shouldRefetchIncrementalRef.current = shouldRefetchIncremental;
  }, [shouldRefetchIncremental]);

  useEffect(() => {
    mergeIncrementalRef.current = mergeIncremental;
  }, [mergeIncremental]);

  if (paramsKey !== prevParamsKeyRef.current) {
    prevParamsKeyRef.current = paramsKey;
    sinceRef.current = null;
    hasInitialFetchRef.current = false;
  }

  const fetchItems = useCallback(
    async (incremental = false) => {
      const activeParamsKey = paramsKey;
      if (!taskId) {
        setItems([]);
        setTotalCount(0);
        setHasNext(false);
        setHasPrevious(false);
        setIsLoading(false);
        return false;
      }

      if (!enabled) {
        setItems([]);
        setTotalCount(0);
        setHasNext(false);
        setHasPrevious(false);
        setIsLoading(false);
        return false;
      }

      const requestId = ++latestRequestRef.current;

      try {
        if (activeParamsKey !== prevParamsKeyRef.current) {
          sinceRef.current = null;
          hasInitialFetchRef.current = false;
        }
        if (!incremental) {
          setIsLoading(true);
        }
        setError(null);

        const params = buildParamsRef.current();
        params.page = String(page);
        params.page_size = String(pageSize);
        const effectiveIncremental = incremental && canUseIncrementalPolling;
        const effectiveSince =
          since ?? (effectiveIncremental ? sinceRef.current : null);
        if (effectiveSince) {
          params.since = effectiveSince;
        }

        const data = await fetchTaskResourcePage<TApiItem>(
          taskType,
          taskId,
          endpoint,
          params
        );
        if (requestId !== latestRequestRef.current) {
          return;
        }

        const incoming = mapResultsRef.current
          ? mapResultsRef.current(data.results)
          : (data.results as unknown as TItem[]);

        if (
          effectiveIncremental &&
          shouldRefetchIncrementalRef.current?.({
            serverCount: data.count,
            currentItems: itemsRef.current,
            incoming,
          })
        ) {
          sinceRef.current = null;
          hasInitialFetchRef.current = false;
          setTimeout(() => {
            void fetchItems(false);
          }, 0);
          return false;
        }

        if (effectiveIncremental && incoming.length > 0) {
          setItems((prev) => {
            if (mergeIncrementalRef.current) {
              return mergeIncrementalRef.current({
                currentItems: prev,
                incoming,
                serverCount: data.count,
              });
            }

            const merged = new Map(
              prev.map((item) => [getItemIdRef.current(item), item])
            );
            for (const item of incoming) {
              merged.set(getItemIdRef.current(item), item);
            }
            return Array.from(merged.values());
          });
          setTotalCount((prev) => data.count ?? prev);
        } else if (!effectiveIncremental) {
          setItems(incoming);
          setTotalCount(data.count ?? 0);
          setHasNext(Boolean(data.next));
          setHasPrevious(Boolean(data.previous));
        }

        const latestCursor = getLatestCursorRef.current(incoming);
        if (
          latestCursor &&
          (!sinceRef.current || latestCursor > sinceRef.current)
        ) {
          sinceRef.current = latestCursor;
        }
        hasInitialFetchRef.current = true;
        return true;
      } catch (err) {
        if (requestId !== latestRequestRef.current) {
          return false;
        }

        if (isApiErrorWithStatus(err)) {
          handleAuthErrorStatus(err.status, {
            source: 'http',
            status: err.status,
            context: errorContext,
          });
        }
        const message =
          err instanceof Error ? err.message : fallbackErrorMessage;
        setError(new Error(message));
        return false;
      } finally {
        if (requestId === latestRequestRef.current) {
          setIsLoading(false);
        }
      }
    },
    [
      endpoint,
      errorContext,
      fallbackErrorMessage,
      page,
      pageSize,
      since,
      taskId,
      taskType,
      enabled,
      canUseIncrementalPolling,
      paramsKey,
    ]
  );

  useEffect(() => {
    void fetchItems(false);
  }, [fetchItems]);

  const pollingPolicy = usePollingPolicy({
    enabled: enableRealTimeUpdates,
    baseIntervalMs: refreshInterval,
  });

  useSequentialPolling(
    async () => {
      if (hasInitialFetchRef.current) {
        const ok = await fetchItems(true);
        if (ok) {
          pollingPolicy.resetFailures();
        } else {
          pollingPolicy.registerFailure();
        }
        return ok;
      }
      return Promise.resolve();
    },
    {
      enabled: pollingPolicy.isActive,
      intervalMs: pollingPolicy.intervalMs,
      onError: (error) => {
        logger.warn('Incremental task resource polling failed', {
          context: errorContext,
          error: error instanceof Error ? error.message : String(error),
        });
      },
    }
  );

  const prevRealTimeRef = useRef(enableRealTimeUpdates);
  useEffect(() => {
    if (prevRealTimeRef.current && !enableRealTimeUpdates) {
      sinceRef.current = null;
      hasInitialFetchRef.current = false;
      void fetchItems(false);
    }
    prevRealTimeRef.current = enableRealTimeUpdates;
  }, [enableRealTimeUpdates, fetchItems]);

  return {
    items,
    totalCount,
    hasNext,
    hasPrevious,
    isLoading,
    error,
    ...toRefreshActions(() => fetchItems(false)),
  };
}
