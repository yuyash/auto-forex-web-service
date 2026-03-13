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
import {
  CandlestickSeries,
  createChart,
  createSeriesMarkers,
  type IChartApi,
  type ISeriesApi,
  type ISeriesMarkersPluginApi,
  type Time,
  type UTCTimestamp,
} from 'lightweight-charts';
import {
  fetchAllTrades,
  fetchTradesSince,
} from '../../../utils/fetchAllTrades';
import { useSupportedGranularities } from '../../../hooks/useMarketConfig';
import {
  useTaskPositions,
  type TaskPosition,
} from '../../../hooks/useTaskPositions';
import { useTaskSummary } from '../../../hooks/useTaskSummary';
import { TaskType } from '../../../types/common';
import { detectMarketGaps } from '../../../utils/marketClosedMarkers';
import { MarketClosedHighlight } from '../../../utils/MarketClosedHighlight';
import {
  AdaptiveTimeScale,
  createSuppressedTickMarkFormatter,
  createTooltipTimeFormatter,
} from '../../../utils/adaptiveTimeScalePlugin';
import { getTimezoneAbbr } from '../../../utils/chartTimezone';
import { useAuth } from '../../../contexts/AuthContext';
import { SequencePositionLine } from '../../../utils/SequencePositionLine';
import { getCandleColors } from '../../../utils/candleColors';
import { useMetricsOverlay } from './MetricsOverlayChart';
import { ColumnConfigDialog } from '../../common/ColumnConfigDialog';
import {
  useColumnConfig,
  type ColumnItem,
} from '../../../hooks/useColumnConfig';
import { useWindowedCandles } from '../../../hooks/useWindowedCandles';
import {
  useWindowedTaskMarkers,
  type WindowedTradeMarker,
} from '../../../hooks/useWindowedTaskMarkers';
import { clampRange, type TimeRange } from '../../../utils/windowedRanges';
import {
  ALLOWED_GRANULARITIES,
  ALLOWED_VALUES,
  DEFAULT_LS_POSITION_WIDTHS,
  DEFAULT_REPLAY_WIDTHS,
  GRANULARITY_MINUTES,
  LOT_UNITS,
  POLLING_INTERVAL_OPTIONS,
  computePosPips,
  computePosPnl,
  findFirstCandleAtOrAfter,
  findGapAroundTime,
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
import type {
  LSPosSortableKey,
  SortableKey,
  TrendPosition,
} from './taskTrendPanel/shared';

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
  pipSize,
}) => {
  const panelRootRef = useRef<HTMLDivElement | null>(null);
  const chartContainerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<'Candlestick', Time> | null>(null);
  const markersRef = useRef<ISeriesMarkersPluginApi<Time> | null>(null);
  const highlightRef = useRef<MarketClosedHighlight | null>(null);
  const adaptiveRef = useRef<AdaptiveTimeScale | null>(null);
  const sequenceLineRef = useRef<SequencePositionLine | null>(null);
  const tradesRef = useRef<ReplayTrade[]>([]);
  const { user } = useAuth();
  const { t } = useTranslation('common');
  const muiTheme = useTheme();
  const isDark = muiTheme.palette.mode === 'dark';
  const timezone = user?.timezone || 'UTC';
  const [granularity, setGranularity] = useState<string>('M1');
  const [trades, setTrades] = useState<ReplayTrade[]>([]);
  const [selectedTradeId, setSelectedTradeId] = useState<string | null>(null);
  // State-based chart reference so hooks can react to chart creation
  const [chartInstance, setChartInstance] = useState<IChartApi | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [pollingIntervalMs, setPollingIntervalMs] = useState(10_000);
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
    initialCount: 800,
    edgeCount: 800,
    autoRefresh: enableRealTimeUpdates,
    refreshIntervalSeconds: Math.max(10, Math.floor(pollingIntervalMs / 1000)),
  });
  const startTimeSec = useMemo(() => isoToSec(startTime), [startTime]);
  const endTimeSec = useMemo(() => isoToSec(endTime), [endTime]);
  const currentTickSec = useMemo(
    () => isoToSec(currentTick?.timestamp ?? null),
    [currentTick?.timestamp]
  );
  const liveRangeUpperBound = useMemo(() => {
    if (!enableRealTimeUpdates) {
      return endTimeSec ?? undefined;
    }
    if (taskType === TaskType.BACKTEST) {
      return endTimeSec ?? currentTickSec ?? undefined;
    }
    return currentTickSec ?? undefined;
  }, [currentTickSec, enableRealTimeUpdates, endTimeSec, taskType]);
  const taskDataBounds = useMemo<Partial<TimeRange> | null>(() => {
    const from = startTimeSec ?? undefined;
    const to = liveRangeUpperBound;
    if (from == null && to == null) {
      return null;
    }
    return { from, to };
  }, [liveRangeUpperBound, startTimeSec]);
  const markerDisplayCutoffSec = useMemo(() => {
    if (!enableRealTimeUpdates) {
      return null;
    }
    return currentTickSec;
  }, [currentTickSec, enableRealTimeUpdates]);
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

  // Fetch open/closed positions via useTaskPositions so that
  // Realized PnL and Unrealized PnL are computed from the positions table.
  const { positions: pnlClosedPositions } = useTaskPositions({
    taskId,
    taskType,
    executionRunId,
    status: 'closed',
    pageSize: 5000,
    enableRealTimeUpdates,
  });
  const { positions: pnlOpenPositions } = useTaskPositions({
    taskId,
    taskType,
    executionRunId,
    status: 'open',
    pageSize: 5000,
    enableRealTimeUpdates,
  });
  const {
    taskEvents: taskLifecycleEvents,
    strategyEvents,
    trades: windowedTradeMarkers,
    ensureRange: ensureMarkerRange,
  } = useWindowedTaskMarkers({
    taskId: String(taskId),
    taskType,
    executionRunId,
    enableRealTimeUpdates,
    bounds: taskDataBounds,
  });

  // Auto-follow: track whether the chart should auto-scroll to the position line
  const [autoFollow, setAutoFollow] = useState(true);
  // Counter-based guard: every programmatic scroll increments this counter.
  // The visibleLogicalRangeChange listener decrements it instead of disabling
  // auto-follow.  This is more reliable than a time-based window because the
  // chart library can fire the change callback with unpredictable async delays
  // (especially when the browser tab is throttled or the machine is under load).
  const programmaticScrollCountRef = useRef(0);
  // Timestamp-based guard kept as a secondary safety net for callbacks that
  // fire multiple times per single programmatic action (e.g. setData triggers
  // both a range reset and a fitContent, each producing a callback).
  const programmaticScrollUntilRef = useRef(0);
  const PROGRAMMATIC_SCROLL_GUARD_MS = 800;
  // Keep the old ref name around as a thin wrapper so every call-site still
  // compiles – but now it sets both the counter and the timestamp.
  // Wrapped in useMemo so the object identity is stable across renders,
  // which satisfies the react-hooks/exhaustive-deps rule.
  const programmaticScrollRef = useMemo(
    () => ({
      get current() {
        return (
          programmaticScrollCountRef.current > 0 ||
          Date.now() < programmaticScrollUntilRef.current
        );
      },
      set current(v: boolean) {
        if (v) {
          programmaticScrollCountRef.current += 1;
          programmaticScrollUntilRef.current =
            Date.now() + PROGRAMMATIC_SCROLL_GUARD_MS;
        } else {
          programmaticScrollCountRef.current = 0;
          programmaticScrollUntilRef.current = 0;
        }
      },
      /** Decrement the counter by one (called from the range-change listener). */
      consume() {
        if (programmaticScrollCountRef.current > 0) {
          programmaticScrollCountRef.current -= 1;
          return true;
        }
        if (Date.now() < programmaticScrollUntilRef.current) {
          return true;
        }
        return false;
      },
    }),
    [PROGRAMMATIC_SCROLL_GUARD_MS]
  );

  // Re-enable auto-follow when real-time updates are turned on (task started)
  useEffect(() => {
    if (enableRealTimeUpdates) {
      setAutoFollow(true);
    }
  }, [enableRealTimeUpdates]);

  const [orderBy, setOrderBy] = useState<SortableKey>('timestamp');
  const [order, setOrder] = useState<'asc' | 'desc'>('desc');
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(10);

  // Row selection for copy
  const [selectedRowIds, setSelectedRowIds] = useState<Set<string>>(new Set());

  // Track whether the selection came from a chart click (to auto-navigate table)
  const chartClickedRef = useRef(false);
  const selectedRowRef = useRef<HTMLTableRowElement | null>(null);

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

  // Column resize state
  const [replayColWidths, setReplayColWidths] = useState(DEFAULT_REPLAY_WIDTHS);
  const replayResizeRef = useRef<{
    col: string;
    startX: number;
    startW: number;
  } | null>(null);

  // ── Column visibility config for the 3 trend tables ──
  const tradesColDefaults: ColumnItem[] = [
    { id: 'timestamp', label: t('tables.trend.time'), visible: true },
    { id: 'direction', label: t('tables.trend.direction'), visible: true },
    { id: 'layer_index', label: t('tables.trend.layer'), visible: true },
    { id: 'retracement_count', label: t('tables.trend.ret'), visible: true },
    { id: 'units', label: t('tables.trend.units'), visible: true },
    { id: 'price', label: t('tables.trend.price'), visible: true },
    { id: 'execution_method', label: t('tables.trend.event'), visible: true },
  ];
  const {
    columns: tradesColConfig,
    updateColumns: updateTradesCols,
    resetToDefaults: resetTradesCols,
  } = useColumnConfig('trend_trades', tradesColDefaults);
  const [tradesColConfigOpen, setTradesColConfigOpen] = useState(false);

  const posColDefaults: ColumnItem[] = [
    { id: 'entry_time', label: t('tables.trend.openTime'), visible: true },
    { id: 'exit_time', label: t('tables.trend.closeTime'), visible: true },
    { id: '_status', label: t('tables.trend.status'), visible: true },
    { id: 'layer_index', label: t('tables.trend.layer'), visible: true },
    {
      id: 'retracement_count',
      label: t('tables.trend.retrace'),
      visible: true,
    },
    { id: 'units', label: t('tables.trend.units'), visible: true },
    { id: 'entry_price', label: t('tables.trend.entry'), visible: true },
    { id: 'exit_price', label: t('tables.trend.exit'), visible: true },
    { id: '_pips', label: t('tables.trend.pips'), visible: true },
    { id: '_pnl', label: t('tables.trend.pnl'), visible: true },
  ];
  const {
    columns: longPosColConfig,
    updateColumns: updateLongPosCols,
    resetToDefaults: resetLongPosCols,
  } = useColumnConfig('trend_long_positions', posColDefaults);
  const [longPosColConfigOpen, setLongPosColConfigOpen] = useState(false);

  const {
    columns: shortPosColConfig,
    updateColumns: updateShortPosCols,
    resetToDefaults: resetShortPosCols,
  } = useColumnConfig('trend_short_positions', posColDefaults);
  const [shortPosColConfigOpen, setShortPosColConfigOpen] = useState(false);

  const handleColResizeStart = useCallback(
    (e: React.MouseEvent | React.TouchEvent, col: string) => {
      e.preventDefault();
      e.stopPropagation();
      const clientX = 'touches' in e ? e.touches[0].clientX : e.clientX;
      replayResizeRef.current = {
        col,
        startX: clientX,
        startW: replayColWidths[col] ?? 100,
      };
      const onMove = (ev: MouseEvent | TouchEvent) => {
        if (!replayResizeRef.current) return;
        const moveX =
          'touches' in ev ? ev.touches[0].clientX : (ev as MouseEvent).clientX;
        const diff = moveX - replayResizeRef.current.startX;
        const w = Math.max(40, replayResizeRef.current.startW + diff);
        setReplayColWidths((prev) => ({
          ...prev,
          [replayResizeRef.current!.col]: w,
        }));
      };
      const onUp = () => {
        replayResizeRef.current = null;
        document.removeEventListener('mousemove', onMove);
        document.removeEventListener('mouseup', onUp);
        document.removeEventListener('touchmove', onMove);
        document.removeEventListener('touchend', onUp);
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
      };
      document.body.style.cursor = 'col-resize';
      document.body.style.userSelect = 'none';
      document.addEventListener('mousemove', onMove);
      document.addEventListener('mouseup', onUp);
      document.addEventListener('touchmove', onMove, { passive: false });
      document.addEventListener('touchend', onUp);
    },
    [replayColWidths]
  );

  const resizeHandle = useCallback(
    (col: string) => (
      <Box
        onMouseDown={(e) => handleColResizeStart(e, col)}
        onTouchStart={(e) => handleColResizeStart(e, col)}
        sx={{
          position: 'absolute',
          right: 0,
          top: 0,
          bottom: 0,
          width: 4,
          cursor: 'col-resize',
          '&:hover': { backgroundColor: 'primary.main', opacity: 0.4 },
        }}
      />
    ),
    [handleColResizeStart]
  );

  // ── Long/Short position column resize ──
  const [longPosColWidths, setLongPosColWidths] = useState(
    DEFAULT_LS_POSITION_WIDTHS
  );
  const [shortPosColWidths, setShortPosColWidths] = useState(
    DEFAULT_LS_POSITION_WIDTHS
  );
  const lsPosResizeRef = useRef<{
    col: string;
    startX: number;
    startW: number;
    setter: React.Dispatch<React.SetStateAction<Record<string, number>>>;
  } | null>(null);

  const handleLSPosColResizeStart = useCallback(
    (
      e: React.MouseEvent | React.TouchEvent,
      col: string,
      widths: Record<string, number>,
      setter: React.Dispatch<React.SetStateAction<Record<string, number>>>
    ) => {
      e.preventDefault();
      e.stopPropagation();
      const clientX = 'touches' in e ? e.touches[0].clientX : e.clientX;
      lsPosResizeRef.current = {
        col,
        startX: clientX,
        startW: widths[col] ?? 100,
        setter,
      };
      const onMove = (ev: MouseEvent | TouchEvent) => {
        if (!lsPosResizeRef.current) return;
        const moveX =
          'touches' in ev ? ev.touches[0].clientX : (ev as MouseEvent).clientX;
        const diff = moveX - lsPosResizeRef.current.startX;
        const w = Math.max(40, lsPosResizeRef.current.startW + diff);
        lsPosResizeRef.current.setter((prev) => ({
          ...prev,
          [lsPosResizeRef.current!.col]: w,
        }));
      };
      const onUp = () => {
        lsPosResizeRef.current = null;
        document.removeEventListener('mousemove', onMove);
        document.removeEventListener('mouseup', onUp);
        document.removeEventListener('touchmove', onMove);
        document.removeEventListener('touchend', onUp);
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
      };
      document.body.style.cursor = 'col-resize';
      document.body.style.userSelect = 'none';
      document.addEventListener('mousemove', onMove);
      document.addEventListener('mouseup', onUp);
      document.addEventListener('touchmove', onMove, { passive: false });
      document.addEventListener('touchend', onUp);
    },
    []
  );

  const makeLSResizeHandle = useCallback(
    (
      col: string,
      widths: Record<string, number>,
      setter: React.Dispatch<React.SetStateAction<Record<string, number>>>
    ) => (
      <Box
        onMouseDown={(e) => handleLSPosColResizeStart(e, col, widths, setter)}
        onTouchStart={(e) => handleLSPosColResizeStart(e, col, widths, setter)}
        sx={{
          position: 'absolute',
          right: 0,
          top: 0,
          bottom: 0,
          width: 4,
          cursor: 'col-resize',
          '&:hover': { backgroundColor: 'primary.main', opacity: 0.4 },
        }}
      />
    ),
    [handleLSPosColResizeStart]
  );

  const handleSort = (column: SortableKey) => {
    if (orderBy === column) {
      setOrder((prev) => (prev === 'asc' ? 'desc' : 'asc'));
    } else {
      setOrderBy(column);
      setOrder('asc');
    }
  };

  const sortedTrades = useMemo(() => {
    const sorted = [...trades].sort((a, b) => {
      let cmp = 0;
      switch (orderBy) {
        case 'timestamp':
          cmp =
            new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime();
          break;
        case 'direction':
          cmp = a.direction.localeCompare(b.direction);
          break;
        case 'layer_index':
          cmp = (a.layer_index ?? -1) - (b.layer_index ?? -1);
          break;
        case 'retracement_count':
          cmp = (a.retracement_count ?? -1) - (b.retracement_count ?? -1);
          break;
        case 'units':
          cmp = Number(a.units) - Number(b.units);
          break;
        case 'price':
          cmp = Number(a.price) - Number(b.price);
          break;
        case 'execution_method':
          cmp = (a.execution_method || '').localeCompare(
            b.execution_method || ''
          );
          break;
      }
      return order === 'asc' ? cmp : -cmp;
    });
    return sorted;
  }, [trades, orderBy, order]);

  const paginatedTrades = useMemo(
    () =>
      sortedTrades.slice(page * rowsPerPage, page * rowsPerPage + rowsPerPage),
    [sortedTrades, page, rowsPerPage]
  );

  // Row selection helpers
  const isAllPageSelected =
    paginatedTrades.length > 0 &&
    paginatedTrades.every((r) => selectedRowIds.has(r.id));

  const toggleRowSelection = useCallback((id: string) => {
    setSelectedRowIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const selectAllOnPage = useCallback(() => {
    setSelectedRowIds((prev) => {
      const next = new Set(prev);
      for (const row of paginatedTrades) next.add(row.id);
      return next;
    });
  }, [paginatedTrades]);

  const resetSelection = useCallback(() => {
    setSelectedRowIds(new Set());
  }, []);

  const copySelectedRows = useCallback(() => {
    // Build headers and row data respecting column config order and visibility
    const extractors: Record<string, (r: (typeof sortedTrades)[0]) => string> =
      {
        timestamp: (r) => new Date(r.timestamp).toLocaleString(),
        direction: (r) => (r.direction ? r.direction.toUpperCase() : ''),
        layer_index: (r) => String(r.layer_index ?? '-'),
        retracement_count: (r) => String(r.retracement_count ?? '-'),
        units: (r) => String(r.units),
        price: (r) => (r.price ? `¥${parseFloat(r.price).toFixed(3)}` : '-'),
        execution_method: (r) =>
          r.execution_method_display || r.execution_method || '-',
      };
    const visibleCols = tradesColConfig.filter((c) => c.visible);
    const applicableCols = visibleCols.filter((c) => extractors[c.id] != null);
    const header = applicableCols.map((c) => c.label).join('\t');
    const rows = sortedTrades
      .filter((r) => selectedRowIds.has(r.id))
      .map((r) =>
        applicableCols
          .map((c) => {
            const ext = extractors[c.id];
            return ext ? ext(r) : '-';
          })
          .join('\t')
      );
    navigator.clipboard.writeText([header, ...rows].join('\n'));
  }, [selectedRowIds, sortedTrades, tradesColConfig]);

  // Reset to first page when sort changes (not on data refresh)
  useEffect(() => {
    setPage(0);
  }, [orderBy, order]);

  const currentPrice =
    currentTick?.price != null ? parseFloat(currentTick.price) : null;

  // Merge open + closed positions for the Positions panel in the Trend tab
  // Merge open + closed positions, de-duplicate by id, and derive _status
  // from the actual `is_open` field rather than which query returned it.
  // This prevents a position that was just closed from appearing as "open"
  // when the open-positions poll returns stale data while the closed-
  // positions poll already includes the updated record.
  const allPositions = useMemo<TrendPosition[]>(() => {
    const map = new Map<string, TaskPosition>();
    // Insert closed first, then open – but if the same id appears in both
    // lists the closed version (is_open=false) wins because it is the more
    // up-to-date state.
    for (const p of pnlOpenPositions) {
      map.set(p.id, p);
    }
    for (const p of pnlClosedPositions) {
      map.set(p.id, p); // overwrites the open entry if duplicate
    }
    return Array.from(map.values())
      .map((p) => ({
        ...p,
        _status: (p.is_open ? 'open' : 'closed') as 'open' | 'closed',
      }))
      .sort(
        (a, b) =>
          new Date(b.entry_time).getTime() - new Date(a.entry_time).getTime()
      );
  }, [pnlOpenPositions, pnlClosedPositions]);

  // Filtered positions by direction for the split Long/Short tables
  const longPositions = useMemo(
    () => allPositions.filter((p) => p.direction === 'long'),
    [allPositions]
  );
  const shortPositions = useMemo(
    () => allPositions.filter((p) => p.direction === 'short'),
    [allPositions]
  );

  const [showOpenLongOnly, setShowOpenLongOnly] = useState(false);
  const [showOpenShortOnly, setShowOpenShortOnly] = useState(false);

  const [, setPosPage] = useState(0);
  const [, setPosRowsPerPage] = useState(10);

  // Separate pagination for Long / Short position tables in the Trend tab
  const [longPosPage, setLongPosPage] = useState(0);
  const [shortPosPage, setShortPosPage] = useState(0);
  const [longPosRowsPerPage, setLongPosRowsPerPage] = useState(10);
  const [shortPosRowsPerPage, setShortPosRowsPerPage] = useState(10);

  const [longPosOrderBy, setLongPosOrderBy] =
    useState<LSPosSortableKey>('entry_time');
  const [longPosOrder, setLongPosOrder] = useState<'asc' | 'desc'>('desc');
  const [shortPosOrderBy, setShortPosOrderBy] =
    useState<LSPosSortableKey>('entry_time');
  const [shortPosOrder, setShortPosOrder] = useState<'asc' | 'desc'>('desc');

  const handleLongPosSort = useCallback((column: LSPosSortableKey) => {
    setLongPosOrderBy((prev) => {
      if (prev === column) {
        setLongPosOrder((o) => (o === 'asc' ? 'desc' : 'asc'));
        return prev;
      }
      setLongPosOrder(
        column === 'entry_time' || column === 'exit_time' ? 'desc' : 'asc'
      );
      return column;
    });
    setLongPosPage(0);
  }, []);

  const handleShortPosSort = useCallback((column: LSPosSortableKey) => {
    setShortPosOrderBy((prev) => {
      if (prev === column) {
        setShortPosOrder((o) => (o === 'asc' ? 'desc' : 'asc'));
        return prev;
      }
      setShortPosOrder(
        column === 'entry_time' || column === 'exit_time' ? 'desc' : 'asc'
      );
      return column;
    });
    setShortPosPage(0);
  }, []);

  // Sorted & paginated long/short positions for the split tables
  const sortLSPositions = useCallback(
    (
      positions: (TaskPosition & { _status: 'open' | 'closed' })[],
      sortBy: LSPosSortableKey,
      sortOrder: 'asc' | 'desc'
    ) => {
      return [...positions].sort((a, b) => {
        let cmp = 0;
        switch (sortBy) {
          case 'entry_time':
            cmp =
              new Date(a.entry_time).getTime() -
              new Date(b.entry_time).getTime();
            break;
          case 'exit_time': {
            const aT = a.exit_time ? new Date(a.exit_time).getTime() : 0;
            const bT = b.exit_time ? new Date(b.exit_time).getTime() : 0;
            cmp = aT - bT;
            break;
          }
          case '_status':
            cmp = a._status.localeCompare(b._status);
            break;
          case 'layer_index':
            cmp = (a.layer_index ?? -1) - (b.layer_index ?? -1);
            break;
          case 'retracement_count':
            cmp = (a.retracement_count ?? -1) - (b.retracement_count ?? -1);
            break;
          case 'units':
            cmp = Math.abs(a.units ?? 0) - Math.abs(b.units ?? 0);
            break;
          case 'entry_price':
            cmp =
              parseFloat(a.entry_price || '0') -
              parseFloat(b.entry_price || '0');
            break;
          case 'exit_price':
            cmp =
              parseFloat(a.exit_price || '0') - parseFloat(b.exit_price || '0');
            break;
          case '_pips': {
            const pipsA = computePosPips(a, currentPrice, pipSize);
            const pipsB = computePosPips(b, currentPrice, pipSize);
            cmp = pipsA - pipsB;
            break;
          }
          case '_pnl': {
            const pnlA = computePosPnl(a, currentPrice);
            const pnlB = computePosPnl(b, currentPrice);
            cmp = pnlA - pnlB;
            break;
          }
        }
        return sortOrder === 'asc' ? cmp : -cmp;
      });
    },
    [currentPrice, pipSize]
  );

  const sortedLongPositions = useMemo(() => {
    const base = showOpenLongOnly
      ? longPositions.filter((p) => p._status === 'open')
      : longPositions;
    return sortLSPositions(base, longPosOrderBy, longPosOrder);
  }, [
    longPositions,
    showOpenLongOnly,
    longPosOrderBy,
    longPosOrder,
    sortLSPositions,
  ]);

  const sortedShortPositions = useMemo(() => {
    const base = showOpenShortOnly
      ? shortPositions.filter((p) => p._status === 'open')
      : shortPositions;
    return sortLSPositions(base, shortPosOrderBy, shortPosOrder);
  }, [
    shortPositions,
    showOpenShortOnly,
    shortPosOrderBy,
    shortPosOrder,
    sortLSPositions,
  ]);

  const paginatedLongPositions = useMemo(
    () =>
      sortedLongPositions.slice(
        longPosPage * longPosRowsPerPage,
        longPosPage * longPosRowsPerPage + longPosRowsPerPage
      ),
    [sortedLongPositions, longPosPage, longPosRowsPerPage]
  );
  const paginatedShortPositions = useMemo(
    () =>
      sortedShortPositions.slice(
        shortPosPage * shortPosRowsPerPage,
        shortPosPage * shortPosRowsPerPage + shortPosRowsPerPage
      ),
    [sortedShortPositions, shortPosPage, shortPosRowsPerPage]
  );

  // Single-position highlight (like selectedTradeId for trades)
  const [selectedPosId, setSelectedPosId] = useState<string | null>(null);
  // Set of trade IDs highlighted because of a position click
  const [highlightedTradeIds, setHighlightedTradeIds] = useState<Set<string>>(
    new Set()
  );
  const selectedPosRowRef = useRef<HTMLTableRowElement | null>(null);
  const pendingPosScrollRef = useRef(false);

  // ── Long position row selection ──
  const [selectedLongPosIds, setSelectedLongPosIds] = useState<Set<string>>(
    new Set()
  );

  const isAllLongPosPageSelected =
    paginatedLongPositions.length > 0 &&
    paginatedLongPositions.every((r) => selectedLongPosIds.has(r.id));

  const toggleLongPosSelection = useCallback((id: string) => {
    setSelectedLongPosIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const selectAllLongPosOnPage = useCallback(() => {
    setSelectedLongPosIds((prev) => {
      const next = new Set(prev);
      for (const row of paginatedLongPositions) next.add(row.id);
      return next;
    });
  }, [paginatedLongPositions]);

  const resetLongPosSelection = useCallback(() => {
    setSelectedLongPosIds(new Set());
  }, []);

  const copySelectedLongPositions = useCallback(() => {
    const extractors: Record<
      string,
      (pos: (typeof sortedLongPositions)[0]) => string
    > = {
      entry_time: (pos) =>
        pos.entry_time ? new Date(pos.entry_time).toLocaleString() : '-',
      exit_time: (pos) =>
        pos.exit_time ? new Date(pos.exit_time).toLocaleString() : '-',
      _status: (pos) => (pos._status === 'open' ? 'Open' : 'Closed'),
      layer_index: (pos) => String(pos.layer_index ?? '-'),
      retracement_count: (pos) => String(pos.retracement_count ?? '-'),
      units: (pos) => String(pos.units),
      entry_price: (pos) => {
        const ep = pos.entry_price ? parseFloat(pos.entry_price) : null;
        return ep != null ? `¥${ep.toFixed(3)}` : '-';
      },
      exit_price: (pos) => {
        const xp = pos.exit_price ? parseFloat(pos.exit_price) : null;
        return xp != null ? `¥${xp.toFixed(3)}` : '-';
      },
      _pips: (pos) => {
        const entryP = pos.entry_price ? parseFloat(pos.entry_price) : null;
        const exitP = pos.exit_price ? parseFloat(pos.exit_price) : null;
        const isOpen = pos._status === 'open';
        const hasPrice = isOpen
          ? currentPrice != null && entryP != null
          : exitP != null && entryP != null;
        return pipSize && hasPrice
          ? computePosPips(pos, currentPrice, pipSize).toFixed(1)
          : '-';
      },
      _pnl: (pos) => {
        const isOpen = pos._status === 'open';
        const entryP = pos.entry_price ? parseFloat(pos.entry_price) : null;
        const exitP = pos.exit_price ? parseFloat(pos.exit_price) : null;
        const units = Math.abs(pos.units ?? 0);
        let pnl: number | null = null;
        if (isOpen && currentPrice != null && entryP != null)
          pnl = (currentPrice - entryP) * units;
        else if (!isOpen && exitP != null && entryP != null)
          pnl = (exitP - entryP) * units;
        return pnl != null ? pnl.toFixed(2) : '-';
      },
    };
    const visibleCols = longPosColConfig.filter((c) => c.visible);
    const applicableCols = visibleCols.filter((c) => extractors[c.id] != null);
    const header = applicableCols.map((c) => c.label).join('\t');
    const rows = sortedLongPositions
      .filter((r) => selectedLongPosIds.has(r.id))
      .map((pos) =>
        applicableCols
          .map((c) => {
            const ext = extractors[c.id];
            return ext ? ext(pos) : '-';
          })
          .join('\t')
      );
    navigator.clipboard.writeText([header, ...rows].join('\n'));
  }, [
    selectedLongPosIds,
    sortedLongPositions,
    currentPrice,
    pipSize,
    longPosColConfig,
  ]);

  // ── Short position row selection ──
  const [selectedShortPosIds, setSelectedShortPosIds] = useState<Set<string>>(
    new Set()
  );

  const isAllShortPosPageSelected =
    paginatedShortPositions.length > 0 &&
    paginatedShortPositions.every((r) => selectedShortPosIds.has(r.id));

  const toggleShortPosSelection = useCallback((id: string) => {
    setSelectedShortPosIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const selectAllShortPosOnPage = useCallback(() => {
    setSelectedShortPosIds((prev) => {
      const next = new Set(prev);
      for (const row of paginatedShortPositions) next.add(row.id);
      return next;
    });
  }, [paginatedShortPositions]);

  const resetShortPosSelection = useCallback(() => {
    setSelectedShortPosIds(new Set());
  }, []);

  const copySelectedShortPositions = useCallback(() => {
    const extractors: Record<
      string,
      (pos: (typeof sortedShortPositions)[0]) => string
    > = {
      entry_time: (pos) =>
        pos.entry_time ? new Date(pos.entry_time).toLocaleString() : '-',
      exit_time: (pos) =>
        pos.exit_time ? new Date(pos.exit_time).toLocaleString() : '-',
      _status: (pos) => (pos._status === 'open' ? 'Open' : 'Closed'),
      layer_index: (pos) => String(pos.layer_index ?? '-'),
      retracement_count: (pos) => String(pos.retracement_count ?? '-'),
      units: (pos) => String(pos.units),
      entry_price: (pos) => {
        const ep = pos.entry_price ? parseFloat(pos.entry_price) : null;
        return ep != null ? `¥${ep.toFixed(3)}` : '-';
      },
      exit_price: (pos) => {
        const xp = pos.exit_price ? parseFloat(pos.exit_price) : null;
        return xp != null ? `¥${xp.toFixed(3)}` : '-';
      },
      _pips: (pos) => {
        const entryP = pos.entry_price ? parseFloat(pos.entry_price) : null;
        const exitP = pos.exit_price ? parseFloat(pos.exit_price) : null;
        const isOpen = pos._status === 'open';
        const hasPrice = isOpen
          ? currentPrice != null && entryP != null
          : exitP != null && entryP != null;
        return pipSize && hasPrice
          ? computePosPips(pos, currentPrice, pipSize).toFixed(1)
          : '-';
      },
      _pnl: (pos) => {
        const isOpen = pos._status === 'open';
        const entryP = pos.entry_price ? parseFloat(pos.entry_price) : null;
        const exitP = pos.exit_price ? parseFloat(pos.exit_price) : null;
        const units = Math.abs(pos.units ?? 0);
        let pnl: number | null = null;
        if (isOpen && currentPrice != null && entryP != null)
          pnl = (entryP - currentPrice) * units;
        else if (!isOpen && exitP != null && entryP != null)
          pnl = (entryP - exitP) * units;
        return pnl != null ? pnl.toFixed(2) : '-';
      },
    };
    const visibleCols = shortPosColConfig.filter((c) => c.visible);
    const applicableCols = visibleCols.filter((c) => extractors[c.id] != null);
    const header = applicableCols.map((c) => c.label).join('\t');
    const rows = sortedShortPositions
      .filter((r) => selectedShortPosIds.has(r.id))
      .map((pos) =>
        applicableCols
          .map((c) => {
            const ext = extractors[c.id];
            return ext ? ext(pos) : '-';
          })
          .join('\t')
      );
    navigator.clipboard.writeText([header, ...rows].join('\n'));
  }, [
    selectedShortPosIds,
    sortedShortPositions,
    currentPrice,
    pipSize,
    shortPosColConfig,
  ]);

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

  // When a chart marker is clicked, navigate the table to the page containing
  // the selected trade and scroll the row into view.
  const pendingScrollRef = useRef(false);

  /** Navigate the correct Long or Short position table to the page
   *  containing the given position, and schedule a scroll-into-view. */
  const navigateToPosition = useCallback(
    (pos: (typeof allPositions)[number]) => {
      setSelectedPosId(pos.id);
      pendingPosScrollRef.current = true;

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
      sortedLongPositions,
      sortedShortPositions,
      longPosRowsPerPage,
      shortPosRowsPerPage,
    ]
  );

  useEffect(() => {
    if (!chartClickedRef.current || !selectedTradeId) return;
    chartClickedRef.current = false;

    const idx = sortedTrades.findIndex((t) => t.id === selectedTradeId);
    if (idx === -1) return;

    const targetPage = Math.floor(idx / rowsPerPage);
    pendingScrollRef.current = true;
    setPage(targetPage);

    // Also highlight the related position
    const trade = trades.find((t) => t.id === selectedTradeId);
    if (trade) {
      const pos = findPositionForTrade(trade);
      if (pos) {
        navigateToPosition(pos);
      } else {
        setSelectedPosId(null);
      }
    }
    setHighlightedTradeIds(new Set());
  }, [
    selectedTradeId,
    sortedTrades,
    rowsPerPage,
    trades,
    findPositionForTrade,
    navigateToPosition,
  ]);

  // After the table re-renders with the selected row on the correct page,
  // scroll to it (only when triggered by a chart click).
  useEffect(() => {
    if (!pendingScrollRef.current) return;
    pendingScrollRef.current = false;
    const raf = requestAnimationFrame(() => {
      selectedRowRef.current?.scrollIntoView({
        behavior: 'smooth',
        block: 'center',
      });
    });
    return () => cancelAnimationFrame(raf);
  }, [page, selectedTradeId]);

  // Scroll the Positions table to the highlighted position row
  useEffect(() => {
    if (!pendingPosScrollRef.current) return;
    pendingPosScrollRef.current = false;
    const raf = requestAnimationFrame(() => {
      selectedPosRowRef.current?.scrollIntoView({
        behavior: 'smooth',
        block: 'center',
      });
    });
    return () => cancelAnimationFrame(raf);
  }, [longPosPage, shortPosPage, selectedPosId]);

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

  // Stores the visible time range before a granularity change so we can
  // restore it after new candles load, preventing the chart from jumping.
  const savedVisibleRangeRef = useRef<{ from: number; to: number } | null>(
    null
  );
  const pnlCurrency = instrument?.includes('_')
    ? instrument.split('_')[1]
    : 'N/A';

  // Stable reference for candle timestamps passed to useMetricsOverlay
  const candleTimestampsMemo = useMemo(
    () => candles.map((c) => Number(c.time)),
    [candles]
  );

  useEffect(() => {
    if (candleTimestampsMemo.length === 0) return;
    void ensureMarkerRange({
      from: candleTimestampsMemo[0],
      to: candleTimestampsMemo[candleTimestampsMemo.length - 1],
    });
  }, [candleTimestampsMemo, ensureMarkerRange]);

  // Attach metric overlay series (Margin Ratio, ATR, thresholds) to the
  // candlestick chart so they share the exact same X-axis.
  useMetricsOverlay({
    taskId: String(taskId),
    taskType,
    executionRunId,
    enableRealTimeUpdates,
    pollingIntervalMs,
    chart: chartInstance,
    candleTimestamps: candleTimestampsMemo,
    currentTickTimestamp: enableRealTimeUpdates ? currentTick?.timestamp : null,
    programmaticScrollRef,
  });

  // PnL summary from server-side aggregation (lightweight endpoint)
  const {
    summary: {
      pnl: { realized: serverRealizedPnl, unrealized: serverUnrealizedPnl },
      counts: {
        totalTrades: serverTotalTrades,
        openPositions: serverOpenPositionCount,
      },
    },
    refetch: refetchPnl,
  } = useTaskSummary(String(taskId), taskType, executionRunId);

  // Periodic PnL refresh while task is running
  useEffect(() => {
    if (!enableRealTimeUpdates) return;
    const interval = setInterval(refetchPnl, pollingIntervalMs);
    return () => clearInterval(interval);
  }, [enableRealTimeUpdates, refetchPnl, pollingIntervalMs]);

  const replaySummary = useMemo(() => {
    const totalTradesRaw =
      typeof latestExecution?.total_trades === 'number'
        ? latestExecution.total_trades
        : serverTotalTrades || trades.length;

    return {
      realizedPnl: Number.isFinite(serverRealizedPnl) ? serverRealizedPnl : 0,
      unrealizedPnl: Number.isFinite(serverUnrealizedPnl)
        ? serverUnrealizedPnl
        : 0,
      totalTrades: totalTradesRaw,
      openPositions: serverOpenPositionCount,
    };
  }, [
    serverRealizedPnl,
    serverUnrealizedPnl,
    serverTotalTrades,
    serverOpenPositionCount,
    latestExecution,
    trades.length,
  ]);

  useEffect(() => {
    setGranularity(recommendedGranularity);
  }, [recommendedGranularity, instrument, startTime, endTime]);

  const hasLoadedOnce = useRef(false);
  // Track the latest trade updated_at for incremental fetching.
  const tradeSinceRef = useRef<string | null>(null);
  // Track when candles were last fetched to throttle OANDA API calls during polling.
  // Candle data only changes at the latest bar, so refreshing every 60s is sufficient.
  const lastCandleFetchRef = useRef<number>(0);
  const CANDLE_REFRESH_INTERVAL_MS = 60_000;

  /** Map raw API trade objects to ReplayTrade rows. */
  const mapRawTrades = useCallback(
    (
      rawTrades: Array<Record<string, unknown>>,
      startSequence = 0
    ): ReplayTrade[] =>
      rawTrades
        .map((t: Record<string, unknown>, idx: number): ReplayTrade | null => {
          const timestamp = String(t.timestamp || '');
          const parsedTime = parseUtcTimestamp(timestamp);
          if (!timestamp || parsedTime === null) return null;
          const rawDir = t.direction;
          let mappedDirection: 'long' | 'short' | '';
          if (
            rawDir == null ||
            rawDir === '' ||
            String(rawDir).toLowerCase() === 'none'
          ) {
            mappedDirection = '';
          } else {
            const direction = String(rawDir).toLowerCase();
            mappedDirection =
              direction === 'buy'
                ? 'long'
                : direction === 'sell'
                  ? 'short'
                  : (direction as 'long' | 'short' | '');
          }
          return {
            id: t.id ? String(t.id) : `${timestamp}-${idx}`,
            sequence: startSequence + idx + 1,
            timestamp,
            timeSec: parsedTime,
            instrument: String(t.instrument || instrument),
            direction: mappedDirection,
            units: String(t.units ?? ''),
            price: String(t.price ?? ''),
            execution_method: String(t.execution_method || ''),
            execution_method_display: t.execution_method_display
              ? String(t.execution_method_display)
              : undefined,
            layer_index:
              t.layer_index === null || t.layer_index === undefined
                ? null
                : Number(t.layer_index),
            retracement_count:
              t.retracement_count === null || t.retracement_count === undefined
                ? null
                : Number(t.retracement_count),
            position_id:
              t.position_id === null || t.position_id === undefined
                ? null
                : String(t.position_id),
          };
        })
        .filter((v): v is ReplayTrade => v !== null),
    [instrument]
  );

  /** Extract the latest updated_at from raw trade records. */
  const getLatestTradeUpdatedAt = (
    rawTrades: Array<Record<string, unknown>>
  ): string | null => {
    let latest: string | null = null;
    for (const t of rawTrades) {
      const ua = t.updated_at as string | undefined;
      if (ua && (!latest || ua > latest)) latest = ua;
    }
    return latest;
  };

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

      // Fetch trades — errors here never hide already-loaded candles.
      try {
        const isIncrementalTrades =
          !isInitialLoad && tradeSinceRef.current !== null;

        const rawTrades = isIncrementalTrades
          ? await fetchTradesSince(
              String(taskId),
              taskType,
              tradeSinceRef.current!,
              executionRunId
            )
          : await fetchAllTrades(String(taskId), taskType, executionRunId);

        // Track latest updated_at for next incremental poll.
        const latestUa = getLatestTradeUpdatedAt(rawTrades);
        if (
          latestUa &&
          (!tradeSinceRef.current || latestUa > tradeSinceRef.current)
        ) {
          tradeSinceRef.current = latestUa;
        }

        if (isIncrementalTrades && rawTrades.length > 0) {
          // Merge new trades into existing array.
          const incoming = mapRawTrades(rawTrades);
          setTrades((prev) => {
            const map = new Map(prev.map((t) => [t.id, t]));
            for (const t of incoming) {
              map.set(t.id, t);
            }
            const merged = Array.from(map.values()).sort(
              (a, b) =>
                new Date(a.timestamp).getTime() -
                new Date(b.timestamp).getTime()
            );
            // Re-sequence after merge.
            merged.forEach((t, i) => {
              t.sequence = i + 1;
            });
            return merged;
          });
        } else if (!isIncrementalTrades) {
          // Full replace (initial load).
          const tradeRows = mapRawTrades(rawTrades).sort(
            (a, b) =>
              new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
          );
          tradeRows.forEach((t, i) => {
            t.sequence = i + 1;
          });

          setTrades((prev) => {
            if (
              prev.length === tradeRows.length &&
              prev.length > 0 &&
              prev[prev.length - 1].id === tradeRows[tradeRows.length - 1].id
            ) {
              return prev;
            }
            return tradeRows;
          });
        }
      } catch (tradeError) {
        console.warn('Failed to refresh trade data:', tradeError);
      }
    } catch (e) {
      console.warn('Failed to load replay data:', e);
    } finally {
      hasLoadedOnce.current = true;
      setIsRefreshing(false);
    }
  }, [taskType, taskId, executionRunId, mapRawTrades, refreshTailCandles]);

  useEffect(() => {
    fetchReplayData();
  }, [fetchReplayData]);

  useEffect(() => {
    if (!enableRealTimeUpdates) return undefined;
    const id = setInterval(fetchReplayData, pollingIntervalMs);
    return () => clearInterval(id);
  }, [enableRealTimeUpdates, fetchReplayData, pollingIntervalMs]);

  useEffect(() => {
    tradesRef.current = trades;
  }, [trades]);

  // Chart height is managed by flex layout + ResizeObserver

  // Derived boolean: true once we have candle data.  Used as a dependency
  // for the chart-creation effect so it only fires on the false→true
  // transition, not on every candle-count change.
  const hasCandles = candles.length > 0;
  const previousFirstCandleTimeRef = useRef<number | null>(null);

  const maybeFetchVisibleWindow = useCallback(async () => {
    const chart = chartRef.current;
    const series = seriesRef.current;
    if (!chart || !series) return;

    const visibleTimeRange = chart.timeScale().getVisibleRange();
    if (
      visibleTimeRange &&
      typeof visibleTimeRange.from === 'number' &&
      typeof visibleTimeRange.to === 'number'
    ) {
      const target = clampTaskRange({
        from: Number(visibleTimeRange.from),
        to: Number(visibleTimeRange.to),
      });
      if (target) {
        await Promise.all([
          ensureCandleRange(target),
          ensureMarkerRange(target),
        ]);
      }
    }

    const logicalRange = chart.timeScale().getVisibleLogicalRange();
    const data = series.data();
    if (!logicalRange || !data || data.length === 0) return;

    const EDGE_THRESHOLD = 5;
    const firstTime = Number(candles[0]?.time ?? 0);
    const lastTime = Number(candles[candles.length - 1]?.time ?? 0);
    const spanSeconds =
      visibleTimeRange &&
      typeof visibleTimeRange.from === 'number' &&
      typeof visibleTimeRange.to === 'number'
        ? Math.max(
            granularitySeconds,
            Number(visibleTimeRange.to) - Number(visibleTimeRange.from)
          )
        : Math.max(granularitySeconds, lastTime - firstTime);
    const lowerBound = taskDataBounds?.from;
    const upperBound = taskDataBounds?.to;

    if (
      logicalRange.from < EDGE_THRESHOLD &&
      (lowerBound == null || firstTime > lowerBound)
    ) {
      await ensureCandleRange({
        from: Math.max(
          lowerBound ?? firstTime - spanSeconds,
          firstTime - spanSeconds
        ),
        to: firstTime,
      });
      return;
    }

    if (
      logicalRange.to > data.length - EDGE_THRESHOLD &&
      (upperBound == null || lastTime < upperBound)
    ) {
      await ensureCandleRange({
        from: lastTime,
        to: Math.min(
          upperBound ?? lastTime + spanSeconds,
          lastTime + spanSeconds
        ),
      });
    }
  }, [
    candles,
    clampTaskRange,
    ensureCandleRange,
    ensureMarkerRange,
    granularitySeconds,
    taskDataBounds,
  ]);
  const maybeFetchVisibleWindowRef = useRef(maybeFetchVisibleWindow);

  useEffect(() => {
    maybeFetchVisibleWindowRef.current = maybeFetchVisibleWindow;
  }, [maybeFetchVisibleWindow]);

  useEffect(() => {
    if (isLoading || !hasCandles) return;
    if (!chartContainerRef.current || chartRef.current) return;

    const container = chartContainerRef.current;

    const dynamicHeight = chartHeight;
    const chart = createChart(container, {
      height: dynamicHeight,
      layout: {
        background: { color: isDark ? '#131722' : '#ffffff' },
        textColor: isDark ? '#ffffff' : '#334155',
      },
      grid: {
        vertLines: { visible: false },
        horzLines: { color: isDark ? '#2a2e39' : '#e2e8f0' },
      },
      handleScale: {
        axisPressedMouseMove: true,
        mouseWheel: true,
        pinch: true,
      },
      handleScroll: {
        mouseWheel: true,
        pressedMouseMove: true,
        vertTouchDrag: true,
        horzTouchDrag: true,
      },
      rightPriceScale: {
        borderColor: isDark ? '#2a2e39' : '#cbd5e1',
        minimumWidth: 80,
        scaleMargins: { top: 0.02, bottom: 0.45 },
      },
      leftPriceScale: {
        borderColor: isDark ? '#2a2e39' : '#cbd5e1',
        visible: true,
        minimumWidth: 80,
        ticksVisible: true,
      },
      timeScale: {
        borderColor: isDark ? '#2a2e39' : '#cbd5e1',
        timeVisible: true,
        secondsVisible: false,
        tickMarkFormatter: createSuppressedTickMarkFormatter(),
      },
      localization: {
        timeFormatter: createTooltipTimeFormatter({ timezone }),
      },
    });

    const { upColor, downColor } = getCandleColors();
    const series = chart.addSeries(CandlestickSeries, {
      upColor,
      downColor,
      wickUpColor: upColor,
      wickDownColor: downColor,
      borderUpColor: upColor,
      borderDownColor: downColor,
    });
    const markers = createSeriesMarkers(series, []);

    chartRef.current = chart;
    setChartInstance(chart);
    seriesRef.current = series;
    markersRef.current = markers;

    const highlight = new MarketClosedHighlight();
    series.attachPrimitive(highlight);
    highlightRef.current = highlight;

    const adaptive = new AdaptiveTimeScale(
      { timezone },
      isDark ? '#ffffff' : '#334155',
      isDark ? '#2a2e39' : '#e2e8f0'
    );
    series.attachPrimitive(adaptive);
    adaptiveRef.current = adaptive;

    const sequenceLine = new SequencePositionLine();
    series.attachPrimitive(sequenceLine);
    sequenceLineRef.current = sequenceLine;

    chart.subscribeClick((param) => {
      if (!param.time || tradesRef.current.length === 0) return;
      const t = Number(param.time);
      const nearest = tradesRef.current.reduce((prev, curr) => {
        const prevDiff = Math.abs(Number(prev.timeSec) - t);
        const currDiff = Math.abs(Number(curr.timeSec) - t);
        return currDiff < prevDiff ? curr : prev;
      }, tradesRef.current[0]);

      // Toggle off if the same trade is already selected
      setSelectedTradeId((prev) => {
        if (prev === nearest.id) {
          // Deselect — clear all cross-highlights
          setSelectedPosId(null);
          setHighlightedTradeIds(new Set());
          return null;
        }
        // Select — let the existing effect handle cross-highlighting
        chartClickedRef.current = true;
        return nearest.id;
      });
    });

    // Detect user-initiated scroll/zoom and disable auto-follow
    let viewportDebounce: ReturnType<typeof setTimeout> | null = null;
    const handleViewportChange = () => {
      if (programmaticScrollRef.consume()) return;
      setAutoFollow(false);
      if (viewportDebounce) clearTimeout(viewportDebounce);
      viewportDebounce = setTimeout(() => {
        void maybeFetchVisibleWindowRef.current();
      }, 250);
    };
    chart.timeScale().subscribeVisibleLogicalRangeChange(handleViewportChange);
    chart.timeScale().subscribeVisibleTimeRangeChange(handleViewportChange);

    const observer = new ResizeObserver(() => {
      const width = container.clientWidth;
      const height = container.clientHeight;
      programmaticScrollRef.current = true;
      if (width > 0) {
        chart.applyOptions({ width });
      }
      if (height > 0) {
        chart.applyOptions({ height });
      }
    });
    observer.observe(container);
    // Guard initial layout so it doesn't disable auto-follow
    programmaticScrollRef.current = true;
    chart.applyOptions({ width: container.clientWidth });

    return () => {
      observer.disconnect();
      if (viewportDebounce) clearTimeout(viewportDebounce);
      chart
        .timeScale()
        .unsubscribeVisibleLogicalRangeChange(handleViewportChange);
      chart.timeScale().unsubscribeVisibleTimeRangeChange(handleViewportChange);
      setChartInstance(null);
      chartRef.current = null;
      seriesRef.current = null;
      markersRef.current = null;
      highlightRef.current = null;
      adaptiveRef.current = null;
      sequenceLineRef.current = null;
      hasInitialFit.current = false;
      requestAnimationFrame(() => {
        try {
          chart.remove();
        } catch {
          /* chart already disposed */
        }
      });
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- chartHeight is read once for initial creation; ResizeObserver handles subsequent resizes.  We derive `hasCandles` (boolean) so the effect only re-runs on the false→true transition and never on candle-count changes that would needlessly destroy and recreate the chart.
  }, [isLoading, hasCandles, timezone, isDark]);

  // Track whether this is the first candle load (for initial fitContent)
  const hasInitialFit = useRef(false);

  // Auto-follow and initial viewport width, measured in candles.
  const AUTO_FOLLOW_CANDLES = 1000;

  // When a task is actively progressing, preload the candle/marker window
  // around the current tick so auto-follow can anchor to the real "now"
  // position instead of the initial start chunk.
  useEffect(() => {
    if (!enableRealTimeUpdates || currentTickSec == null) return;

    const isTrading = taskType === TaskType.TRADING;
    const leftCandles = isTrading
      ? AUTO_FOLLOW_CANDLES * 0.75
      : AUTO_FOLLOW_CANDLES / 2;
    const rightCandles = AUTO_FOLLOW_CANDLES - leftCandles;
    const target = clampTaskRange({
      from: currentTickSec - leftCandles * granularitySeconds,
      to: currentTickSec + rightCandles * granularitySeconds,
    });

    if (!target) return;

    void Promise.all([ensureCandleRange(target), ensureMarkerRange(target)]);
  }, [
    AUTO_FOLLOW_CANDLES,
    clampTaskRange,
    currentTickSec,
    enableRealTimeUpdates,
    ensureCandleRange,
    ensureMarkerRange,
    granularitySeconds,
    taskType,
  ]);

  // Keep small windows around task boundaries loaded so START/STOP markers
  // can still snap to actual candles even when the main viewport is focused
  // on the current progress position.
  useEffect(() => {
    const boundaryPaddingSeconds = Math.max(granularitySeconds * 8, 60 * 60);
    const requests: Promise<void>[] = [];

    if (startTimeSec != null) {
      const startRange = clampTaskRange({
        from: startTimeSec,
        to: startTimeSec + boundaryPaddingSeconds,
      });
      if (startRange) {
        requests.push(ensureCandleRange(startRange));
      }
    }

    if (endTimeSec != null) {
      const endRange = clampTaskRange({
        from: endTimeSec - boundaryPaddingSeconds,
        to: endTimeSec + boundaryPaddingSeconds,
      });
      if (endRange) {
        requests.push(ensureCandleRange(endRange));
      }
    }

    if (requests.length === 0) return;

    void Promise.all(requests);
  }, [
    clampTaskRange,
    endTimeSec,
    ensureCandleRange,
    granularitySeconds,
    startTimeSec,
  ]);

  // Update candle data, market gaps, and fit chart when data changes
  useEffect(() => {
    if (!seriesRef.current || !markersRef.current) return;

    // Guard setData so the resulting visible-range change doesn't disable auto-follow
    programmaticScrollRef.current = true;

    // Save the current visible range before setData.  lightweight-charts
    // resets the scroll position to the last bar on setData, which would
    // cause the chart to jump when data is refreshed while the user has
    // scrolled to a different position.
    const savedLogicalRange = hasInitialFit.current
      ? chartRef.current?.timeScale().getVisibleLogicalRange()
      : null;

    try {
      seriesRef.current.setData(candles);
    } catch (e) {
      console.warn('Failed to set candle data:', e);
      return;
    }

    const times = candles.map((c) => Number(c.time));

    if (highlightRef.current) {
      highlightRef.current.setGaps(
        detectMarketGaps(times, granularity, candleDataRanges, timezone)
      );
    }

    // Only fit content on the very first load — preserve user's zoom/pan on updates
    if (candles.length > 0 && !hasInitialFit.current) {
      programmaticScrollRef.current = true;

      // Determine the initial viewport:
      // 1. If a sequence position line exists (currentTick), centre on it
      // 2. Otherwise, show the start of the data (left edge)
      const tickTs = currentTick?.timestamp
        ? Math.floor(new Date(currentTick.timestamp).getTime() / 1000)
        : null;

      if (
        enableRealTimeUpdates &&
        tickTs &&
        Number.isFinite(tickTs) &&
        seriesRef.current
      ) {
        // Centre on the current tick position
        const data = seriesRef.current.data();
        let logicalCenter = 0;
        if (data.length > 0) {
          let lo = 0;
          let hi = data.length - 1;
          while (lo < hi) {
            const mid = (lo + hi) >>> 1;
            const midSec =
              typeof data[mid].time === 'number'
                ? (data[mid].time as number)
                : new Date(data[mid].time as string).getTime() / 1000;
            if (midSec < tickTs) lo = mid + 1;
            else hi = mid;
          }
          logicalCenter = lo;
        }
        const half = AUTO_FOLLOW_CANDLES / 2;
        try {
          chartRef.current?.timeScale().setVisibleLogicalRange({
            from: logicalCenter - half,
            to: logicalCenter + half,
          });
        } catch (e) {
          console.warn('Failed to set initial visible range on tick:', e);
        }
      } else if (!enableRealTimeUpdates && startTimeSec != null) {
        const totalSpanSeconds = AUTO_FOLLOW_CANDLES * granularitySeconds;
        const gapAroundStart = findGapAroundTime(
          startTimeSec,
          times,
          granularitySeconds * 6
        );
        const initialFrom = gapAroundStart
          ? Math.max(startTimeSec, gapAroundStart.from)
          : startTimeSec;
        const requiredGapSpan = gapAroundStart
          ? gapAroundStart.to - initialFrom
          : 0;
        const initialSpanSeconds = Math.max(totalSpanSeconds, requiredGapSpan);
        try {
          chartRef.current?.timeScale().setVisibleRange({
            from: initialFrom as Time,
            to: (initialFrom + initialSpanSeconds) as Time,
          });
        } catch (e) {
          console.warn('Failed to set initial visible range at task start:', e);
        }
      } else {
        // No tick — show the start of the data
        try {
          chartRef.current?.timeScale().setVisibleLogicalRange({
            from: 0,
            to: AUTO_FOLLOW_CANDLES,
          });
        } catch (e) {
          console.warn('Failed to set initial visible range at start:', e);
        }
      }

      hasInitialFit.current = true;
    } else if (savedLogicalRange) {
      // Restore the visible range so the chart doesn't jump on data refresh.
      programmaticScrollRef.current = true;
      try {
        const previousFirst = previousFirstCandleTimeRef.current;
        const currentFirst =
          candles.length > 0 ? Number(candles[0].time) : null;
        const prependCount =
          previousFirst != null &&
          currentFirst != null &&
          currentFirst < previousFirst
            ? candles.filter((c) => Number(c.time) < previousFirst).length
            : 0;
        chartRef.current?.timeScale().setVisibleLogicalRange({
          from: savedLogicalRange.from + prependCount,
          to: savedLogicalRange.to + prependCount,
        });
      } catch (e) {
        console.warn('Failed to restore visible range after setData:', e);
      }
    }

    // After a granularity change, restore the previously visible time range
    // so the chart doesn't jump to the latest candles.
    if (savedVisibleRangeRef.current && chartRef.current) {
      const { from, to } = savedVisibleRangeRef.current;
      savedVisibleRangeRef.current = null;
      programmaticScrollRef.current = true;
      try {
        chartRef.current.timeScale().setVisibleRange({
          from: from as import('lightweight-charts').Time,
          to: to as import('lightweight-charts').Time,
        });
      } catch (e) {
        console.warn(
          'Failed to restore visible range after granularity change:',
          e
        );
      }
    }
    previousFirstCandleTimeRef.current =
      candles.length > 0 ? Number(candles[0].time) : null;
    // currentTick is intentionally excluded: it is only read on the very first
    // load (guarded by hasInitialFit) to decide the initial viewport position.
    // Including it would re-run setData on every tick update.
  }, [
    candles,
    granularity,
    candleDataRanges,
    enableRealTimeUpdates,
    startTimeSec,
    granularitySeconds,
    currentTick?.timestamp,
    timezone,
    programmaticScrollRef,
  ]);

  // Update sequence position line when current tick changes
  useEffect(() => {
    if (!sequenceLineRef.current) return;
    if (!currentTick?.timestamp) {
      sequenceLineRef.current.clear();
      return;
    }
    const price =
      currentTick.price != null ? parseFloat(currentTick.price) : null;
    sequenceLineRef.current.setPosition(currentTick.timestamp, price);

    // Auto-scroll: keep the sequence line at the horizontal centre of the
    // viewport (backtest) or at the 3/4 position from the left (trading),
    // since trading has no future candles to display on the right.
    // We use logical-index based positioning so that market gaps
    // don't shift the line away from the visual centre.
    if (autoFollow && enableRealTimeUpdates) {
      const ts = chartRef.current?.timeScale();
      const series = seriesRef.current;
      if (ts && series) {
        const centerSec = Math.floor(
          new Date(currentTick.timestamp).getTime() / 1000
        );
        if (Number.isFinite(centerSec)) {
          // Find the logical index of the candle closest to the current tick
          const data = series.data();
          let logicalCenter = data.length - 1; // default: latest candle
          if (data.length > 0) {
            // Binary search for the nearest candle
            let lo = 0;
            let hi = data.length - 1;
            while (lo < hi) {
              const mid = (lo + hi) >>> 1;
              const midSec =
                typeof data[mid].time === 'number'
                  ? (data[mid].time as number)
                  : new Date(data[mid].time as string).getTime() / 1000;
              if (midSec < centerSec) {
                lo = mid + 1;
              } else {
                hi = mid;
              }
            }
            logicalCenter = lo;
          }

          // For trading tasks, place the position line at 3/4 from the left
          // so the right side (no future data) is minimal.
          // For backtest tasks, keep it centred.
          const isTrading = taskType === TaskType.TRADING;
          const leftCandles = isTrading
            ? AUTO_FOLLOW_CANDLES * 0.75
            : AUTO_FOLLOW_CANDLES / 2;
          const rightCandles = AUTO_FOLLOW_CANDLES - leftCandles;

          programmaticScrollRef.current = true;
          try {
            ts.setVisibleLogicalRange({
              from: logicalCenter - leftCandles,
              to: logicalCenter + rightCandles,
            });
          } catch (e) {
            console.warn('Failed to set visible range during auto-follow:', e);
          }
        }
      }
    }
    // Re-run when candles load so the ref is available after chart creation
  }, [
    currentTick?.timestamp,
    currentTick?.price,
    enableRealTimeUpdates,
    candles.length,
    granularity,
    autoFollow,
    programmaticScrollRef,
    taskType,
  ]);

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
    if (!seriesRef.current || !markersRef.current) return;
    const candleTimes = candles.map((c) => Number(c.time));

    const tradeMarkers = windowedTradeMarkers
      .map((t: WindowedTradeMarker) => {
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
    windowedTradeMarkers,
    candles,
    selectedTradeId,
    highlightedTradeIds,
    eventMarkers,
    markerDisplayCutoffSec,
    programmaticScrollRef,
  ]);

  const handleGranularityChange = (e: SelectChangeEvent) => {
    // Save the current visible time range so we can restore it after new
    // candles load, keeping the user's view position stable.
    const ts = chartRef.current?.timeScale();
    if (ts) {
      const range = ts.getVisibleRange();
      if (range) {
        savedVisibleRangeRef.current = {
          from: Number(range.from),
          to: Number(range.to),
        };
      }
    }
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
        const targetPage = Math.floor(idx / rowsPerPage);
        pendingScrollRef.current = true;
        setPage(targetPage);
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
          setSelectedRowIds(new Set());
          setSelectedPosId(null);
          setHighlightedTradeIds(new Set());
          setPage(0);
        }}
        onResetZoom={() => {
          programmaticScrollRef.current = true;
          chartRef.current?.timeScale().fitContent();
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
            selectedRowIds={selectedRowIds}
            isAllPageSelected={isAllPageSelected}
            isRefreshing={isRefreshing}
            orderBy={orderBy}
            order={order}
            replayColWidths={replayColWidths}
            page={page}
            rowsPerPage={rowsPerPage}
            selectedRowRef={selectedRowRef}
            onConfigureColumns={() => setTradesColConfigOpen(true)}
            onCopySelected={copySelectedRows}
            onSelectAllOnPage={selectAllOnPage}
            onResetSelection={resetSelection}
            onReload={fetchReplayData}
            onSelectTrade={onRowSelect}
            onToggleRowSelection={toggleRowSelection}
            onTogglePageSelection={() => {
              if (isAllPageSelected) {
                setSelectedRowIds((prev) => {
                  const next = new Set(prev);
                  for (const row of paginatedTrades) next.delete(row.id);
                  return next;
                });
              } else {
                selectAllOnPage();
              }
            }}
            onSort={handleSort}
            onPageChange={(_e, newPage) => setPage(newPage)}
            onRowsPerPageChange={(e) => {
              const newVal = parseInt(e.target.value, 10);
              setRowsPerPage(newVal);
              setPage(0);
              setPosRowsPerPage(newVal);
              setPosPage(0);
              setLongPosRowsPerPage(newVal);
              setLongPosPage(0);
              setShortPosRowsPerPage(newVal);
              setShortPosPage(0);
            }}
            resizeHandle={resizeHandle}
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
          selectedPosRowRef={selectedPosRowRef}
          onConfigureColumns={() => setLongPosColConfigOpen(true)}
          onCopySelected={copySelectedLongPositions}
          onSelectAllOnPage={selectAllLongPosOnPage}
          onResetSelection={resetLongPosSelection}
          onReload={fetchReplayData}
          onToggleOpenOnly={() => {
            setShowOpenLongOnly((prev) => !prev);
            setLongPosPage(0);
          }}
          onTogglePageSelection={() => {
            if (isAllLongPosPageSelected) {
              setSelectedLongPosIds((prev) => {
                const next = new Set(prev);
                for (const row of paginatedLongPositions) next.delete(row.id);
                return next;
              });
            } else {
              selectAllLongPosOnPage();
            }
          }}
          onSort={handleLongPosSort}
          onSelectPosition={onPosRowSelect}
          onToggleSelection={toggleLongPosSelection}
          onPageChange={(_e, newPage) => setLongPosPage(newPage)}
          onRowsPerPageChange={(e) => {
            const newVal = parseInt(e.target.value, 10);
            setLongPosRowsPerPage(newVal);
            setLongPosPage(0);
            setRowsPerPage(newVal);
            setPage(0);
            setPosRowsPerPage(newVal);
            setPosPage(0);
            setShortPosRowsPerPage(newVal);
            setShortPosPage(0);
          }}
          resizeHandle={(col) =>
            makeLSResizeHandle(col, longPosColWidths, setLongPosColWidths)
          }
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
          selectedPosRowRef={selectedPosRowRef}
          onConfigureColumns={() => setShortPosColConfigOpen(true)}
          onCopySelected={copySelectedShortPositions}
          onSelectAllOnPage={selectAllShortPosOnPage}
          onResetSelection={resetShortPosSelection}
          onReload={fetchReplayData}
          onToggleOpenOnly={() => {
            setShowOpenShortOnly((prev) => !prev);
            setShortPosPage(0);
          }}
          onTogglePageSelection={() => {
            if (isAllShortPosPageSelected) {
              setSelectedShortPosIds((prev) => {
                const next = new Set(prev);
                for (const row of paginatedShortPositions) next.delete(row.id);
                return next;
              });
            } else {
              selectAllShortPosOnPage();
            }
          }}
          onSort={handleShortPosSort}
          onSelectPosition={onPosRowSelect}
          onToggleSelection={toggleShortPosSelection}
          onPageChange={(_e, newPage) => setShortPosPage(newPage)}
          onRowsPerPageChange={(e) => {
            const newVal = parseInt(e.target.value, 10);
            setShortPosRowsPerPage(newVal);
            setShortPosPage(0);
            setRowsPerPage(newVal);
            setPage(0);
            setPosRowsPerPage(newVal);
            setPosPage(0);
            setLongPosRowsPerPage(newVal);
            setLongPosPage(0);
          }}
          resizeHandle={(col) =>
            makeLSResizeHandle(col, shortPosColWidths, setShortPosColWidths)
          }
        />
      </Box>

      <ColumnConfigDialog
        open={tradesColConfigOpen}
        columns={tradesColConfig}
        onClose={() => setTradesColConfigOpen(false)}
        onSave={updateTradesCols}
        onReset={resetTradesCols}
      />
      <ColumnConfigDialog
        open={longPosColConfigOpen}
        columns={longPosColConfig}
        onClose={() => setLongPosColConfigOpen(false)}
        onSave={updateLongPosCols}
        onReset={resetLongPosCols}
      />
      <ColumnConfigDialog
        open={shortPosColConfigOpen}
        columns={shortPosColConfig}
        onClose={() => setShortPosColConfigOpen(false)}
        onSave={updateShortPosCols}
        onReset={resetShortPosCols}
      />
    </Box>
  );
};

export default TaskTrendPanel;
