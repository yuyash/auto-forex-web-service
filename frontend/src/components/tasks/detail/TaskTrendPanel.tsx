import React, {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import {
  Alert,
  Box,
  CircularProgress,
  LinearProgress,
  Paper,
} from '@mui/material';
import type { SelectChangeEvent } from '@mui/material/Select';
import { useTheme } from '@mui/material/styles';
import { useTranslation } from 'react-i18next';
import { type Time, type UTCTimestamp } from 'lightweight-charts';
import { type TaskSummary } from '../../../hooks/useTaskSummary';
import { useDocumentVisibility } from '../../../hooks/useDocumentVisibility';
import { useSupportedGranularities } from '../../../hooks/useMarketConfig';
import { useTaskPositions } from '../../../hooks/useTaskPositions';
import { TaskType } from '../../../types/common';
import { getTimezoneAbbr } from '../../../utils/chartTimezone';
import { useAuth } from '../../../contexts/AuthContext';
import { useMetricsOverlay } from './MetricsOverlayChart';
import { ColumnConfigDialog } from '../../common/ColumnConfigDialog';
import { useWindowedCandles } from '../../../hooks/useWindowedCandles';
import { useWindowedTaskMarkers } from '../../../hooks/useWindowedTaskMarkers';
import { clampRange, type TimeRange } from '../../../utils/windowedRanges';
import {
  ALLOWED_GRANULARITIES,
  ALLOWED_VALUES,
  GRANULARITY_MINUTES,
  LOT_UNITS,
  POLLING_INTERVAL_OPTIONS,
  findFirstCandleAtOrAfter,
  findLastCandleAtOrBefore,
  isoToSec,
  parseUtcTimestamp,
  recommendGranularity,
  snapToCandleTimeInLoadedRange,
  toEventMarkerTime,
} from './taskTrendPanel/shared';
import type { CandlePoint, ReplayTrade } from './taskTrendPanel/shared';
import { TaskTrendToolbar } from './taskTrendPanel/TaskTrendToolbar';
import { TaskTrendTradesTable } from './taskTrendPanel/TaskTrendTradesTable';
import { TaskTrendPositionsTable } from './taskTrendPanel/TaskTrendPositionsTable';
import type { TrendPosition } from './taskTrendPanel/shared';
import { useTaskTrendChart } from './taskTrendPanel/useTaskTrendChart';
import { useTaskTrendReplayData } from './taskTrendPanel/useTaskTrendReplayData';
import { useTaskTrendTradesTable } from './taskTrendPanel/useTaskTrendTradesTable';
import { useTaskTrendPositionsTable } from './taskTrendPanel/useTaskTrendPositionsTable';

interface TaskTrendPanelProps {
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
  configId?: string;
}

export const TaskTrendPanel: React.FC<TaskTrendPanelProps> = ({
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
  pipSize,
}) => {
  const panelRootRef = useRef<HTMLDivElement | null>(null);
  const tradesRef = useRef<ReplayTrade[]>([]);
  const { user } = useAuth();
  const { t } = useTranslation('common');
  const muiTheme = useTheme();
  const isDark = muiTheme.palette.mode === 'dark';
  const timezone = user?.timezone || 'UTC';
  const [granularity, setGranularity] = useState<string>('M1');
  const [selectedTradeId, setSelectedTradeId] = useState<string | null>(null);
  const [pollingIntervalMs, setPollingIntervalMs] = useState(10_000);
  const isPageVisible = useDocumentVisibility();
  const realTimeUpdatesEnabled = enableRealTimeUpdates && isPageVisible;
  const { granularities } = useSupportedGranularities();
  const {
    candles: windowedCandles,
    isInitialLoading: isLoading,
    isRefreshing: isCandleRefreshing,
    loadingOlder: loadingOlderCandles,
    loadingNewer: loadingNewerCandles,
    error,
    dataRanges: candleDataRanges,
    ensureRange: ensureCandleRange,
    refreshTail: refreshTailCandles,
  } = useWindowedCandles({
    instrument,
    granularity,
    startTime,
    endTime,
    initialFocusTime: realTimeUpdatesEnabled
      ? currentTick?.timestamp
      : undefined,
    initialCount: 800,
    edgeCount: 800,
    autoRefresh: false,
    refreshIntervalSeconds: Math.max(10, Math.floor(pollingIntervalMs / 1000)),
  });
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
  const markerDisplayCutoffSec = useMemo(() => {
    if (!realTimeUpdatesEnabled) {
      return null;
    }
    return currentTickSec;
  }, [currentTickSec, realTimeUpdatesEnabled]);
  const candles = useMemo(
    () =>
      windowedCandles
        .filter((c) => {
          if (startTimeSec != null && c.time < startTimeSec) return false;
          if (liveRangeUpperBound != null && c.time > liveRangeUpperBound)
            return false;
          return true;
        })
        .map((c) => ({
          ...c,
          time: c.time as UTCTimestamp,
        })) as CandlePoint[],
    [liveRangeUpperBound, startTimeSec, windowedCandles]
  );
  const granularitySeconds = useMemo(
    () => (GRANULARITY_MINUTES[granularity] ?? 1) * 60,
    [granularity]
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

  // Fetch positions once and derive open/closed state client-side to avoid
  // duplicating position polling for the trend panel.
  const { positions: fetchedPositions } = useTaskPositions({
    taskId,
    taskType,
    executionRunId,
    pageSize: 5000,
    enableRealTimeUpdates: realTimeUpdatesEnabled,
  });
  const {
    taskEvents: taskLifecycleEvents,
    strategyEvents,
    ensureRange: ensureMarkerRange,
  } = useWindowedTaskMarkers({
    taskId: String(taskId),
    taskType,
    executionRunId,
    enableRealTimeUpdates: realTimeUpdatesEnabled,
    bounds: taskDataBounds,
    pollTrades: false,
  });

  // Auto-follow: track whether the chart should auto-scroll to the position line
  const [autoFollow, setAutoFollow] = useState(true);

  const chartClickedRef = useRef(false);
  const selectedPosRowRef = useRef<HTMLTableRowElement | null>(null);
  const [selectedPosId, setSelectedPosId] = useState<string | null>(null);
  const [highlightedTradeIds, setHighlightedTradeIds] = useState<Set<string>>(
    new Set()
  );

  // Chart height state for draggable separator
  const MIN_CHART_HEIGHT = 200;
  const CHART_HEIGHT_STORAGE_KEY = 'replay-chart-height';
  const [chartHeight, setChartHeight] = useState(() => {
    try {
      const saved = localStorage.getItem(CHART_HEIGHT_STORAGE_KEY);
      if (saved) {
        const parsed = parseInt(saved, 10);
        if (Number.isFinite(parsed) && parsed >= MIN_CHART_HEIGHT)
          return parsed;
      }
    } catch {
      /* ignore */
    }
    return 400;
  });
  const dragRef = useRef<{ startY: number; startHeight: number } | null>(null);

  const handleSeparatorMouseDown = useCallback(
    (e: React.MouseEvent | React.TouchEvent) => {
      e.preventDefault();
      const clientY = 'touches' in e ? e.touches[0].clientY : e.clientY;
      dragRef.current = { startY: clientY, startHeight: chartHeight };

      const onMove = (ev: MouseEvent | TouchEvent) => {
        if (!dragRef.current) return;
        const moveY =
          'touches' in ev ? ev.touches[0].clientY : (ev as MouseEvent).clientY;
        const diff = moveY - dragRef.current.startY;
        const maxHeight = window.innerHeight;
        const newHeight = Math.min(
          maxHeight,
          Math.max(MIN_CHART_HEIGHT, dragRef.current.startHeight + diff)
        );
        setChartHeight(newHeight);
      };

      const onEnd = () => {
        dragRef.current = null;
        document.removeEventListener('mousemove', onMove);
        document.removeEventListener('mouseup', onEnd);
        document.removeEventListener('touchmove', onMove);
        document.removeEventListener('touchend', onEnd);
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
        // Persist final height
        setChartHeight((h) => {
          try {
            localStorage.setItem(CHART_HEIGHT_STORAGE_KEY, String(h));
          } catch {
            /* ignore */
          }
          return h;
        });
      };

      document.body.style.cursor = 'row-resize';
      document.body.style.userSelect = 'none';
      document.addEventListener('mousemove', onMove);
      document.addEventListener('mouseup', onEnd);
      document.addEventListener('touchmove', onMove, { passive: false });
      document.addEventListener('touchend', onEnd);
    },
    [chartHeight]
  );

  const currentPrice =
    currentTick?.price != null ? parseFloat(currentTick.price) : null;
  const { trades, isRefreshing, replaySummary, fetchReplayData } =
    useTaskTrendReplayData({
      taskId,
      taskType,
      executionRunId,
      instrument,
      latestExecution,
      enableRealTimeUpdates: realTimeUpdatesEnabled,
      pollingIntervalMs,
      refreshTailCandles,
      summary,
    });

  // Merge open + closed positions for the Positions panel in the Trend tab
  // Merge open + closed positions, de-duplicate by id, and derive _status
  // from the actual `is_open` field rather than which query returned it.
  // This prevents a position that was just closed from appearing as "open"
  // when the open-positions poll returns stale data while the closed-
  // positions poll already includes the updated record.
  const allPositions = useMemo<TrendPosition[]>(() => {
    return [...fetchedPositions]
      .map((p) => ({
        ...p,
        _status: (p.is_open ? 'open' : 'closed') as 'open' | 'closed',
      }))
      .sort(
        (a, b) =>
          new Date(b.entry_time).getTime() - new Date(a.entry_time).getTime()
      );
  }, [fetchedPositions]);

  // Filtered positions by direction for the split Long/Short tables
  const longPositions = useMemo(
    () => allPositions.filter((p) => p.direction === 'long'),
    [allPositions]
  );
  const shortPositions = useMemo(
    () => allPositions.filter((p) => p.direction === 'short'),
    [allPositions]
  );
  const tradeTable = useTaskTrendTradesTable(trades, timezone);
  const longPositionsTable = useTaskTrendPositionsTable({
    positions: longPositions,
    currentPrice,
    pipSize,
    storageKey: 'trend_long_positions',
    timezone,
  });
  const shortPositionsTable = useTaskTrendPositionsTable({
    positions: shortPositions,
    currentPrice,
    pipSize,
    storageKey: 'trend_short_positions',
    timezone,
  });
  const {
    showOpenOnly: showOpenLongOnly,
    page: longPosPage,
    rowsPerPage: longPosRowsPerPage,
    orderBy: longPosOrderBy,
    order: longPosOrder,
    selectedIds: selectedLongPosIds,
    setPage: setLongPosPage,
    setRowsPerPage: setLongPosRowsPerPage,
    sortedPositions: sortedLongPositions,
    paginatedPositions: paginatedLongPositions,
    isAllPageSelected: isAllLongPosPageSelected,
    colWidths: longPosColWidths,
    createResizeHandle: createLongPosResizeHandle,
    columnConfig: longPosColumnConfig,
    updateColumns: updateLongPosColumns,
    resetToDefaults: resetLongPosDefaults,
    configOpen: longPosConfigOpen,
    setConfigOpen: setLongPosConfigOpen,
    handleSort: handleLongPosSort,
    toggleSelection: toggleLongPosSelection,
    selectAllOnPage: selectAllLongPosOnPage,
    togglePageSelection: toggleLongPosPageSelection,
    resetSelection: resetLongPosSelection,
    copySelectedPositions: copySelectedLongPositions,
    toggleOpenOnly: toggleOpenLongOnly,
  } = longPositionsTable;
  const {
    showOpenOnly: showOpenShortOnly,
    page: shortPosPage,
    rowsPerPage: shortPosRowsPerPage,
    orderBy: shortPosOrderBy,
    order: shortPosOrder,
    selectedIds: selectedShortPosIds,
    setPage: setShortPosPage,
    setRowsPerPage: setShortPosRowsPerPage,
    sortedPositions: sortedShortPositions,
    paginatedPositions: paginatedShortPositions,
    isAllPageSelected: isAllShortPosPageSelected,
    colWidths: shortPosColWidths,
    createResizeHandle: createShortPosResizeHandle,
    columnConfig: shortPosColumnConfig,
    updateColumns: updateShortPosColumns,
    resetToDefaults: resetShortPosDefaults,
    configOpen: shortPosConfigOpen,
    setConfigOpen: setShortPosConfigOpen,
    handleSort: handleShortPosSort,
    toggleSelection: toggleShortPosSelection,
    selectAllOnPage: selectAllShortPosOnPage,
    togglePageSelection: toggleShortPosPageSelection,
    resetSelection: resetShortPosSelection,
    copySelectedPositions: copySelectedShortPositions,
    toggleOpenOnly: toggleOpenShortOnly,
  } = shortPositionsTable;
  const {
    orderBy: tradeOrderBy,
    order: tradeOrder,
    page: tradePage,
    rowsPerPage: tradeRowsPerPage,
    setPage: setTradePage,
    setRowsPerPage: setTradeRowsPerPage,
    selectedRowIds: tradeSelectedRowIds,
    setSelectedRowIds: setTradeSelectedRowIds,
    selectedRowRef: tradeSelectedRowRef,
    sortedTrades,
    paginatedTrades,
    isAllPageSelected: isAllTradePageSelected,
    colWidths: tradeColWidths,
    createResizeHandle: createTradeResizeHandle,
    columnConfig: tradeColumnConfig,
    updateColumns: updateTradeColumns,
    resetToDefaults: resetTradeDefaults,
    configOpen: tradeConfigOpen,
    setConfigOpen: setTradeConfigOpen,
    handleSort: handleTradeSort,
    toggleRowSelection: toggleTradeRowSelection,
    togglePageSelection: toggleTradePageSelection,
    resetSelection: resetTradeSelection,
    copySelectedRows,
    selectAllOnPage: selectAllTradeRowsOnPage,
  } = tradeTable;

  // --- Cross-linking helpers: trade ↔ position (using backend IDs) ---
  const positionById = useMemo(() => {
    const map = new Map<string, (typeof allPositions)[number]>();
    for (const pos of allPositions) map.set(pos.id, pos);
    return map;
  }, [allPositions]);

  const tradeById = useMemo(() => {
    const map = new Map<string, ReplayTrade>();
    for (const t of trades) map.set(t.id, t);
    return map;
  }, [trades]);

  const posToTradeIds = useMemo(() => {
    const map = new Map<string, string[]>();
    for (const pos of allPositions) {
      if (pos.trade_ids && pos.trade_ids.length > 0) {
        map.set(pos.id, pos.trade_ids);
      }
    }
    return map;
  }, [allPositions]);

  const findPositionForTrade = useCallback(
    (trade: ReplayTrade): (typeof allPositions)[number] | null => {
      if (trade.position_id) {
        return positionById.get(trade.position_id) ?? null;
      }
      return null;
    },
    [positionById]
  );

  const findTradeIdsForPosition = useCallback(
    (pos: (typeof allPositions)[number]): string[] => {
      return posToTradeIds.get(pos.id) ?? [];
    },
    [posToTradeIds]
  );

  /** Highlight the related position in the correct Long or Short table. */
  const navigateToPosition = useCallback(
    (pos: (typeof allPositions)[number]) => {
      setSelectedPosId(pos.id);

      if (pos.direction === 'long') {
        const idx = sortedLongPositions.findIndex((p) => p.id === pos.id);
        if (idx !== -1) {
          setLongPosPage(Math.floor(idx / longPosRowsPerPage));
        }
      } else if (pos.direction === 'short') {
        const idx = sortedShortPositions.findIndex((p) => p.id === pos.id);
        if (idx !== -1) {
          setShortPosPage(Math.floor(idx / shortPosRowsPerPage));
        }
      }
    },
    [
      longPosRowsPerPage,
      setLongPosPage,
      setShortPosPage,
      shortPosRowsPerPage,
      sortedLongPositions,
      sortedShortPositions,
    ]
  );

  useEffect(() => {
    if (!chartClickedRef.current || !selectedTradeId) return;
    chartClickedRef.current = false;

    const idx = sortedTrades.findIndex((t) => t.id === selectedTradeId);
    if (idx !== -1) {
      setTradePage(Math.floor(idx / tradeRowsPerPage));
    }

    const highlightReset = requestAnimationFrame(() => {
      setHighlightedTradeIds(new Set());
    });

    // Also highlight the related position
    const trade = trades.find((t) => t.id === selectedTradeId);
    if (trade) {
      const pos = findPositionForTrade(trade);
      if (pos) {
        const relatedTradeIds = findTradeIdsForPosition(pos).filter(
          (tradeId) => tradeId !== selectedTradeId
        );
        const highlightRelatedMarkers = requestAnimationFrame(() => {
          setHighlightedTradeIds(new Set(relatedTradeIds));
        });
        const raf = requestAnimationFrame(() => {
          navigateToPosition(pos);
        });
        return () => {
          cancelAnimationFrame(highlightReset);
          cancelAnimationFrame(highlightRelatedMarkers);
          cancelAnimationFrame(raf);
        };
      } else {
        const raf = requestAnimationFrame(() => {
          setSelectedPosId(null);
        });
        return () => {
          cancelAnimationFrame(highlightReset);
          cancelAnimationFrame(raf);
        };
      }
    }
    return () => cancelAnimationFrame(highlightReset);
  }, [
    selectedTradeId,
    sortedTrades,
    tradeRowsPerPage,
    setTradePage,
    trades,
    findPositionForTrade,
    findTradeIdsForPosition,
    navigateToPosition,
  ]);

  const granularityOptions = useMemo(() => {
    if (granularities.length > 0) {
      return granularities.filter((g) => ALLOWED_VALUES.has(g.value));
    }
    return ALLOWED_GRANULARITIES;
  }, [granularities]);

  const recommendedGranularity = useMemo(() => {
    const availableValues = granularityOptions
      .map((g) => g.value)
      .filter((v) => !!GRANULARITY_MINUTES[v]);
    return recommendGranularity(startTime, endTime, availableValues);
  }, [granularityOptions, startTime, endTime]);

  const pnlCurrency = instrument?.includes('_')
    ? instrument.split('_')[1]
    : 'N/A';

  // Stable reference for candle timestamps passed to useMetricsOverlay
  const candleTimestampsMemo = useMemo(
    () => candles.map((c) => Number(c.time)),
    [candles]
  );

  useEffect(() => {
    if (realTimeUpdatesEnabled || candleTimestampsMemo.length === 0) return;
    void ensureMarkerRange({
      from: candleTimestampsMemo[0],
      to: candleTimestampsMemo[candleTimestampsMemo.length - 1],
    });
  }, [candleTimestampsMemo, ensureMarkerRange, realTimeUpdatesEnabled]);

  const {
    chartContainerRef,
    chartInstance,
    chartRef,
    markersRef,
    programmaticScrollRef,
    storeVisibleRange,
    fitContent,
  } = useTaskTrendChart({
    isLoading,
    chartHeight,
    isDark,
    timezone,
    candles,
    granularity,
    granularitySeconds,
    candleDataRanges,
    startTimeSec,
    endTimeSec,
    currentTick: currentTick ?? null,
    currentTickSec,
    enableRealTimeUpdates: realTimeUpdatesEnabled,
    autoFollow,
    taskType,
    tradesRef,
    clampTaskRange,
    ensureCandleRange,
    ensureMarkerRange,
    setAutoFollow,
    onTradeMarkerClick: (tradeId) => {
      setSelectedTradeId((prev) => {
        if (!tradeId || prev === tradeId) {
          setSelectedPosId(null);
          setHighlightedTradeIds(new Set());
          return null;
        }
        chartClickedRef.current = true;
        return tradeId;
      });
    },
  });

  // Attach metric overlay series (Margin Ratio, ATR, thresholds) to the
  // candlestick chart so they share the exact same X-axis.
  useMetricsOverlay({
    taskId: String(taskId),
    taskType,
    executionRunId,
    enableRealTimeUpdates: realTimeUpdatesEnabled,
    pollingIntervalMs,
    chart: chartInstance,
    candleTimestamps: candleTimestampsMemo,
    currentTickTimestamp: realTimeUpdatesEnabled
      ? currentTick?.timestamp
      : null,
    programmaticScrollRef,
  });
  useEffect(() => {
    const raf = requestAnimationFrame(() => {
      setGranularity(recommendedGranularity);
    });
    return () => cancelAnimationFrame(raf);
  }, [recommendedGranularity, instrument, startTime, endTime]);

  useEffect(() => {
    tradesRef.current = trades;
  }, [trades]);

  // Chart height is managed by flex layout + ResizeObserver

  const eventMarkers = useMemo(() => {
    const candleTimes = candles.map((c) => Number(c.time));
    const markers: Array<{
      time: Time;
      position: 'aboveBar' | 'belowBar';
      shape: 'circle' | 'arrowUp' | 'arrowDown' | 'square';
      color: string;
      text?: string;
      size?: number;
    }> = [];

    for (const event of taskLifecycleEvents) {
      const rawTime = toEventMarkerTime(event);
      if (!rawTime) continue;
      const time = snapToCandleTimeInLoadedRange(Number(rawTime), candleTimes);
      if (!time) continue;
      markers.push({
        time,
        position: 'aboveBar',
        shape: 'circle',
        color: '#2563eb',
        text: event.event_type_display || event.event_type,
      });
    }

    // Trading events (open/close) are intentionally excluded here because
    // tradeMarkers already display the same information with direction and
    // lot size.  Including both would create duplicate overlapping markers.

    for (const event of strategyEvents) {
      const rawTime = toEventMarkerTime(event);
      if (!rawTime) continue;
      const time = snapToCandleTimeInLoadedRange(Number(rawTime), candleTimes);
      if (!time) continue;
      markers.push({
        time,
        position: 'aboveBar',
        shape: 'arrowDown',
        color: '#111111',
        text: event.event_type_display || event.event_type,
      });
    }

    if (startTimeSec != null) {
      const time = findFirstCandleAtOrAfter(startTimeSec, candleTimes);
      if (time) {
        markers.push({
          time,
          position: 'aboveBar',
          shape: 'arrowDown',
          color: '#111111',
          text: 'START',
        });
      }
    }

    if (endTimeSec != null) {
      const time = findLastCandleAtOrBefore(endTimeSec, candleTimes);
      if (time) {
        markers.push({
          time,
          position: 'aboveBar',
          shape: 'arrowDown',
          color: '#111111',
          text: 'STOP',
        });
      }
    }

    return markers
      .filter((marker) => {
        if (markerDisplayCutoffSec == null) {
          return true;
        }
        return Number(marker.time) <= markerDisplayCutoffSec;
      })
      .sort((a, b) => Number(a.time) - Number(b.time));
  }, [
    taskLifecycleEvents,
    strategyEvents,
    candles,
    startTimeSec,
    endTimeSec,
    markerDisplayCutoffSec,
  ]);

  // Update trade markers when trades or selection changes (without resetting the view)
  useEffect(() => {
    if (!markersRef.current) return;
    const candleTimes = candles.map((c) => Number(c.time));

    const tradeMarkers = trades
      .map((t) => {
        const selected =
          t.id === selectedTradeId || highlightedTradeIds.has(t.id);
        const units = Number(t.units);
        const lots = Number.isFinite(units)
          ? Math.abs(units) / LOT_UNITS
          : null;
        const executionMethod = String(t.execution_method || '').toLowerCase();
        const isClose =
          executionMethod === 'take_profit' ||
          executionMethod === 'margin_protection' ||
          executionMethod === 'volatility_lock' ||
          executionMethod === 'close_position' ||
          executionMethod === 'volatility_hedge_neutralize';

        // Resolve direction: use explicit field first, then infer from units sign
        const direction: 'long' | 'short' =
          t.direction === 'long' || t.direction === 'short'
            ? t.direction
            : Number.isFinite(units) && units < 0
              ? 'short'
              : 'long';

        const lotLabel = lots === null ? '' : `${Math.round(lots)}L`;
        const dirLabel = direction.toUpperCase();
        // Open: "OPEN LONG 1L" / "OPEN SHORT 1L", Close: "CLOSE LONG 1L" / "CLOSE SHORT 1L" (grey)
        const text = isClose
          ? `CLOSE ${dirLabel} ${lotLabel}`.trim()
          : `OPEN ${dirLabel} ${lotLabel}`.trim();

        const rawTradeTime = parseUtcTimestamp(t.timestamp);
        const markerTime =
          rawTradeTime != null
            ? snapToCandleTimeInLoadedRange(Number(rawTradeTime), candleTimes)
            : null;

        return {
          time: (markerTime ?? 0) as UTCTimestamp,
          position:
            direction === 'short'
              ? ('aboveBar' as const)
              : ('belowBar' as const),
          shape:
            direction === 'short'
              ? ('arrowDown' as const)
              : ('arrowUp' as const),
          color: selected
            ? '#f59e0b'
            : isClose
              ? '#9ca3af'
              : direction === 'long'
                ? '#16a34a'
                : '#ef4444',
          text,
        };
      })
      .filter((marker) => {
        if (Number(marker.time) <= 0) {
          return false;
        }
        if (markerDisplayCutoffSec == null) {
          return true;
        }
        return Number(marker.time) <= markerDisplayCutoffSec;
      });

    try {
      programmaticScrollRef.current = true;
      const allMarkers = [...eventMarkers, ...tradeMarkers].sort(
        (a, b) => Number(a.time) - Number(b.time)
      );
      markersRef.current.setMarkers(allMarkers);
    } catch (e) {
      console.warn('Failed to set trade markers:', e);
    }
  }, [
    trades,
    candles,
    selectedTradeId,
    highlightedTradeIds,
    eventMarkers,
    markerDisplayCutoffSec,
    markersRef,
    programmaticScrollRef,
  ]);

  const handleGranularityChange = (e: SelectChangeEvent) => {
    storeVisibleRange();
    setGranularity(String(e.target.value));
  };

  const onRowSelect = (row: ReplayTrade) => {
    // Toggle off if the same trade is already selected
    if (row.id === selectedTradeId) {
      setSelectedTradeId(null);
      setSelectedPosId(null);
      setHighlightedTradeIds(new Set());
      return;
    }

    setSelectedTradeId(row.id);
    setHighlightedTradeIds(new Set());
    setAutoFollow(false);

    // Also highlight the related position
    const pos = findPositionForTrade(row);
    if (pos) {
      navigateToPosition(pos);
    } else {
      setSelectedPosId(null);
    }

    const ts = chartRef.current?.timeScale();
    if (!ts) return;

    const range = ts.getVisibleRange();
    if (!range) return;

    const from = Number(range.from);
    const to = Number(range.to);
    const target = Number(row.timeSec);

    // Already visible → just highlight, no scroll
    if (target >= from && target <= to) return;

    // Scroll so the target appears at the centre, keeping the same span
    const span = to - from;
    const half = span / 2;
    programmaticScrollRef.current = true;
    try {
      ts.setVisibleRange({
        from: (target - half) as Time,
        to: (target + half) as Time,
      });
    } catch (e) {
      console.warn('Failed to set visible range on row select:', e);
    }
  };

  const onPosRowSelect = (pos: (typeof allPositions)[number]) => {
    // Toggle off if the same position is already selected
    if (pos.id === selectedPosId) {
      setSelectedPosId(null);
      setSelectedTradeId(null);
      setHighlightedTradeIds(new Set());
      return;
    }

    setSelectedPosId(pos.id);
    setAutoFollow(false);

    // Find related trade IDs from the position's trade_ids
    const relatedTradeIds = findTradeIdsForPosition(pos);
    const relatedIdSet = new Set(relatedTradeIds);
    setHighlightedTradeIds(relatedIdSet);

    // Find the first (open) trade to highlight in the Trades table and scroll chart to it
    // Prefer the earliest trade (the open trade)
    const relatedTrades = relatedTradeIds
      .map((tid) => tradeById.get(tid))
      .filter((t): t is ReplayTrade => t != null)
      .sort(
        (a, b) =>
          new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
      );

    if (relatedTrades.length > 0) {
      const openTrade = relatedTrades[0];
      setSelectedTradeId(openTrade.id);

      // Navigate Trades table to the open trade's page
      const idx = sortedTrades.findIndex((t) => t.id === openTrade.id);
      if (idx !== -1) {
        const targetPage = Math.floor(idx / tradeRowsPerPage);
        setTradePage(targetPage);
      }

      // Scroll chart to show all related markers (open + close).
      // Strategy: keep the current zoom level and only pan horizontally.
      // If the current span is too narrow to contain all markers, zoom out
      // just enough to fit them with some padding.
      const ts = chartRef.current?.timeScale();
      if (ts) {
        const range = ts.getVisibleRange();
        if (range) {
          const from = Number(range.from);
          const to = Number(range.to);
          const span = to - from;

          // Compute the bounding range of all related markers
          const times = relatedTrades.map((t) => Number(t.timeSec));
          const minTime = Math.min(...times);
          const maxTime = Math.max(...times);
          const markerSpan = maxTime - minTime;

          // Add 10% padding on each side so markers aren't at the very edge
          const padding = Math.max(markerSpan * 0.1, span * 0.05);
          const paddedMin = minTime - padding;
          const paddedMax = maxTime + padding;
          const paddedSpan = paddedMax - paddedMin;

          const allVisible = minTime >= from && maxTime <= to;

          if (!allVisible) {
            programmaticScrollRef.current = true;
            try {
              if (paddedSpan <= span) {
                // Current zoom is wide enough — just pan to centre the markers
                const centre = (minTime + maxTime) / 2;
                const half = span / 2;
                ts.setVisibleRange({
                  from: (centre - half) as Time,
                  to: (centre + half) as Time,
                });
              } else {
                // Need to zoom out to fit all markers
                ts.setVisibleRange({
                  from: paddedMin as Time,
                  to: paddedMax as Time,
                });
              }
            } catch (e) {
              console.warn(
                'Failed to set visible range on position select:',
                e
              );
            }
          }
        }
      }
    } else {
      setSelectedTradeId(null);
    }
  };

  if (isLoading) {
    return (
      <Box
        ref={panelRootRef}
        sx={{ p: 4, display: 'flex', justifyContent: 'center' }}
      >
        <CircularProgress />
      </Box>
    );
  }

  if (error && candles.length === 0) {
    return (
      <Box ref={panelRootRef} sx={{ p: 3 }}>
        <Alert severity="error">{error}</Alert>
      </Box>
    );
  }

  return (
    <Box
      ref={panelRootRef}
      sx={{
        p: 2,
        pt: 0,
        pb: 2,
        boxSizing: 'border-box',
      }}
    >
      {error && (
        <Alert severity="warning" sx={{ mb: 1 }}>
          {error}
        </Alert>
      )}
      <TaskTrendToolbar
        replaySummary={replaySummary}
        pnlCurrency={pnlCurrency}
        executionRunId={executionRunId}
        isRefreshing={isRefreshing}
        isCandleRefreshing={isCandleRefreshing}
        pollingIntervalMs={pollingIntervalMs}
        granularity={granularity}
        granularityOptions={granularityOptions}
        pollingIntervalOptions={POLLING_INTERVAL_OPTIONS}
        enableRealTimeUpdates={enableRealTimeUpdates}
        autoFollow={autoFollow}
        onPollingIntervalChange={setPollingIntervalMs}
        onGranularityChange={handleGranularityChange}
        onFollow={() => {
          setAutoFollow(true);
          setSelectedTradeId(null);
          setTradeSelectedRowIds(new Set());
          setSelectedPosId(null);
          setHighlightedTradeIds(new Set());
          setTradePage(0);
        }}
        onResetZoom={() => {
          fitContent();
        }}
      />

      <Paper
        variant="outlined"
        sx={{
          mt: 0,
          mb: 0,
          height: chartHeight,
          minHeight: MIN_CHART_HEIGHT,
          display: 'flex',
          position: 'relative',
        }}
      >
        {(loadingOlderCandles || loadingNewerCandles) && (
          <Box
            sx={{
              position: 'absolute',
              top: 0,
              left: 0,
              right: 0,
              zIndex: 3,
              display: 'flex',
              gap: 1,
              px: 1,
              pt: 0.5,
            }}
          >
            <Box
              sx={{
                flex: 1,
                visibility: loadingOlderCandles ? 'visible' : 'hidden',
              }}
            >
              <LinearProgress color="inherit" />
            </Box>
            <Box
              sx={{
                flex: 1,
                visibility: loadingNewerCandles ? 'visible' : 'hidden',
              }}
            >
              <LinearProgress color="inherit" />
            </Box>
          </Box>
        )}
        <Box ref={chartContainerRef} sx={{ width: '100%', flex: 1 }} />
        {/* Timezone indicator (bottom-right) */}
        <Box
          sx={{
            position: 'absolute',
            bottom: 8,
            right: 8,
            zIndex: 2,
            fontSize: '11px',
            fontFamily:
              '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
            color: isDark ? 'rgba(255,255,255,0.45)' : 'rgba(51,65,85,0.5)',
            pointerEvents: 'none',
            userSelect: 'none',
          }}
        >
          TZ: {getTimezoneAbbr(timezone)}
        </Box>
      </Paper>

      {/* Draggable separator */}
      <Box
        onMouseDown={handleSeparatorMouseDown}
        onTouchStart={handleSeparatorMouseDown}
        sx={{
          height: 8,
          cursor: 'row-resize',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          '&:hover': { '& > div': { backgroundColor: 'primary.main' } },
        }}
      >
        <Box
          sx={{
            width: 40,
            height: 3,
            borderRadius: 1.5,
            backgroundColor: 'divider',
            transition: 'background-color 0.15s',
          }}
        />
      </Box>

      <Box
        sx={{
          display: 'flex',
          flexDirection: { xs: 'column', lg: 'row' },
          gap: 2,
          mt: 0.5,
          alignItems: 'flex-start',
        }}
      >
        {/* Left column: Trades */}
        <Box
          sx={{
            flex: 1,
            minWidth: 0,
            display: 'flex',
            flexDirection: 'column',
          }}
        >
          <TaskTrendTradesTable
            trades={sortedTrades}
            paginatedTrades={paginatedTrades}
            selectedTradeId={selectedTradeId}
            highlightedTradeIds={highlightedTradeIds}
            selectedRowIds={tradeSelectedRowIds}
            isAllPageSelected={isAllTradePageSelected}
            isRefreshing={isRefreshing}
            orderBy={tradeOrderBy}
            order={tradeOrder}
            replayColWidths={tradeColWidths}
            page={tradePage}
            rowsPerPage={tradeRowsPerPage}
            timezone={timezone}
            selectedRowRef={tradeSelectedRowRef}
            onConfigureColumns={() => setTradeConfigOpen(true)}
            onCopySelected={copySelectedRows}
            onSelectAllOnPage={selectAllTradeRowsOnPage}
            onResetSelection={resetTradeSelection}
            onReload={fetchReplayData}
            onSelectTrade={onRowSelect}
            onToggleRowSelection={toggleTradeRowSelection}
            onTogglePageSelection={toggleTradePageSelection}
            onSort={handleTradeSort}
            onPageChange={(_e, newPage) => setTradePage(newPage)}
            onRowsPerPageChange={(e) => {
              const newVal = parseInt(e.target.value, 10);
              setTradeRowsPerPage(newVal);
              setTradePage(0);
              setLongPosRowsPerPage(newVal);
              setLongPosPage(0);
              setShortPosRowsPerPage(newVal);
              setShortPosPage(0);
            }}
            resizeHandle={createTradeResizeHandle}
          />
        </Box>

        <TaskTrendPositionsTable
          title={t('tables.trend.longPositions')}
          count={longPositions.length}
          positions={sortedLongPositions}
          paginatedPositions={paginatedLongPositions}
          selectedPosId={selectedPosId}
          selectedIds={selectedLongPosIds}
          isAllPageSelected={isAllLongPosPageSelected}
          isRefreshing={isRefreshing}
          showOpenOnly={showOpenLongOnly}
          orderBy={longPosOrderBy}
          order={longPosOrder}
          colWidths={longPosColWidths}
          currentPrice={currentPrice}
          pipSize={pipSize}
          isShort={false}
          page={longPosPage}
          rowsPerPage={longPosRowsPerPage}
          timezone={timezone}
          selectedPosRowRef={selectedPosRowRef}
          onConfigureColumns={() => setLongPosConfigOpen(true)}
          onCopySelected={() => copySelectedLongPositions(false)}
          onSelectAllOnPage={selectAllLongPosOnPage}
          onResetSelection={resetLongPosSelection}
          onReload={fetchReplayData}
          onToggleOpenOnly={toggleOpenLongOnly}
          onTogglePageSelection={toggleLongPosPageSelection}
          onSort={handleLongPosSort}
          onSelectPosition={onPosRowSelect}
          onToggleSelection={toggleLongPosSelection}
          onPageChange={(_e, newPage) => setLongPosPage(newPage)}
          onRowsPerPageChange={(e) => {
            const newVal = parseInt(e.target.value, 10);
            setLongPosRowsPerPage(newVal);
            setLongPosPage(0);
            setTradeRowsPerPage(newVal);
            setTradePage(0);
            setShortPosRowsPerPage(newVal);
            setShortPosPage(0);
          }}
          resizeHandle={createLongPosResizeHandle}
        />

        <TaskTrendPositionsTable
          title={t('tables.trend.shortPositions')}
          count={shortPositions.length}
          positions={sortedShortPositions}
          paginatedPositions={paginatedShortPositions}
          selectedPosId={selectedPosId}
          selectedIds={selectedShortPosIds}
          isAllPageSelected={isAllShortPosPageSelected}
          isRefreshing={isRefreshing}
          showOpenOnly={showOpenShortOnly}
          orderBy={shortPosOrderBy}
          order={shortPosOrder}
          colWidths={shortPosColWidths}
          currentPrice={currentPrice}
          pipSize={pipSize}
          isShort={true}
          page={shortPosPage}
          rowsPerPage={shortPosRowsPerPage}
          timezone={timezone}
          selectedPosRowRef={selectedPosRowRef}
          onConfigureColumns={() => setShortPosConfigOpen(true)}
          onCopySelected={() => copySelectedShortPositions(true)}
          onSelectAllOnPage={selectAllShortPosOnPage}
          onResetSelection={resetShortPosSelection}
          onReload={fetchReplayData}
          onToggleOpenOnly={toggleOpenShortOnly}
          onTogglePageSelection={toggleShortPosPageSelection}
          onSort={handleShortPosSort}
          onSelectPosition={onPosRowSelect}
          onToggleSelection={toggleShortPosSelection}
          onPageChange={(_e, newPage) => setShortPosPage(newPage)}
          onRowsPerPageChange={(e) => {
            const newVal = parseInt(e.target.value, 10);
            setShortPosRowsPerPage(newVal);
            setShortPosPage(0);
            setTradeRowsPerPage(newVal);
            setTradePage(0);
            setLongPosRowsPerPage(newVal);
            setLongPosPage(0);
          }}
          resizeHandle={createShortPosResizeHandle}
        />
      </Box>

      <ColumnConfigDialog
        open={tradeConfigOpen}
        columns={tradeColumnConfig}
        onClose={() => setTradeConfigOpen(false)}
        onSave={updateTradeColumns}
        onReset={resetTradeDefaults}
      />
      <ColumnConfigDialog
        open={longPosConfigOpen}
        columns={longPosColumnConfig}
        onClose={() => setLongPosConfigOpen(false)}
        onSave={updateLongPosColumns}
        onReset={resetLongPosDefaults}
      />
      <ColumnConfigDialog
        open={shortPosConfigOpen}
        columns={shortPosColumnConfig}
        onClose={() => setShortPosConfigOpen(false)}
        onSave={updateShortPosColumns}
        onReset={resetShortPosDefaults}
      />
    </Box>
  );
};

export default TaskTrendPanel;
