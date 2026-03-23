import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { TaskSummary } from '../../../../hooks/useTaskSummary';
import { useSequentialPolling } from '../../../../hooks/useSequentialPolling';
import { usePollingPolicy } from '../../../../hooks/usePollingPolicy';
import {
  fetchTaskTrendReplay,
  type TaskTrendReplayPosition,
  type TaskTrendReplayTrade,
} from '../../../../services/api/taskResources';
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
  loadedTimeRange?: {
    from?: string | null;
    to?: string | null;
  };
}

const CANDLE_REFRESH_INTERVAL_MS = 60_000;
const MAX_EAGER_REPLAY_TRADE_COUNT = 1_000;

function mapRawTrades(
  rawTrades: Array<Record<string, unknown> | TaskTrendReplayTrade>,
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
  rawTrades: Array<Record<string, unknown> | TaskTrendReplayTrade>
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

function toReplayErrorMessage(error: unknown): string {
  if (error instanceof Error && error.message.trim()) {
    return error.message;
  }
  return 'Failed to refresh replay data. Showing the latest available trades.';
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
  loadedTimeRange,
}: UseTaskTrendReplayDataParams) {
  const [trades, setTrades] = useState<ReplayTrade[]>([]);
  const [positions, setPositions] = useState<TaskTrendReplayPosition[]>([]);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [warningMessage, setWarningMessage] = useState<string | null>(null);
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
  const expectedTotalTrades = replaySummary.totalTrades;
  const shouldUseWindowedInitialFetch =
    expectedTotalTrades > MAX_EAGER_REPLAY_TRADE_COUNT &&
    !!loadedTimeRange?.from &&
    !!loadedTimeRange?.to;

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

        if (isInitialLoad && expectedTotalTrades === 0) {
          setTrades([]);
          setPositions([]);
          setErrorMessage(null);
          setWarningMessage(null);
          return;
        }

        const replayPayload = await fetchTaskTrendReplay(
          taskType,
          String(taskId),
          {
            execution_id: executionRunId,
            since: useIncrementalTrades
              ? (tradeSinceRef.current ?? undefined)
              : undefined,
            range_from: loadedTimeRange?.from ?? undefined,
            range_to: loadedTimeRange?.to ?? undefined,
            page: 1,
            page_size:
              expectedTotalTrades > MAX_EAGER_REPLAY_TRADE_COUNT ? 500 : 1000,
          }
        );
        const rawTrades = replayPayload.trades;
        const incomingPositions = replayPayload.positions;

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
          setPositions((prev) => {
            const mergedById = new Map(
              prev.map((position) => [position.id, position])
            );
            for (const position of incomingPositions) {
              mergedById.set(position.id, position);
            }
            return Array.from(mergedById.values()).sort(
              (a, b) =>
                new Date(b.entry_time).getTime() -
                new Date(a.entry_time).getTime()
            );
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
          setPositions(
            [...incomingPositions].sort(
              (a, b) =>
                new Date(b.entry_time).getTime() -
                new Date(a.entry_time).getTime()
            )
          );
        }
        setErrorMessage(null);
        if (shouldUseWindowedInitialFetch) {
          setWarningMessage(
            'Showing replay trades for the loaded chart range to avoid fetching the full execution history.'
          );
        } else if (replayPayload.meta.has_more_trades) {
          setWarningMessage(
            'Showing the latest replay trades first because this execution has a large trade history.'
          );
        } else {
          setWarningMessage(null);
        }
      } catch (tradeError) {
        setErrorMessage(toReplayErrorMessage(tradeError));
      }
    } catch (error) {
      setErrorMessage(toReplayErrorMessage(error));
    } finally {
      hasLoadedOnce.current = true;
      setIsRefreshing(false);
    }
  }, [
    executionRunId,
    expectedTotalTrades,
    instrument,
    loadedTimeRange?.from,
    loadedTimeRange?.to,
    refreshTailCandles,
    shouldUseWindowedInitialFetch,
    taskId,
    taskType,
  ]);

  useEffect(() => {
    void fetchReplayData();
  }, [fetchReplayData]);
  const pollingPolicy = usePollingPolicy({
    enabled: enableRealTimeUpdates,
    baseIntervalMs: pollingIntervalMs,
  });
  useSequentialPolling(fetchReplayData, {
    enabled: pollingPolicy.isActive,
    intervalMs: pollingPolicy.intervalMs,
  });

  useEffect(() => {
    setTrades([]);
    setPositions([]);
    setIsRefreshing(false);
    setErrorMessage(null);
    setWarningMessage(null);
    hasLoadedOnce.current = false;
    tradeSinceRef.current = null;
    lastCandleFetchRef.current = 0;
  }, [executionRunId, taskId, taskType]);

  return {
    trades,
    positions,
    isRefreshing,
    errorMessage,
    warningMessage,
    replaySummary,
    fetchReplayData,
  };
}
