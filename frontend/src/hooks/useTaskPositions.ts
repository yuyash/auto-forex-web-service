/**
 * useTaskPositions Hook
 *
 * Fetches positions from task-based API endpoints with DRF pagination.
 * Position polling uses the shared incremental task-resource hook and adds
 * the position-specific reconciliation needed when open positions close.
 */

import { useCallback, useMemo } from 'react';
import type { TaskType } from '../types/common';
import type {
  CurrencyConversionContext,
  MoneyAmountLike,
} from '../types/money';
import { toIncrementalCollectionState } from './useTaskCollections';
import { useIncrementalTaskResource } from './useIncrementalTaskResource';

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
  is_initial_position_seed?: boolean;
  oanda_trade_id?: string | null;
  replayed_at?: string | null;
  unrealized_pnl?: string | null;
  unrealized_pnl_currency?: string | null;
  unrealized_pnl_money?: MoneyAmountLike | null;
  unrealized_pnl_display_money?: MoneyAmountLike | null;
  unrealized_pnl_display_conversion_context?: CurrencyConversionContext | null;
  realized_pnl?: string | null;
  realized_pnl_currency?: string | null;
  realized_pnl_money?: MoneyAmountLike | null;
  realized_pnl_display_money?: MoneyAmountLike | null;
  realized_pnl_display_conversion_context?: CurrencyConversionContext | null;
  is_open: boolean;
  layer_index?: number | null;
  retracement_count?: number | null;
  close_reason?: string | null;
  trade_ids?: string[];
  updated_at?: string | null;
}

export type InitialPositionFilter = 'all' | 'initial' | 'normal';

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
  ordering?: string;
  /** Filter positions by cycle ID (via related trades). */
  cycleId?: string;
  /** Filter positions by position ID prefix (e.g. first 8 chars of UUID). */
  positionId?: string;
  /** Filter positions by initial-position seed marker. */
  initialPositionFilter?: InitialPositionFilter;
  /** ISO 8601 timestamp - only return records updated after this time. */
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
  ordering = '-entry_time',
  cycleId,
  positionId,
  initialPositionFilter = 'all',
  since,
  enableRealTimeUpdates = false,
  refreshInterval = 5_000,
}: UseTaskPositionsOptions): UseTaskPositionsResult => {
  const canUseIncrementalPolling = page === 1;
  const paramsKey = useMemo(
    () =>
      [
        taskId,
        taskType,
        executionRunId ?? '',
        status ?? '',
        direction ?? '',
        page,
        pageSize,
        rangeFrom ?? '',
        rangeTo ?? '',
        includeTradeIds,
        ordering,
        cycleId ?? '',
        positionId ?? '',
        initialPositionFilter,
        since ?? '',
      ].join('|'),
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
      ordering,
      cycleId,
      positionId,
      initialPositionFilter,
      since,
    ]
  );

  const buildParams = useCallback(() => {
    const params: Record<string, string> = {};
    if (executionRunId != null) params.execution_id = String(executionRunId);
    if (status) params.position_status = status;
    if (direction) params.direction = direction;
    if (rangeFrom) params.range_from = rangeFrom;
    if (rangeTo) params.range_to = rangeTo;
    if (includeTradeIds) params.include_trade_ids = 'true';
    if (ordering) params.ordering = ordering;
    if (cycleId) params.cycle_id = cycleId;
    if (positionId) params.position_id = positionId;
    if (initialPositionFilter !== 'all') {
      params.initial_position_filter = initialPositionFilter;
    }
    return params;
  }, [
    executionRunId,
    status,
    direction,
    rangeFrom,
    rangeTo,
    includeTradeIds,
    ordering,
    cycleId,
    positionId,
    initialPositionFilter,
  ]);

  const resource = useIncrementalTaskResource<TaskPosition>({
    taskId,
    taskType,
    endpoint: 'positions',
    paramsKey,
    page,
    pageSize,
    since,
    enableRealTimeUpdates,
    refreshInterval,
    errorContext: 'task_positions',
    fallbackErrorMessage: 'Failed to load positions',
    buildParams,
    getLatestCursor: getLatestUpdatedAt,
    getItemId: (position) => position.id,
    canUseIncrementalPolling,
    shouldRefetchIncremental: ({ serverCount, currentItems }) =>
      serverCount != null && serverCount < currentItems.length,
    mergeIncremental: ({ currentItems, incoming }) => {
      const mergedById = new Map(
        currentItems.map((position) => [position.id, position])
      );
      for (const position of incoming) {
        mergedById.set(position.id, position);
      }
      const merged = Array.from(mergedById.values()).filter((position) => {
        if (status === 'open' && !position.is_open) return false;
        if (status === 'closed' && position.is_open) return false;
        if (initialPositionFilter === 'initial') {
          return position.is_initial_position_seed === true;
        }
        if (initialPositionFilter === 'normal') {
          return position.is_initial_position_seed !== true;
        }
        return true;
      });
      return merged.length > pageSize ? merged.slice(0, pageSize) : merged;
    },
  });

  return {
    ...toIncrementalCollectionState({
      items: resource.items,
      totalCount: resource.totalCount,
      hasNext: resource.hasNext,
      hasPrevious: resource.hasPrevious,
      isLoading: resource.isLoading,
      error: resource.error,
      refresh: resource.refresh,
    }),
    positions: resource.items,
  };
};
