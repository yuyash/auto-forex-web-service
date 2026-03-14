import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  fetchAllTrades,
  fetchTradesSince,
} from '../../../../utils/fetchAllTrades';
import type { TaskSummary } from '../../../../hooks/useTaskSummary';
import { parseUtcTimestamp } from './shared';
import type { ReplaySummary, ReplayTrade } from './shared';
import type { TaskType } from '../../../../types/common';

interface UseTaskTrendReplayDataParams {
  taskId: string | number;
  taskType: TaskType;
  executionRunId?: string;
  instrument: string;
  latestExecution?: {
    total_trades?: number;
  };
  enableRealTimeUpdates: boolean;
  pollingIntervalMs: number;
  refreshTailCandles: () => Promise<number>;
  summary?: TaskSummary;
}

const CANDLE_REFRESH_INTERVAL_MS = 60_000;

function mapRawTrades(
  rawTrades: Array<Record<string, unknown>>,
  instrument: string,
  startSequence = 0
): ReplayTrade[] {
  return rawTrades
    .map((trade, idx): ReplayTrade | null => {
      const timestamp = String(trade.timestamp || '');
      const parsedTime = parseUtcTimestamp(timestamp);
      if (!timestamp || parsedTime === null) return null;

      const rawDirection = trade.direction;
      let direction: 'long' | 'short' | '';
      if (
        rawDirection == null ||
        rawDirection === '' ||
        String(rawDirection).toLowerCase() === 'none'
      ) {
        direction = '';
      } else {
        const normalizedDirection = String(rawDirection).toLowerCase();
        direction =
          normalizedDirection === 'buy'
            ? 'long'
            : normalizedDirection === 'sell'
              ? 'short'
              : (normalizedDirection as 'long' | 'short' | '');
      }

      return {
        id: trade.id ? String(trade.id) : `${timestamp}-${idx}`,
        sequence: startSequence + idx + 1,
        timestamp,
        timeSec: parsedTime,
        instrument: String(trade.instrument || instrument),
        direction,
        units: String(trade.units ?? ''),
        price: String(trade.price ?? ''),
        execution_method: String(trade.execution_method || ''),
        execution_method_display: trade.execution_method_display
          ? String(trade.execution_method_display)
          : undefined,
        layer_index:
          trade.layer_index === null || trade.layer_index === undefined
            ? null
            : Number(trade.layer_index),
        retracement_count:
          trade.retracement_count === null ||
          trade.retracement_count === undefined
            ? null
            : Number(trade.retracement_count),
        position_id:
          trade.position_id === null || trade.position_id === undefined
            ? null
            : String(trade.position_id),
      };
    })
    .filter((trade): trade is ReplayTrade => trade !== null);
}

function getLatestTradeUpdatedAt(
  rawTrades: Array<Record<string, unknown>>
): string | null {
  let latest: string | null = null;
  for (const trade of rawTrades) {
    const updatedAt = trade.updated_at as string | undefined;
    if (updatedAt && (!latest || updatedAt > latest)) {
      latest = updatedAt;
    }
  }
  return latest;
}

export function useTaskTrendReplayData({
  taskId,
  taskType,
  executionRunId,
  instrument,
  latestExecution,
  enableRealTimeUpdates,
  pollingIntervalMs,
  refreshTailCandles,
  summary,
}: UseTaskTrendReplayDataParams) {
  const [trades, setTrades] = useState<ReplayTrade[]>([]);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const hasLoadedOnce = useRef(false);
  const tradeSinceRef = useRef<string | null>(null);
  const lastCandleFetchRef = useRef<number>(0);

  const replaySummary = useMemo<ReplaySummary>(() => {
    const serverRealizedPnl = summary?.pnl.realized ?? 0;
    const serverUnrealizedPnl = summary?.pnl.unrealized ?? 0;
    const serverTotalTrades = summary?.counts.totalTrades ?? 0;
    const serverOpenPositionCount = summary?.counts.openPositions ?? 0;
    const totalTrades =
      typeof latestExecution?.total_trades === 'number'
        ? latestExecution.total_trades
        : serverTotalTrades || trades.length;

    return {
      realizedPnl: Number.isFinite(serverRealizedPnl) ? serverRealizedPnl : 0,
      unrealizedPnl: Number.isFinite(serverUnrealizedPnl)
        ? serverUnrealizedPnl
        : 0,
      totalTrades,
      openPositions: serverOpenPositionCount,
    };
  }, [latestExecution, summary, trades.length]);

  const fetchReplayData = useCallback(async () => {
    const isInitialLoad = !hasLoadedOnce.current;

    try {
      if (!isInitialLoad) {
        setIsRefreshing(true);
      }

      const now = Date.now();
      const shouldRefreshTail =
        !isInitialLoad &&
        now - lastCandleFetchRef.current >= CANDLE_REFRESH_INTERVAL_MS;
      if (shouldRefreshTail) {
        await refreshTailCandles();
        lastCandleFetchRef.current = Date.now();
      }

      try {
        const useIncrementalTrades =
          !isInitialLoad && tradeSinceRef.current !== null;

        const rawTrades = useIncrementalTrades
          ? await fetchTradesSince(
              String(taskId),
              taskType,
              tradeSinceRef.current!,
              executionRunId
            )
          : await fetchAllTrades(String(taskId), taskType, executionRunId);

        const latestUpdatedAt = getLatestTradeUpdatedAt(rawTrades);
        if (
          latestUpdatedAt &&
          (!tradeSinceRef.current || latestUpdatedAt > tradeSinceRef.current)
        ) {
          tradeSinceRef.current = latestUpdatedAt;
        }

        if (useIncrementalTrades && rawTrades.length > 0) {
          const incomingTrades = mapRawTrades(rawTrades, instrument);
          setTrades((prev) => {
            const mergedById = new Map(prev.map((trade) => [trade.id, trade]));
            for (const trade of incomingTrades) {
              mergedById.set(trade.id, trade);
            }
            const mergedTrades = Array.from(mergedById.values()).sort(
              (a, b) =>
                new Date(a.timestamp).getTime() -
                new Date(b.timestamp).getTime()
            );
            mergedTrades.forEach((trade, idx) => {
              trade.sequence = idx + 1;
            });
            return mergedTrades;
          });
        } else if (!useIncrementalTrades) {
          const fullTrades = mapRawTrades(rawTrades, instrument).sort(
            (a, b) =>
              new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
          );
          fullTrades.forEach((trade, idx) => {
            trade.sequence = idx + 1;
          });

          setTrades((prev) => {
            if (
              prev.length === fullTrades.length &&
              prev.length > 0 &&
              prev[prev.length - 1].id === fullTrades[fullTrades.length - 1].id
            ) {
              return prev;
            }
            return fullTrades;
          });
        }
      } catch (tradeError) {
        console.warn('Failed to refresh trade data:', tradeError);
      }
    } catch (error) {
      console.warn('Failed to load replay data:', error);
    } finally {
      hasLoadedOnce.current = true;
      setIsRefreshing(false);
    }
  }, [executionRunId, instrument, refreshTailCandles, taskId, taskType]);

  useEffect(() => {
    void fetchReplayData();
  }, [fetchReplayData]);

  useEffect(() => {
    if (!enableRealTimeUpdates) return;
    const interval = setInterval(() => {
      void fetchReplayData();
    }, pollingIntervalMs);
    return () => clearInterval(interval);
  }, [enableRealTimeUpdates, fetchReplayData, pollingIntervalMs]);

  useEffect(() => {
    setTrades([]);
    setIsRefreshing(false);
    hasLoadedOnce.current = false;
    tradeSinceRef.current = null;
    lastCandleFetchRef.current = 0;
  }, [executionRunId, taskId, taskType]);

  return {
    trades,
    isRefreshing,
    replaySummary,
    fetchReplayData,
  };
}
