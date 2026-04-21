/**
 * useTaskTrades Hook
 *
 * Fetches trades from task-based API endpoints with DRF pagination.
 * Supports incremental fetching via the `since` parameter — during polling
 * cycles only new/updated records are fetched and merged into the local cache.
 *
 * Uses axios directly (consistent with useTaskPositions / useTaskOrders)
 * so that the `since` query parameter is sent without depending on the
 * generated OpenAPI client being regenerated.
 */

import { TaskType } from '../types/common';
import { toIncrementalCollectionState } from './useTaskCollections';
import { useIncrementalTaskResource } from './useIncrementalTaskResource';

export interface TaskTrade {
  id: number | string;
  sequence: number;
  timestamp: string;
  instrument: string;
  direction: 'long' | 'short' | null | '';
  units: string;
  price: string;
  layer_index?: number | null;
  retracement_count?: number | null;
  execution_method?: string;
  execution_method_display?: string;
  description?: string;
  commission?: string;
  cycle_id?: string | null;
  position_id?: string | null;
  order_id?: string | null;
  oanda_trade_id?: string | null;
  is_rebuild?: boolean;
  stop_loss_price?: string | null;
  pnl?: string | null;
  replayed_at?: string | null;
  updated_at?: string | null;
}

interface UseTaskTradesOptions {
  taskId: string | number;
  taskType: TaskType;
  /** Filter by execution run ID. When omitted, uses the latest execution run. */
  executionRunId?: string;
  enabled?: boolean;
  direction?: 'long' | 'short';
  page?: number;
  pageSize?: number;
  /** Filter trades by cycle ID. */
  cycleId?: string;
  /** Filter trades by trade ID prefix (e.g. first 8 chars of UUID). */
  tradeId?: string;
  ordering?: 'asc' | 'desc';
  /** ISO 8601 timestamp — only return records updated after this time. */
  since?: string;
  /** Filter trades with timestamp >= this value. */
  timestampFrom?: string;
  /** Filter trades with timestamp <= this value. */
  timestampTo?: string;
  enableRealTimeUpdates?: boolean;
  refreshInterval?: number;
}

interface UseTaskTradesResult {
  trades: TaskTrade[];
  totalCount: number;
  hasNext: boolean;
  hasPrevious: boolean;
  isLoading: boolean;
  error: Error | null;
  refresh: () => Promise<unknown>;
}

function getLatestUpdatedAt(trades: TaskTrade[]): string | null {
  let latest: string | null = null;
  for (const t of trades) {
    if (t.updated_at && (!latest || t.updated_at > latest)) {
      latest = t.updated_at;
    }
  }
  return latest;
}

/** Map API direction (buy/sell) to frontend direction (long/short). */
function mapTradeResults(
  rawResults: Array<Record<string, unknown>>,
  page: number,
  pageSize: number
): TaskTrade[] {
  return rawResults.map((t, index) => {
    const rawDir = t.direction;
    let mappedDir: string | null;
    if (rawDir == null || rawDir === '') {
      mappedDir = null;
    } else {
      const dir = String(rawDir).toLowerCase();
      mappedDir = dir === 'buy' ? 'long' : dir === 'sell' ? 'short' : dir;
    }
    const syntheticId =
      t.id ??
      `${(page - 1) * pageSize + index}-${t.timestamp ?? ''}-${t.price ?? ''}`;
    return {
      ...t,
      id: syntheticId,
      direction: mappedDir,
    } as unknown as TaskTrade;
  });
}

export const useTaskTrades = ({
  taskId,
  taskType,
  executionRunId,
  enabled = true,
  direction,
  page = 1,
  pageSize = 100,
  cycleId,
  tradeId,
  ordering = 'asc',
  since,
  timestampFrom,
  timestampTo,
  enableRealTimeUpdates = false,
  refreshInterval = 5_000,
}: UseTaskTradesOptions): UseTaskTradesResult => {
  const paramsKey = `${taskId}-${taskType}-${executionRunId ?? ''}-${direction}-${page}-${pageSize}-${cycleId ?? ''}-${tradeId ?? ''}-${ordering}-${since ?? ''}-${timestampFrom ?? ''}-${timestampTo ?? ''}-${enabled ? 'on' : 'off'}`;
  const {
    items: trades,
    totalCount,
    hasNext,
    hasPrevious,
    isLoading,
    error,
    refresh,
  } = useIncrementalTaskResource<Record<string, unknown>, TaskTrade>({
    taskId,
    taskType,
    endpoint: 'trades',
    paramsKey,
    enabled,
    page,
    pageSize,
    since,
    enableRealTimeUpdates,
    refreshInterval,
    errorContext: 'task_trades',
    fallbackErrorMessage: 'Failed to load trades',
    buildParams: () => {
      const params: Record<string, string> = {};
      if (executionRunId != null) {
        params.execution_id = String(executionRunId);
      }
      if (direction === 'long') params.direction = 'buy';
      if (direction === 'short') params.direction = 'sell';
      if (cycleId) params.cycle_id = cycleId;
      if (tradeId) params.trade_id = tradeId;
      if (timestampFrom) params.timestamp_from = timestampFrom;
      if (timestampTo) params.timestamp_to = timestampTo;
      params.ordering = ordering;
      return params;
    },
    getLatestCursor: getLatestUpdatedAt,
    getItemId: (trade) => trade.id,
    mapResults: (results) => mapTradeResults(results, page, pageSize),
  });

  return {
    ...toIncrementalCollectionState({
      items: trades,
      totalCount,
      hasNext,
      hasPrevious,
      isLoading,
      error,
      refresh,
    }),
    trades,
  };
};
