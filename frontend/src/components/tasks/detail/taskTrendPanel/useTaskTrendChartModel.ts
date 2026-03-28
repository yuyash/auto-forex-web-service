import { useCallback, useEffect, useMemo, useRef } from 'react';
import { type UTCTimestamp } from 'lightweight-charts';
import type { SelectChangeEvent } from '@mui/material/Select';
import { usePollingPolicy } from '../../../../hooks/usePollingPolicy';
import { useSupportedGranularities } from '../../../../hooks/useMarketConfig';
import { useWindowedCandles } from '../../../../hooks/useWindowedCandles';
import { useWindowedTaskMarkers } from '../../../../hooks/useWindowedTaskMarkers';
import { TaskType } from '../../../../types/common';
import { clampRange, type TimeRange } from '../../../../utils/windowedRanges';
import type { TaskSummary } from '../../../../hooks/useTaskSummary';
import { useTaskStrategyEvents } from '../../../../hooks/useTaskStrategyEvents';
import { useMetricsOverlay } from '../MetricsOverlayChart';
import {
  GRANULARITY_MINUTES,
  isoToSec,
  type CandlePoint,
  type ReplayTrade,
  type TrendPosition,
} from './shared';
import { useTaskTrendChart } from './useTaskTrendChart';
import { useTaskTrendDerivedData } from './useTaskTrendDerivedData';
import { useTaskTrendMarkers } from './useTaskTrendMarkers';
import { useTaskTrendPanelState } from './useTaskTrendPanelState';
import { useTaskTrendReplayData } from './useTaskTrendReplayData';

interface TaskTrendChartModelParams {
  taskId: string | number;
  taskType: TaskType;
  instrument: string;
  executionRunId?: string;
  startTime?: string;
  endTime?: string;
  enableRealTimeUpdates?: boolean;
  currentTick?: { timestamp: string; price: string | null } | null;
  latestExecution?: {
    total_trades?: number;
  };
  summary?: TaskSummary;
  pipSize?: number | null;
  timezone: string;
  isDark: boolean;
  t: (key: string, options?: Record<string, unknown>) => string;
}

export function useTaskTrendChartModel({
  taskId,
  taskType,
  instrument,
  executionRunId,
  startTime,
  endTime,
  enableRealTimeUpdates = false,
  currentTick,
  latestExecution,
  summary,
  timezone,
  isDark,
  t,
}: TaskTrendChartModelParams) {
  const tradesRef = useRef<ReplayTrade[]>([]);
  const panelState = useTaskTrendPanelState({
    taskType,
    taskId,
    executionRunId,
  });
  const realTimePollingPolicy = usePollingPolicy({
    enabled: enableRealTimeUpdates,
    baseIntervalMs: panelState.pollingIntervalMs,
  });
  const realTimeUpdatesEnabled = realTimePollingPolicy.isActive;

  // Fetch strategy cycles to support active cycle filtering
  const { data: strategyCyclesData } = useTaskStrategyEvents({
    taskId,
    taskType,
    executionRunId,
    enableRealTimeUpdates: realTimeUpdatesEnabled,
    refreshInterval: panelState.pollingIntervalMs,
  });

  // Compute active cycle IDs grouped by direction
  const activeCycleSets = useMemo(() => {
    const longIds = new Set<string>();
    const shortIds = new Set<string>();
    for (const cycle of strategyCyclesData?.cycles ?? []) {
      if (cycle.status !== 'active') continue;
      const dir = cycle.direction.toLowerCase();
      if (dir === 'long' || dir === 'buy') {
        longIds.add(cycle.cycle_id);
      } else if (dir === 'short' || dir === 'sell') {
        shortIds.add(cycle.cycle_id);
      }
    }
    return { long: longIds, short: shortIds };
  }, [strategyCyclesData]);

  const { granularities, usingFallback: usingGranularityFallback } =
    useSupportedGranularities();

  const candleState = useWindowedCandles({
    instrument,
    granularity: panelState.granularity,
    startTime,
    endTime,
    initialFocusTime: realTimeUpdatesEnabled
      ? currentTick?.timestamp
      : undefined,
    initialCount: 800,
    edgeCount: 800,
    autoRefresh: false,
    refreshIntervalSeconds: Math.max(
      10,
      Math.floor(panelState.pollingIntervalMs / 1000)
    ),
  });

  const candleErrorMessage = useMemo(() => {
    if (candleState.errorCode === 'NO_OANDA_ACCOUNT') {
      return t('trend.noOandaAccount');
    }
    return candleState.error;
  }, [candleState.error, candleState.errorCode, t]);
  const candleErrorSeverity: 'info' | 'error' =
    candleState.errorCode === 'NO_OANDA_ACCOUNT' ? 'info' : 'error';

  const startTimeSec = useMemo(() => isoToSec(startTime), [startTime]);
  const endTimeSec = useMemo(() => isoToSec(endTime), [endTime]);
  const currentTickSec = useMemo(
    () => isoToSec(currentTick?.timestamp ?? null),
    [currentTick?.timestamp]
  );
  const liveRangeUpperBound = useMemo(() => {
    if (!realTimeUpdatesEnabled) {
      return endTimeSec ?? undefined;
    }
    if (taskType === TaskType.BACKTEST) {
      return endTimeSec ?? currentTickSec ?? undefined;
    }
    return currentTickSec ?? undefined;
  }, [currentTickSec, endTimeSec, realTimeUpdatesEnabled, taskType]);
  const taskDataBounds = useMemo<Partial<TimeRange> | null>(() => {
    const from = startTimeSec ?? undefined;
    const to = liveRangeUpperBound;
    if (from == null && to == null) {
      return null;
    }
    return { from, to };
  }, [liveRangeUpperBound, startTimeSec]);
  const markerDisplayCutoffSec = useMemo(
    () => (realTimeUpdatesEnabled ? currentTickSec : null),
    [currentTickSec, realTimeUpdatesEnabled]
  );

  const candles = useMemo(
    () =>
      candleState.candles
        .filter((c) => {
          if (startTimeSec != null && c.time < startTimeSec) return false;
          if (liveRangeUpperBound != null && c.time > liveRangeUpperBound) {
            return false;
          }
          return true;
        })
        .map((c) => ({ ...c, time: c.time as UTCTimestamp })) as CandlePoint[],
    [candleState.candles, liveRangeUpperBound, startTimeSec]
  );
  const loadedTimeRange = useMemo(() => {
    if (candles.length === 0) {
      return undefined;
    }
    return {
      from: new Date(Number(candles[0].time) * 1000).toISOString(),
      to: new Date(
        Number(candles[candles.length - 1].time) * 1000
      ).toISOString(),
    };
  }, [candles]);
  const granularitySeconds = useMemo(
    () => (GRANULARITY_MINUTES[panelState.granularity] ?? 1) * 60,
    [panelState.granularity]
  );
  const candleTimestamps = useMemo(
    () => candles.map((c) => Number(c.time)),
    [candles]
  );

  const clampTaskRange = useCallback(
    (range: TimeRange): TimeRange | null => {
      if (!taskDataBounds) {
        return range;
      }
      const clamped = clampRange(range, taskDataBounds);
      return clamped.to >= clamped.from ? clamped : null;
    },
    [taskDataBounds]
  );

  const markerState = useWindowedTaskMarkers({
    taskId: String(taskId),
    taskType,
    executionRunId,
    enableRealTimeUpdates: realTimeUpdatesEnabled,
    bounds: taskDataBounds,
    pollTrades: false,
  });

  const replayData = useTaskTrendReplayData({
    taskId,
    taskType,
    executionRunId,
    instrument,
    latestExecution,
    enableRealTimeUpdates: realTimeUpdatesEnabled,
    pollingIntervalMs: panelState.pollingIntervalMs,
    refreshTailCandles: candleState.refreshTail,
    summary,
    loadedTimeRange,
  });

  const derivedData = useTaskTrendDerivedData({
    fetchedPositions: replayData.positions as TrendPosition[],
    granularities,
    instrument,
    startTime,
    endTime,
    currentTickPrice: currentTick?.price ?? null,
  });

  useEffect(() => {
    if (realTimeUpdatesEnabled || candleTimestamps.length === 0) return;
    void markerState.ensureRange({
      from: candleTimestamps[0],
      to: candleTimestamps[candleTimestamps.length - 1],
    });
  }, [candleTimestamps, markerState, realTimeUpdatesEnabled]);

  const chartState = useTaskTrendChart({
    isLoading: candleState.isInitialLoading,
    chartHeight: panelState.chartHeight,
    isDark,
    timezone,
    candles,
    granularity: panelState.granularity,
    granularitySeconds,
    candleDataRanges: candleState.dataRanges,
    startTimeSec,
    endTimeSec,
    currentTick: currentTick ?? null,
    currentTickSec,
    enableRealTimeUpdates: realTimeUpdatesEnabled,
    autoFollow: panelState.autoFollow,
    taskType,
    tradesRef,
    clampTaskRange,
    ensureCandleRange: candleState.ensureRange,
    ensureMarkerRange: markerState.ensureRange,
    setAutoFollow: panelState.setAutoFollow,
    onChartError: panelState.reportChartWarning,
    onTradeMarkerClick: (tradeId) => {
      panelState.setSelectedTradeId((prev) => {
        if (!tradeId || prev === tradeId) {
          panelState.setSelectedPosId(null);
          panelState.setHighlightedTradeIds(new Set());
          return null;
        }
        panelState.chartClickedRef.current = true;
        return tradeId;
      });
    },
  });

  useMetricsOverlay({
    taskId: String(taskId),
    taskType,
    executionRunId,
    enableRealTimeUpdates: realTimeUpdatesEnabled,
    pollingIntervalMs: panelState.pollingIntervalMs,
    chart: chartState.chartInstance,
    candleTimestamps,
    currentTickTimestamp: realTimeUpdatesEnabled
      ? currentTick?.timestamp
      : null,
    programmaticScrollRef: chartState.programmaticScrollRef,
  });

  useEffect(() => {
    const raf = requestAnimationFrame(() => {
      panelState.setGranularity(derivedData.recommendedGranularity);
    });
    return () => cancelAnimationFrame(raf);
  }, [
    derivedData.recommendedGranularity,
    endTime,
    instrument,
    panelState,
    startTime,
  ]);

  useEffect(() => {
    tradesRef.current = replayData.trades;
  }, [replayData.trades]);

  useTaskTrendMarkers({
    candles,
    taskLifecycleEvents: markerState.taskEvents,
    strategyEvents: markerState.strategyEvents,
    trades: replayData.trades,
    selectedTradeId: panelState.selectedTradeId,
    highlightedTradeIds: panelState.highlightedTradeIds,
    markersVisible: panelState.markersVisible,
    startTimeSec,
    endTimeSec,
    markerDisplayCutoffSec,
    markersRef: chartState.markersRef,
    programmaticScrollRef: chartState.programmaticScrollRef,
    reportChartWarning: panelState.reportChartWarning,
  });

  const handleGranularityChange = useCallback(
    (event: SelectChangeEvent) => {
      chartState.storeVisibleRange();
      panelState.setGranularity(String(event.target.value));
    },
    [chartState, panelState]
  );

  return {
    panelState: {
      ...panelState,
      realTimeUpdatesEnabled,
      candleErrorMessage,
      candleErrorSeverity,
      errorCode: candleState.errorCode,
      usingGranularityFallback,
      handleGranularityChange,
    },
    candleState: {
      ...candleState,
      candles,
    },
    replayData,
    derivedData,
    chartState,
    activeCycleSets,
  };
}
