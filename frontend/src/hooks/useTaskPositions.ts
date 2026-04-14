/**
 * useTaskPositions Hook
 *
 * Fetches positions from task-based API endpoints with DRF pagination.
 * Supports incremental fetching via the `since` parameter — during polling
 * cycles only new/updated records are fetched and merged into the local cache,
 * dramatically reducing response sizes and backend load.
 *
 * Uses a monotonic request counter so that late-arriving responses from
 * earlier polling cycles never overwrite fresher data (race-condition fix).
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { TaskType } from '../types/common';
import { handleAuthErrorStatus } from '../utils/authEvents';
import { logger } from '../utils/logger';
import { usePollingPolicy } from './usePollingPolicy';
import { useSequentialPolling } from './useSequentialPolling';
import {
  toIncrementalCollectionState,
  toRefreshActions,
} from './useTaskCollections';
import {
  fetchTaskResourcePage,
  isApiErrorWithStatus,
} from '../services/api/taskResources';

export interface TaskPosition {
  id: string;
  instrument: string;
  direction: 'long' | 'short';
  units: number;
  entry_price: string;
  entry_time: string;
  exit_price?: string | null;
  exit_time?: string | null;
  planned_exit_price?: string | null;
  planned_exit_price_formula?: string | null;
  adverse_pips?: string | null;
  stop_loss_price?: string | null;
  is_rebuild?: boolean;
  oanda_trade_id?: string | null;
  replayed_at?: string | null;
  unrealized_pnl?: string | null;
  is_open: boolean;
  layer_index?: number | null;
  retracement_count?: number | null;
  close_reason?: string | null;
  trade_ids?: string[];
  updated_at?: string | null;
}

interface UseTaskPositionsOptions {
  taskId: string | number;
  taskType: TaskType;
  /** Filter by execution run ID. When omitted, uses the latest execution run. */
  executionRunId?: string;
  status?: 'open' | 'closed';
  direction?: 'long' | 'short';
  page?: number;
  pageSize?: number;
  rangeFrom?: string;
  rangeTo?: string;
  includeTradeIds?: boolean;
  /** Filter positions by cycle ID (via related trades). */
  cycleId?: string;
  /** ISO 8601 timestamp — only return records updated after this time. */
  since?: string;
  enableRealTimeUpdates?: boolean;
  refreshInterval?: number;
}

interface UseTaskPositionsResult {
  positions: TaskPosition[];
  totalCount: number;
  hasNext: boolean;
  hasPrevious: boolean;
  isLoading: boolean;
  error: Error | null;
  refresh: () => Promise<unknown>;
}

/** Extract the latest updated_at from a list of positions. */
function getLatestUpdatedAt(positions: TaskPosition[]): string | null {
  let latest: string | null = null;
  for (const p of positions) {
    if (p.updated_at && (!latest || p.updated_at > latest)) {
      latest = p.updated_at;
    }
  }
  return latest;
}

export const useTaskPositions = ({
  taskId,
  taskType,
  executionRunId,
  status,
  direction,
  page = 1,
  pageSize = 100,
  rangeFrom,
  rangeTo,
  includeTradeIds = false,
  cycleId,
  since,
  enableRealTimeUpdates = false,
  refreshInterval = 5_000,
}: UseTaskPositionsOptions): UseTaskPositionsResult => {
  const [positions, setPositions] = useState<TaskPosition[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [hasNext, setHasNext] = useState(false);
  const [hasPrevious, setHasPrevious] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  // Monotonic counter to discard stale responses.
  const latestRequestRef = useRef(0);

  // Track current cached position count so incremental polls can detect
  // when the server-side count has dropped (positions closed/removed).
  const positionsCountRef = useRef(0);
  useEffect(() => {
    positionsCountRef.current = positions.length;
  }, [positions]);

  // Track the latest updated_at for incremental polling.
  const sinceRef = useRef<string | null>(null);
  // Whether we have done the initial full fetch for this set of params.
  const hasInitialFetchRef = useRef(false);
  const canUseIncrementalPolling = page === 1;

  // Reset incremental state when key params change.
  const paramsKey = `${taskId}-${taskType}-${executionRunId ?? ''}-${status}-${direction}-${page}-${pageSize}-${rangeFrom ?? ''}-${rangeTo ?? ''}-${includeTradeIds}-${cycleId ?? ''}-${since ?? ''}`;
  const prevParamsKeyRef = useRef(paramsKey);
  if (paramsKey !== prevParamsKeyRef.current) {
    prevParamsKeyRef.current = paramsKey;
    sinceRef.current = null;
    hasInitialFetchRef.current = false;
  }

  const fetchPositions = useCallback(
    async (incremental = false) => {
      if (!taskId) {
        setIsLoading(false);
        return false;
      }

      const requestId = ++latestRequestRef.current;

      try {
        if (!incremental) setIsLoading(true);
        setError(null);

        const params: Record<string, string> = {
          page: String(page),
          page_size: String(pageSize),
        };
        if (executionRunId != null) {
          params.execution_id = String(executionRunId);
        }
        if (status) params.position_status = status;
        if (direction) params.direction = direction;
        if (rangeFrom) params.range_from = rangeFrom;
        if (rangeTo) params.range_to = rangeTo;
        if (includeTradeIds) params.include_trade_ids = 'true';
        if (cycleId) params.cycle_id = cycleId;
        // Use caller-provided `since` OR our tracked incremental timestamp.
        const effectiveSince =
          since ??
          (incremental && canUseIncrementalPolling ? sinceRef.current : null);
        if (effectiveSince) params.since = effectiveSince;

        const data = await fetchTaskResourcePage<TaskPosition>(
          taskType,
          taskId,
          'positions',
          params
        );

        // Discard stale responses.
        if (requestId !== latestRequestRef.current) return;

        const incoming = data.results;

        if (incremental) {
          const serverCount = data.count as number | undefined;

          // When the server reports fewer total records than our local cache
          // holds, positions have been removed from this result set (e.g. an
          // open position was closed).  The incremental response won't contain
          // those removed records, so we can't merge them out — fall back to a
          // full refetch to reconcile.
          const needsFullRefetch =
            serverCount != null && serverCount < positionsCountRef.current;

          if (needsFullRefetch) {
            sinceRef.current = null;
            // Re-invoke as a non-incremental fetch to replace the cache.
            // Use setTimeout to avoid calling fetchPositions recursively
            // inside the current execution.
            setTimeout(() => fetchPositions(false), 0);
            return false;
          }

          // Incremental poll: merge new/updated records into the cache.
          // When nothing changed (incoming is empty), leave state untouched.
          if (incoming.length > 0) {
            setPositions((prev) => {
              const map = new Map(prev.map((p) => [p.id, p]));
              for (const p of incoming) {
                map.set(p.id, p);
              }
              // Evict any positions whose is_open status no longer matches
              // the requested filter.  This handles the edge case where the
              // backend returns a recently-closed position in the incremental
              // window before the status filter excludes it.
              const merged = Array.from(map.values()).filter((p) => {
                if (status === 'open') return p.is_open;
                if (status === 'closed') return !p.is_open;
                return true;
              });
              // Cap to pageSize so the table never shows more rows than
              // the current page should contain.
              return merged.length > pageSize
                ? merged.slice(0, pageSize)
                : merged;
            });
          }
          // Always update totalCount from server (it reflects the full count).
          if (serverCount != null) {
            setTotalCount(serverCount);
          }
        } else {
          // Full replace (initial fetch or non-incremental).
          setPositions(incoming);
          setTotalCount(data.count ?? 0);
          setHasNext(Boolean(data.next));
          setHasPrevious(Boolean(data.previous));
        }

        // Track latest updated_at for next incremental poll.
        const latestTs = getLatestUpdatedAt(incoming);
        if (latestTs && (!sinceRef.current || latestTs > sinceRef.current)) {
          sinceRef.current = latestTs;
        }
        hasInitialFetchRef.current = true;
        return true;
      } catch (err) {
        if (requestId !== latestRequestRef.current) return;

        if (isApiErrorWithStatus(err)) {
          handleAuthErrorStatus(err.status, {
            source: 'http',
            status: err.status,
            context: 'task_positions',
          });
        }
        const msg =
          err instanceof Error ? err.message : 'Failed to load positions';
        setError(new Error(msg));
        return false;
      } finally {
        if (requestId === latestRequestRef.current) {
          setIsLoading(false);
        }
      }
    },
    [
      taskId,
      taskType,
      executionRunId,
      status,
      direction,
      page,
      pageSize,
      rangeFrom,
      rangeTo,
      includeTradeIds,
      cycleId,
      since,
      canUseIncrementalPolling,
    ]
  );

  // Initial full fetch.
  useEffect(() => {
    fetchPositions(false);
  }, [fetchPositions]);

  const pollingPolicy = usePollingPolicy({
    enabled: enableRealTimeUpdates,
    baseIntervalMs: refreshInterval,
  });

  useSequentialPolling(
    async () => {
      if (hasInitialFetchRef.current) {
        const ok = await fetchPositions(canUseIncrementalPolling);
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
        logger.warn('Task positions polling failed', {
          error: error instanceof Error ? error.message : String(error),
        });
      },
    }
  );

  // When real-time updates stop (task finished), do one final full refetch.
  const prevRealTimeRef = useRef(enableRealTimeUpdates);
  useEffect(() => {
    if (prevRealTimeRef.current && !enableRealTimeUpdates) {
      sinceRef.current = null;
      hasInitialFetchRef.current = false;
      void fetchPositions(false);
    }
    prevRealTimeRef.current = enableRealTimeUpdates;
  }, [enableRealTimeUpdates, fetchPositions]);

  const refreshActions = toRefreshActions(() => fetchPositions(false));

  return {
    ...toIncrementalCollectionState({
      items: positions,
      totalCount,
      hasNext,
      hasPrevious,
      isLoading,
      error,
      ...refreshActions,
    }),
    positions,
  };
};
