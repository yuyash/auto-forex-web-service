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
  Button,
  Checkbox,
  Chip,
  CircularProgress,
  FormControl,
  IconButton,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TablePagination,
  TableRow,
  TableSortLabel,
  Tooltip,
  Typography,
  ToggleButton,
} from '@mui/material';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import SelectAllIcon from '@mui/icons-material/SelectAll';
import DeselectIcon from '@mui/icons-material/Deselect';
import RefreshIcon from '@mui/icons-material/Refresh';
import ZoomOutMapIcon from '@mui/icons-material/ZoomOutMap';
import type { SelectChangeEvent } from '@mui/material/Select';
import { useTheme } from '@mui/material/styles';
import {
  CandlestickSeries,
  createChart,
  createSeriesMarkers,
  type CandlestickData,
  type IChartApi,
  type ISeriesApi,
  type ISeriesMarkersPluginApi,
  type Time,
  type UTCTimestamp,
} from 'lightweight-charts';
import { getAuthToken } from '../../../api/client';
import {
  fetchAllTrades,
  fetchTradesSince,
} from '../../../utils/fetchAllTrades';
import { useSupportedGranularities } from '../../../hooks/useMarketConfig';
import { useTaskEvents, type TaskEvent } from '../../../hooks/useTaskEvents';
import {
  useTaskPositions,
  type TaskPosition,
} from '../../../hooks/useTaskPositions';
import { useTaskSummary } from '../../../hooks/useTaskSummary';
import { TaskType } from '../../../types/common';
import { handleAuthErrorStatus } from '../../../utils/authEvents';
import { detectMarketGaps } from '../../../utils/marketClosedMarkers';
import { MarketClosedHighlight } from '../../../utils/MarketClosedHighlight';
import {
  AdaptiveTimeScale,
  createSuppressedTickMarkFormatter,
  createTooltipTimeFormatter,
} from '../../../utils/adaptiveTimeScalePlugin';
import { useAuth } from '../../../contexts/AuthContext';
import { SequencePositionLine } from '../../../utils/SequencePositionLine';
import { useMetricsOverlay } from './MetricsOverlayChart';

type CandlePoint = CandlestickData<Time>;

const TARGET_CANDLE_COUNT = 10000;
const LOT_UNITS = 1000;

const GRANULARITY_MINUTES: Record<string, number> = {
  M1: 1,
  M2: 2,
  M4: 4,
  M5: 5,
  M10: 10,
  M15: 15,
  M30: 30,
  H1: 60,
  H2: 120,
  H3: 180,
  H4: 240,
  H6: 360,
  H8: 480,
  H12: 720,
  D: 1440,
  W: 10080,
  M: 43200,
};

type ReplayTrade = {
  id: string;
  sequence: number;
  timestamp: string;
  timeSec: UTCTimestamp;
  instrument: string;
  direction: 'long' | 'short' | '';
  units: string;
  price: string;
  execution_method?: string;
  execution_method_display?: string;
  layer_index?: number | null;
  retracement_count?: number | null;
  position_id?: string | null;
};

interface TaskReplayPanelProps {
  taskId: string | number;
  taskType: TaskType;
  instrument: string;
  executionRunId?: number;
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

const ALLOWED_GRANULARITIES = [
  { value: 'M1', label: '1 Minute' },
  { value: 'M5', label: '5 Minutes' },
  { value: 'M15', label: '15 Minutes' },
  { value: 'M30', label: '30 Minutes' },
  { value: 'H1', label: '1 Hour' },
  { value: 'H4', label: '4 Hours' },
  { value: 'H8', label: '8 Hours' },
  { value: 'H12', label: '12 Hours' },
  { value: 'D', label: 'Daily' },
  { value: 'W', label: 'Weekly' },
  { value: 'M', label: 'Monthly' },
];

const ALLOWED_VALUES = new Set(ALLOWED_GRANULARITIES.map((g) => g.value));

const parseUtcTimestamp = (value: unknown): UTCTimestamp | null => {
  if (typeof value === 'number' && Number.isFinite(value)) {
    if (value > 1_000_000_000_000) {
      return Math.floor(value / 1000) as UTCTimestamp;
    }
    if (value > 1_000_000_000) {
      return Math.floor(value) as UTCTimestamp;
    }
  }

  if (typeof value === 'string') {
    const asNumber = Number(value);
    if (Number.isFinite(asNumber)) {
      if (asNumber > 1_000_000_000_000) {
        return Math.floor(asNumber / 1000) as UTCTimestamp;
      }
      if (asNumber > 1_000_000_000) {
        return Math.floor(asNumber) as UTCTimestamp;
      }
    }

    const ms = new Date(value).getTime();
    if (Number.isFinite(ms)) {
      return Math.floor(ms / 1000) as UTCTimestamp;
    }
  }

  return null;
};

const toRfc3339Seconds = (value: string): string => {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toISOString().replace(/\.\d{3}Z$/, 'Z');
};

const TRADING_OPEN_EVENT_TYPES = new Set([
  'open_position',
  'initial_entry',
  'retracement',
]);
const TRADING_CLOSE_EVENT_TYPES = new Set([
  'close_position',
  'take_profit',
  'margin_protection',
  'volatility_lock',
  'volatility_hedge_neutralize',
]);

const toEventMarkerTime = (event: TaskEvent): UTCTimestamp | null => {
  const detailTimestamp =
    typeof event.details?.timestamp === 'string'
      ? event.details.timestamp
      : undefined;
  return (
    parseUtcTimestamp(detailTimestamp) ?? parseUtcTimestamp(event.created_at)
  );
};

const toEventDirection = (event: TaskEvent): 'long' | 'short' | null => {
  const raw = String(event.details?.direction ?? '').toLowerCase();
  if (raw === 'long' || raw === 'short') return raw;
  return null;
};

const recommendGranularity = (
  fromIso: string | undefined,
  toIso: string | undefined,
  available: string[]
): string => {
  if (!fromIso || !toIso || available.length === 0) return 'H1';

  const fromMs = new Date(fromIso).getTime();
  const toMs = new Date(toIso).getTime();
  if (!Number.isFinite(fromMs) || !Number.isFinite(toMs) || toMs <= fromMs)
    return 'H1';

  const rangeMinutes = (toMs - fromMs) / (1000 * 60);
  let best = available[0] ?? 'H1';
  let bestDiff = Number.POSITIVE_INFINITY;

  for (const g of available) {
    const mins = GRANULARITY_MINUTES[g];
    if (!mins) continue;
    const candles = rangeMinutes / mins;
    const diff = Math.abs(candles - TARGET_CANDLE_COUNT);
    if (diff < bestDiff) {
      bestDiff = diff;
      best = g;
    }
  }

  return best;
};

const fetchCandles = async (
  instrument: string,
  granularity: string,
  startTime?: string,
  endTime?: string
): Promise<Record<string, unknown>> => {
  const params = new URLSearchParams();
  params.set('instrument', instrument);
  params.set('granularity', granularity);

  if (startTime && endTime) {
    params.set('from_time', toRfc3339Seconds(startTime));
    params.set('to_time', toRfc3339Seconds(endTime));
  } else {
    params.set('count', '5000');
    if (startTime) params.set('from_time', toRfc3339Seconds(startTime));
    if (endTime) params.set('to_time', toRfc3339Seconds(endTime));
  }

  const MAX_RETRIES = 3;
  const INITIAL_BACKOFF_MS = 1000;

  for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
    const response = await fetch(`/api/market/candles/?${params.toString()}`, {
      method: 'GET',
      credentials: 'include',
      headers: (() => {
        const token = getAuthToken();
        return token
          ? { Authorization: `Bearer ${token}` }
          : ({} as Record<string, string>);
      })(),
    });

    // Retry on 429 with exponential backoff
    if (response.status === 429 && attempt < MAX_RETRIES) {
      const retryAfter = response.headers.get('retry-after');
      const delayMs =
        retryAfter && Number.isFinite(Number(retryAfter))
          ? Number(retryAfter) * 1000
          : INITIAL_BACKOFF_MS * Math.pow(2, attempt);
      await new Promise((r) => setTimeout(r, delayMs));
      continue;
    }

    handleAuthErrorStatus(response.status, {
      source: 'http',
      status: response.status,
      context: 'task_replay_candles',
    });

    const body = (await response.json().catch(() => ({}))) as Record<
      string,
      unknown
    >;
    if (!response.ok) {
      const errorMessage =
        typeof body.error === 'string'
          ? body.error
          : typeof body.detail === 'string'
            ? body.detail
            : `Failed to load candles (HTTP ${response.status})`;
      throw new Error(errorMessage);
    }

    return body;
  }

  throw new Error('Failed to load candles after retries');
};

/** Compute PnL for a single position (used for sorting). */
const computePosPnl = (
  pos: TaskPosition & { _status: 'open' | 'closed' },
  currentPrice: number | null
): number => {
  const entryP = pos.entry_price ? parseFloat(pos.entry_price) : null;
  const exitP = pos.exit_price ? parseFloat(pos.exit_price) : null;
  const units = Math.abs(pos.units ?? 0);
  const dir = String(pos.direction).toLowerCase();
  if (pos._status === 'open' && currentPrice != null && entryP != null) {
    return dir === 'long'
      ? (currentPrice - entryP) * units
      : (entryP - currentPrice) * units;
  }
  if (pos._status === 'closed' && exitP != null && entryP != null) {
    return dir === 'long' ? (exitP - entryP) * units : (entryP - exitP) * units;
  }
  return 0;
};

/** Compute Pips for a single position (used for sorting and display). */
const computePosPips = (
  pos: TaskPosition & { _status: 'open' | 'closed' },
  currentPrice: number | null,
  pipSize: number | null | undefined
): number => {
  if (!pipSize) return 0;
  const entryP = pos.entry_price ? parseFloat(pos.entry_price) : null;
  if (entryP == null || !Number.isFinite(entryP)) return 0;
  const dir = String(pos.direction).toLowerCase();
  if (pos._status === 'open' && currentPrice != null) {
    const diff = dir === 'long' ? currentPrice - entryP : entryP - currentPrice;
    const pips = diff / pipSize;
    return Number.isFinite(pips) ? pips : 0;
  }
  const exitP = pos.exit_price ? parseFloat(pos.exit_price) : null;
  if (exitP != null && Number.isFinite(exitP)) {
    const diff = dir === 'long' ? exitP - entryP : entryP - exitP;
    const pips = diff / pipSize;
    return Number.isFinite(pips) ? pips : 0;
  }
  return 0;
};

export const TaskReplayPanel: React.FC<TaskReplayPanelProps> = ({
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
  const muiTheme = useTheme();
  const isDark = muiTheme.palette.mode === 'dark';
  const timezone = user?.timezone || 'UTC';

  const [candles, setCandles] = useState<CandlePoint[]>([]);
  const [trades, setTrades] = useState<ReplayTrade[]>([]);
  const [selectedTradeId, setSelectedTradeId] = useState<string | null>(null);
  // State-based chart reference so hooks can react to chart creation
  const [chartInstance, setChartInstance] = useState<IChartApi | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { granularities } = useSupportedGranularities();

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
  const { events: taskLifecycleEvents } = useTaskEvents({
    taskId,
    taskType,
    executionRunId,
    source: 'task',
    page: 1,
    pageSize: 5000,
    enableRealTimeUpdates,
  });
  const { events: tradingEvents } = useTaskEvents({
    taskId,
    taskType,
    executionRunId,
    source: 'trading',
    page: 1,
    pageSize: 5000,
    enableRealTimeUpdates,
  });
  const { events: strategyEvents } = useTaskEvents({
    taskId,
    taskType,
    executionRunId,
    source: 'strategy',
    page: 1,
    pageSize: 5000,
    enableRealTimeUpdates,
  });

  // Auto-follow: track whether the chart should auto-scroll to the position line
  const [autoFollow, setAutoFollow] = useState(true);
  // Timestamp-based guard: any visibleLogicalRangeChange that fires within
  // this window (ms) after a programmatic scroll is treated as our own and
  // will NOT disable auto-follow.  This is far more reliable than the old
  // boolean flag + requestAnimationFrame approach because the chart library
  // can fire the change callback with unpredictable async delays.
  const programmaticScrollUntilRef = useRef(0);
  const PROGRAMMATIC_SCROLL_GUARD_MS = 400;
  // Keep the old ref name around as a thin wrapper so every call-site still
  // compiles – but now it just sets / reads the timestamp.
  // Wrapped in useMemo so the object identity is stable across renders,
  // which satisfies the react-hooks/exhaustive-deps rule.
  const programmaticScrollRef = useMemo(
    () => ({
      get current() {
        return Date.now() < programmaticScrollUntilRef.current;
      },
      set current(v: boolean) {
        programmaticScrollUntilRef.current = v
          ? Date.now() + PROGRAMMATIC_SCROLL_GUARD_MS
          : 0;
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

  type SortableKey =
    | 'timestamp'
    | 'direction'
    | 'layer_index'
    | 'retracement_count'
    | 'units'
    | 'price'
    | 'execution_method';
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
    (e: React.MouseEvent) => {
      e.preventDefault();
      dragRef.current = { startY: e.clientY, startHeight: chartHeight };

      const onMouseMove = (ev: MouseEvent) => {
        if (!dragRef.current) return;
        const diff = ev.clientY - dragRef.current.startY;
        const maxHeight = window.innerHeight;
        const newHeight = Math.min(
          maxHeight,
          Math.max(MIN_CHART_HEIGHT, dragRef.current.startHeight + diff)
        );
        setChartHeight(newHeight);
      };

      const onMouseUp = () => {
        dragRef.current = null;
        document.removeEventListener('mousemove', onMouseMove);
        document.removeEventListener('mouseup', onMouseUp);
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
      document.addEventListener('mousemove', onMouseMove);
      document.addEventListener('mouseup', onMouseUp);
    },
    [chartHeight]
  );

  // Column resize state
  const defaultReplayWidths: Record<string, number> = {
    timestamp: 150,
    direction: 55,
    layer_index: 50,
    retracement_count: 35,
    units: 65,
    price: 85,
    execution_method: 95,
  };
  const [replayColWidths, setReplayColWidths] = useState(defaultReplayWidths);
  const replayResizeRef = useRef<{
    col: string;
    startX: number;
    startW: number;
  } | null>(null);

  const handleColResizeStart = useCallback(
    (e: React.MouseEvent, col: string) => {
      e.preventDefault();
      e.stopPropagation();
      replayResizeRef.current = {
        col,
        startX: e.clientX,
        startW: replayColWidths[col] ?? 100,
      };
      const onMove = (ev: MouseEvent) => {
        if (!replayResizeRef.current) return;
        const diff = ev.clientX - replayResizeRef.current.startX;
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
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
      };
      document.body.style.cursor = 'col-resize';
      document.body.style.userSelect = 'none';
      document.addEventListener('mousemove', onMove);
      document.addEventListener('mouseup', onUp);
    },
    [replayColWidths]
  );

  const resizeHandle = useCallback(
    (col: string) => (
      <Box
        onMouseDown={(e) => handleColResizeStart(e, col)}
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

  // ── Positions column resize ──
  const defaultPosWidths: Record<string, number> = {
    entry_time: 130,
    exit_time: 130,
    _status: 65,
    direction: 65,
    layer_index: 50,
    retracement_count: 50,
    units: 65,
    entry_price: 85,
    exit_price: 85,
    _pips: 75,
    _pnl: 90,
  };
  const [posColWidths, setPosColWidths] = useState(defaultPosWidths);
  const posResizeRef = useRef<{
    col: string;
    startX: number;
    startW: number;
  } | null>(null);

  const handlePosColResizeStart = useCallback(
    (e: React.MouseEvent, col: string) => {
      e.preventDefault();
      e.stopPropagation();
      posResizeRef.current = {
        col,
        startX: e.clientX,
        startW: posColWidths[col] ?? 100,
      };
      const onMove = (ev: MouseEvent) => {
        if (!posResizeRef.current) return;
        const diff = ev.clientX - posResizeRef.current.startX;
        const w = Math.max(40, posResizeRef.current.startW + diff);
        setPosColWidths((prev) => ({
          ...prev,
          [posResizeRef.current!.col]: w,
        }));
      };
      const onUp = () => {
        posResizeRef.current = null;
        document.removeEventListener('mousemove', onMove);
        document.removeEventListener('mouseup', onUp);
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
      };
      document.body.style.cursor = 'col-resize';
      document.body.style.userSelect = 'none';
      document.addEventListener('mousemove', onMove);
      document.addEventListener('mouseup', onUp);
    },
    [posColWidths]
  );

  const posResizeHandle = useCallback(
    (col: string) => (
      <Box
        onMouseDown={(e) => handlePosColResizeStart(e, col)}
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
    [handlePosColResizeStart]
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
    const header = [
      'Time',
      'Direction',
      'Layer',
      'Ret',
      'Units',
      'Price',
      'Event',
    ].join('\t');
    const rows = sortedTrades
      .filter((r) => selectedRowIds.has(r.id))
      .map((r) =>
        [
          new Date(r.timestamp).toLocaleString(),
          r.direction ? r.direction.toUpperCase() : '',
          r.layer_index ?? '-',
          r.retracement_count ?? '-',
          r.units,
          r.price ? `¥${parseFloat(r.price).toFixed(3)}` : '-',
          r.execution_method_display || r.execution_method || '-',
        ].join('\t')
      );
    navigator.clipboard.writeText([header, ...rows].join('\n'));
  }, [selectedRowIds, sortedTrades]);

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
  const allPositions = useMemo<
    (TaskPosition & { _status: 'open' | 'closed' })[]
  >(() => {
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

  const [showOpenPosOnly, setShowOpenPosOnly] = useState(false);

  const [posPage, setPosPage] = useState(0);
  const [posRowsPerPage, setPosRowsPerPage] = useState(10);

  type PosSortableKey =
    | 'entry_time'
    | 'exit_time'
    | '_status'
    | 'direction'
    | 'layer_index'
    | 'retracement_count'
    | 'units'
    | 'entry_price'
    | 'exit_price'
    | '_pips'
    | '_pnl';
  const [posOrderBy, setPosOrderBy] = useState<PosSortableKey>('entry_time');
  const [posOrder, setPosOrder] = useState<'asc' | 'desc'>('desc');

  const handlePosSort = useCallback((column: PosSortableKey) => {
    setPosOrderBy((prev) => {
      if (prev === column) {
        setPosOrder((o) => (o === 'asc' ? 'desc' : 'asc'));
        return prev;
      }
      setPosOrder(
        column === 'entry_time' || column === 'exit_time' ? 'desc' : 'asc'
      );
      return column;
    });
    setPosPage(0);
  }, []);

  const sortedPositions = useMemo(() => {
    const base = showOpenPosOnly
      ? allPositions.filter((p) => p._status === 'open')
      : allPositions;
    return [...base].sort((a, b) => {
      let cmp = 0;
      switch (posOrderBy) {
        case 'entry_time':
          cmp =
            new Date(a.entry_time).getTime() - new Date(b.entry_time).getTime();
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
          cmp = Math.abs(a.units ?? 0) - Math.abs(b.units ?? 0);
          break;
        case 'entry_price':
          cmp =
            parseFloat(a.entry_price || '0') - parseFloat(b.entry_price || '0');
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
      return posOrder === 'asc' ? cmp : -cmp;
    });
  }, [
    allPositions,
    showOpenPosOnly,
    posOrderBy,
    posOrder,
    currentPrice,
    pipSize,
  ]);

  const paginatedPositions = useMemo(
    () =>
      sortedPositions.slice(
        posPage * posRowsPerPage,
        posPage * posRowsPerPage + posRowsPerPage
      ),
    [sortedPositions, posPage, posRowsPerPage]
  );

  // Position row selection
  const [selectedPosIds, setSelectedPosIds] = useState<Set<string>>(new Set());

  // Single-position highlight (like selectedTradeId for trades)
  const [selectedPosId, setSelectedPosId] = useState<string | null>(null);
  // Set of trade IDs highlighted because of a position click
  const [highlightedTradeIds, setHighlightedTradeIds] = useState<Set<string>>(
    new Set()
  );
  const selectedPosRowRef = useRef<HTMLTableRowElement | null>(null);
  const pendingPosScrollRef = useRef(false);

  const isAllPosPageSelected =
    paginatedPositions.length > 0 &&
    paginatedPositions.every((r) => selectedPosIds.has(r.id));

  const togglePosSelection = useCallback((id: string) => {
    setSelectedPosIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const selectAllPosOnPage = useCallback(() => {
    setSelectedPosIds((prev) => {
      const next = new Set(prev);
      for (const row of paginatedPositions) next.add(row.id);
      return next;
    });
  }, [paginatedPositions]);

  const resetPosSelection = useCallback(() => {
    setSelectedPosIds(new Set());
  }, []);

  const copySelectedPositions = useCallback(() => {
    const header = [
      'Open Time',
      'Close Time',
      'Status',
      'Dir',
      'Layer',
      'Retrace',
      'Units',
      'Entry',
      'Exit',
      'Pips',
      'PnL',
    ].join('\t');
    const rows = allPositions
      .filter((r) => selectedPosIds.has(r.id))
      .map((pos) => {
        const isOpen = pos._status === 'open';
        const entryP = pos.entry_price ? parseFloat(pos.entry_price) : null;
        const exitP = pos.exit_price ? parseFloat(pos.exit_price) : null;
        const units = Math.abs(pos.units ?? 0);
        const dir = String(pos.direction).toLowerCase();
        let pnl: number | null = null;
        if (isOpen && currentPrice != null && entryP != null) {
          pnl =
            dir === 'long'
              ? (currentPrice - entryP) * units
              : (entryP - currentPrice) * units;
        } else if (!isOpen && exitP != null && entryP != null) {
          pnl =
            dir === 'long'
              ? (exitP - entryP) * units
              : (entryP - exitP) * units;
        }
        const pips = computePosPips(pos, currentPrice, pipSize);
        const hasPrice = isOpen
          ? currentPrice != null && entryP != null
          : exitP != null && entryP != null;
        return [
          pos.entry_time ? new Date(pos.entry_time).toLocaleString() : '-',
          pos.exit_time ? new Date(pos.exit_time).toLocaleString() : '-',
          isOpen ? 'Open' : 'Closed',
          dir.toUpperCase(),
          pos.layer_index ?? '-',
          pos.retracement_count ?? '-',
          pos.units,
          entryP != null ? `¥${entryP.toFixed(3)}` : '-',
          exitP != null ? `¥${exitP.toFixed(3)}` : '-',
          pipSize && hasPrice ? pips.toFixed(1) : '-',
          pnl != null ? pnl.toFixed(2) : '-',
        ].join('\t');
      });
    navigator.clipboard.writeText([header, ...rows].join('\n'));
  }, [selectedPosIds, allPositions, currentPrice, pipSize]);

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
        setSelectedPosId(pos.id);
        const posIdx = sortedPositions.findIndex((p) => p.id === pos.id);
        if (posIdx !== -1) {
          const targetPosPage = Math.floor(posIdx / posRowsPerPage);
          pendingPosScrollRef.current = true;
          setPosPage(targetPosPage);
        }
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
    sortedPositions,
    posRowsPerPage,
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
  }, [posPage, selectedPosId]);

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

  const [granularity, setGranularity] = useState<string>('H1');
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

  // Attach metric overlay series (Margin Ratio, ATR, thresholds) to the
  // candlestick chart so they share the exact same X-axis.
  useMetricsOverlay({
    taskId: String(taskId),
    taskType,
    executionRunId,
    enableRealTimeUpdates,
    chart: chartInstance,
    candleTimestamps: candleTimestampsMemo,
    currentTickTimestamp: enableRealTimeUpdates ? currentTick?.timestamp : null,
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
    const interval = setInterval(refetchPnl, 10000);
    return () => clearInterval(interval);
  }, [enableRealTimeUpdates, refetchPnl]);

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
      if (isInitialLoad) {
        setIsLoading(true);
      } else {
        setIsRefreshing(true);
      }
      setError(null);

      // Fetch candles first — show chart ASAP before loading trades.
      // Errors here are only fatal on the very first load (when we have
      // no data to show).  On subsequent fetches we keep the previously
      // loaded candles visible so that stopping a task does not wipe the chart.
      //
      // During polling (non-initial loads), candle data is only refreshed
      // every CANDLE_REFRESH_INTERVAL_MS (60s) because only the latest bar
      // changes.  Trades and positions (from local DB) are always fetched.
      const now = Date.now();
      const shouldFetchCandles =
        isInitialLoad ||
        now - lastCandleFetchRef.current >= CANDLE_REFRESH_INTERVAL_MS;
      let candlesFetched = false;

      if (shouldFetchCandles) {
        try {
          const candleResponse = await fetchCandles(
            instrument,
            granularity,
            startTime,
            endTime
          );
          const rawCandles = Array.isArray(candleResponse?.candles)
            ? candleResponse.candles
            : [];
          const candleByTime = new Map<number, CandlePoint>();
          rawCandles
            .map((c: Record<string, unknown>) => {
              const parsedTime = parseUtcTimestamp(c.time);
              const open = Number(c.open);
              const high = Number(c.high);
              const low = Number(c.low);
              const close = Number(c.close);
              if (
                parsedTime === null ||
                [open, high, low, close].some((v) => Number.isNaN(v))
              ) {
                return null;
              }
              return {
                time: parsedTime,
                open,
                high,
                low,
                close,
              } as CandlePoint;
            })
            .filter((v: CandlePoint | null): v is CandlePoint => v !== null)
            .forEach((c) => candleByTime.set(Number(c.time), c));

          const candlePoints: CandlePoint[] = Array.from(
            candleByTime.values()
          ).sort((a, b) => Number(a.time) - Number(b.time));
          // Only update candles state when we receive non-empty data so that a
          // transient empty response (e.g. market API hiccup during polling)
          // does not wipe out previously loaded candles and destroy the chart.
          if (candlePoints.length > 0) {
            setCandles((prev) => {
              // Skip update if candle count and last candle timestamp are identical
              if (
                prev.length === candlePoints.length &&
                prev.length > 0 &&
                Number(prev[prev.length - 1].time) ===
                  Number(candlePoints[candlePoints.length - 1].time)
              ) {
                return prev;
              }
              return candlePoints;
            });
          }
          candlesFetched = true;
          lastCandleFetchRef.current = Date.now();
        } catch (candleError) {
          // On the very first load with no existing data, propagate the error
          // so the user sees feedback.  Otherwise silently keep the old candles.
          if (isInitialLoad) {
            throw candleError;
          }
          console.warn('Failed to refresh candle data:', candleError);
        }
      } // end shouldFetchCandles

      // Mark initial load complete and show chart before fetching trades.
      // This lets the user see candles immediately while trades load lazily.
      if (isInitialLoad && candlesFetched) {
        hasLoadedOnce.current = true;
        setIsLoading(false);
      }

      // Small delay between candle and trade requests to avoid burst traffic
      // that can trigger OANDA / backend rate limits.
      // Only needed when we actually fetched candles this cycle.
      if (shouldFetchCandles) {
        await new Promise((r) => setTimeout(r, 300));
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
        // On the very first load when candles also failed, propagate.
        // Otherwise keep existing trades and log the warning.
        if (isInitialLoad && !candlesFetched) {
          throw tradeError;
        }
        console.warn('Failed to refresh trade data:', tradeError);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load replay data');
    } finally {
      hasLoadedOnce.current = true;
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, [
    instrument,
    granularity,
    startTime,
    endTime,
    taskType,
    taskId,
    executionRunId,
    mapRawTrades,
  ]);

  useEffect(() => {
    fetchReplayData();
  }, [fetchReplayData]);

  useEffect(() => {
    if (!enableRealTimeUpdates) return undefined;
    const id = setInterval(fetchReplayData, 10000);
    return () => clearInterval(id);
  }, [enableRealTimeUpdates, fetchReplayData]);

  useEffect(() => {
    tradesRef.current = trades;
  }, [trades]);

  // Chart height is managed by flex layout + ResizeObserver

  // Derived boolean: true once we have candle data.  Used as a dependency
  // for the chart-creation effect so it only fires on the false→true
  // transition, not on every candle-count change.
  const hasCandles = candles.length > 0;

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

    const series = chart.addSeries(CandlestickSeries, {
      upColor: '#16a34a',
      downColor: '#ef4444',
      wickUpColor: '#16a34a',
      wickDownColor: '#ef4444',
      borderUpColor: '#16a34a',
      borderDownColor: '#ef4444',
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
    chart.timeScale().subscribeVisibleLogicalRangeChange(() => {
      if (programmaticScrollRef.current) return;
      setAutoFollow(false);
    });

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
      chart.remove();
      chartRef.current = null;
      setChartInstance(null);
      seriesRef.current = null;
      markersRef.current = null;
      highlightRef.current = null;
      adaptiveRef.current = null;
      sequenceLineRef.current = null;
      hasInitialFit.current = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- chartHeight is read once for initial creation; ResizeObserver handles subsequent resizes.  We derive `hasCandles` (boolean) so the effect only re-runs on the false→true transition and never on candle-count changes that would needlessly destroy and recreate the chart.
  }, [isLoading, hasCandles, timezone, isDark]);

  // Track whether this is the first candle load (for initial fitContent)
  const hasInitialFit = useRef(false);

  // Update candle data, market gaps, and fit chart when data changes
  useEffect(() => {
    if (!seriesRef.current || !markersRef.current) return;

    // Guard setData so the resulting visible-range change doesn't disable auto-follow
    programmaticScrollRef.current = true;
    try {
      seriesRef.current.setData(candles);
    } catch (e) {
      console.warn('Failed to set candle data:', e);
      return;
    }

    const times = candles.map((c) => Number(c.time));

    if (highlightRef.current) {
      highlightRef.current.setGaps(detectMarketGaps(times));
    }

    // Only fit content on the very first load — preserve user's zoom/pan on updates
    if (candles.length > 0 && !hasInitialFit.current) {
      programmaticScrollRef.current = true;
      try {
        chartRef.current?.timeScale().fitContent();
      } catch (e) {
        console.warn('Failed to fit chart content:', e);
      }
      hasInitialFit.current = true;
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
  }, [candles, programmaticScrollRef]);

  // Auto-follow: show ~40 candles worth of data with the position line centred.
  // The visible half-width adapts to the selected granularity so the zoom
  // level always feels natural regardless of candle size.
  const AUTO_FOLLOW_CANDLES = 500;

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
    // viewport.  We use logical-index based positioning so that market gaps
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

          const halfCandles = AUTO_FOLLOW_CANDLES / 2;
          programmaticScrollRef.current = true;
          try {
            ts.setVisibleLogicalRange({
              from: logicalCenter - halfCandles,
              to: logicalCenter + halfCandles,
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
  ]);

  const eventMarkers = useMemo(() => {
    const markers: Array<{
      time: Time;
      position: 'aboveBar' | 'belowBar';
      shape: 'circle' | 'arrowUp' | 'arrowDown';
      color: string;
      text?: string;
    }> = [];

    for (const event of taskLifecycleEvents) {
      const time = toEventMarkerTime(event);
      if (!time) continue;
      markers.push({
        time,
        position: 'aboveBar',
        shape: 'circle',
        color: '#2563eb',
        text: event.event_type_display || event.event_type,
      });
    }

    for (const event of tradingEvents) {
      const time = toEventMarkerTime(event);
      if (!time) continue;

      const eventType = String(event.event_type || '').toLowerCase();
      const direction = toEventDirection(event);
      const isOpen = TRADING_OPEN_EVENT_TYPES.has(eventType);
      const isClose = TRADING_CLOSE_EVENT_TYPES.has(eventType);

      let color = '#111111';
      if (isOpen && direction === 'long') color = '#16a34a';
      else if (isOpen && direction === 'short') color = '#dc2626';
      else if (isClose) color = '#6b7280';

      markers.push({
        time,
        position: direction === 'short' ? 'aboveBar' : 'belowBar',
        shape:
          direction === 'short'
            ? 'arrowDown'
            : direction === 'long'
              ? 'arrowUp'
              : 'circle',
        color,
        text: event.event_type_display || event.event_type,
      });
    }

    for (const event of strategyEvents) {
      const time = toEventMarkerTime(event);
      if (!time) continue;
      markers.push({
        time,
        position: 'belowBar',
        shape: 'circle',
        color: '#111111',
        text: event.event_type_display || event.event_type,
      });
    }

    return markers.sort((a, b) => Number(a.time) - Number(b.time));
  }, [taskLifecycleEvents, tradingEvents, strategyEvents]);

  // Update trade markers when trades or selection changes (without resetting the view)
  useEffect(() => {
    if (!seriesRef.current || !markersRef.current) return;

    const tradeMarkers = trades.map((t) => {
      const selected =
        t.id === selectedTradeId || highlightedTradeIds.has(t.id);
      const units = Number(t.units);
      const lots = Number.isFinite(units) ? Math.abs(units) / LOT_UNITS : null;
      const executionMethod = String(t.execution_method || '').toLowerCase();
      const isClose =
        executionMethod === 'take_profit' ||
        executionMethod === 'margin_protection' ||
        executionMethod === 'volatility_lock';

      const openSide =
        t.direction === 'long'
          ? 'LONG'
          : t.direction === 'short'
            ? 'SHORT'
            : '';
      const closeSide =
        t.direction === 'long'
          ? 'SHORT'
          : t.direction === 'short'
            ? 'LONG'
            : '';
      const sideLabel = isClose ? closeSide : openSide;
      const actionLabel = isClose ? 'CLOSE' : t.direction ? 'OPEN' : '';
      const lotLabel = lots === null ? '' : ` ${Math.round(lots)}L`;

      return {
        time: t.timeSec,
        position:
          t.direction === 'short'
            ? ('aboveBar' as const)
            : ('belowBar' as const),
        shape:
          t.direction === 'short'
            ? ('arrowDown' as const)
            : ('arrowUp' as const),
        color: selected
          ? '#f59e0b'
          : t.direction === 'long'
            ? '#16a34a'
            : t.direction === 'short'
              ? '#ef4444'
              : '#9ca3af',
        text: `${actionLabel} ${sideLabel}${lotLabel}`.trim(),
      };
    });

    try {
      programmaticScrollRef.current = true;
      markersRef.current.setMarkers([...eventMarkers, ...tradeMarkers]);
    } catch (e) {
      console.warn('Failed to set trade markers:', e);
    }
  }, [
    trades,
    selectedTradeId,
    highlightedTradeIds,
    eventMarkers,
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
      setSelectedPosId(pos.id);
      const posIdx = sortedPositions.findIndex((p) => p.id === pos.id);
      if (posIdx !== -1) {
        const targetPosPage = Math.floor(posIdx / posRowsPerPage);
        pendingPosScrollRef.current = true;
        setPosPage(targetPosPage);
      }
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
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 2,
          mb: 1,
          height: 48,
          minHeight: 48,
        }}
      >
        <Box sx={{ px: 2, whiteSpace: 'nowrap' }}>
          <Typography variant="caption" color="text.secondary" lineHeight={1.2}>
            Realized PnL ({pnlCurrency})
          </Typography>
          <Typography
            variant="body2"
            fontWeight="bold"
            lineHeight={1.4}
            color={
              replaySummary.realizedPnl >= 0 ? 'success.main' : 'error.main'
            }
          >
            {replaySummary.realizedPnl >= 0 ? '+' : ''}
            {replaySummary.realizedPnl.toFixed(2)} {pnlCurrency}
          </Typography>
        </Box>

        <Box sx={{ px: 2, whiteSpace: 'nowrap' }}>
          <Typography variant="caption" color="text.secondary" lineHeight={1.2}>
            Unrealized PnL ({pnlCurrency})
          </Typography>
          <Typography
            variant="body2"
            fontWeight="bold"
            lineHeight={1.4}
            color={
              replaySummary.unrealizedPnl >= 0 ? 'success.main' : 'error.main'
            }
          >
            {replaySummary.unrealizedPnl >= 0 ? '+' : ''}
            {replaySummary.unrealizedPnl.toFixed(2)} {pnlCurrency}
          </Typography>
        </Box>

        <Box sx={{ px: 2, whiteSpace: 'nowrap' }}>
          <Typography variant="caption" color="text.secondary" lineHeight={1.2}>
            Total Trades (count)
          </Typography>
          <Typography variant="body2" fontWeight="bold" lineHeight={1.4}>
            {replaySummary.totalTrades} trades
          </Typography>
        </Box>

        <Box sx={{ px: 2, whiteSpace: 'nowrap' }}>
          <Typography variant="caption" color="text.secondary" lineHeight={1.2}>
            Open Positions (count)
          </Typography>
          <Typography variant="body2" fontWeight="bold" lineHeight={1.4}>
            {replaySummary.openPositions} positions
          </Typography>
        </Box>

        <Box sx={{ flex: 1 }} />

        <Box
          sx={{
            width: 20,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          {isRefreshing && <CircularProgress size={16} thickness={5} />}
        </Box>

        <FormControl
          sx={{ minWidth: 110, '& .MuiInputBase-root': { height: 32 } }}
        >
          <InputLabel
            id="replay-granularity-label"
            sx={{ fontSize: '0.75rem' }}
          >
            Granularity
          </InputLabel>
          <Select
            labelId="replay-granularity-label"
            value={granularity}
            label="Granularity"
            onChange={handleGranularityChange}
            sx={{ fontSize: '0.75rem' }}
          >
            {granularityOptions.map((g) => (
              <MenuItem
                key={g.value}
                value={g.value}
                sx={{ fontSize: '0.75rem' }}
              >
                {g.label}
              </MenuItem>
            ))}
          </Select>
        </FormControl>

        {enableRealTimeUpdates && (
          <Button
            variant={autoFollow ? 'contained' : 'outlined'}
            onClick={() => {
              setAutoFollow(true);
              setSelectedTradeId(null);
              setSelectedRowIds(new Set());
              setSelectedPosId(null);
              setHighlightedTradeIds(new Set());
              setPage(0);
            }}
            disabled={autoFollow}
            sx={{
              fontSize: '0.75rem',
              whiteSpace: 'nowrap',
              minWidth: 0,
              px: 1.5,
              height: 32,
            }}
          >
            Follow
          </Button>
        )}

        <Tooltip title="Reset zoom (show all)">
          <IconButton
            onClick={() => {
              programmaticScrollRef.current = true;
              chartRef.current?.timeScale().fitContent();
            }}
            sx={{ height: 32, width: 32 }}
          >
            <ZoomOutMapIcon fontSize="small" />
          </IconButton>
        </Tooltip>
      </Box>

      <Paper
        variant="outlined"
        sx={{
          mt: 0,
          mb: 0,
          height: chartHeight,
          minHeight: MIN_CHART_HEIGHT,
          display: 'flex',
        }}
      >
        <Box ref={chartContainerRef} sx={{ width: '100%', flex: 1 }} />
      </Paper>

      {/* Draggable separator */}
      <Box
        onMouseDown={handleSeparatorMouseDown}
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
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              height: 36,
              minHeight: 36,
            }}
          >
            <Typography variant="subtitle1">Trades</Typography>
            <Typography variant="caption" color="text.secondary" sx={{ ml: 1 }}>
              ({sortedTrades.length})
            </Typography>
            {selectedRowIds.size > 0 && (
              <Typography
                variant="caption"
                color="text.secondary"
                sx={{ ml: 0.5 }}
              >
                — {selectedRowIds.size} selected
              </Typography>
            )}
            <Box sx={{ flex: 1 }} />
            <Tooltip title="Copy selected rows">
              <span>
                <IconButton
                  onClick={copySelectedRows}
                  disabled={selectedRowIds.size === 0}
                >
                  <ContentCopyIcon fontSize="small" />
                </IconButton>
              </span>
            </Tooltip>
            <Tooltip title="Select all on page">
              <IconButton onClick={selectAllOnPage}>
                <SelectAllIcon fontSize="small" />
              </IconButton>
            </Tooltip>
            <Tooltip title="Reset selection">
              <span>
                <IconButton
                  onClick={resetSelection}
                  disabled={selectedRowIds.size === 0}
                >
                  <DeselectIcon fontSize="small" />
                </IconButton>
              </span>
            </Tooltip>
            <Tooltip title="Reload data">
              <IconButton onClick={fetchReplayData} disabled={isRefreshing}>
                <RefreshIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          </Box>

          <TableContainer component={Paper} variant="outlined">
            <Table stickyHeader sx={{ tableLayout: 'fixed', minWidth: 580 }}>
              <TableHead>
                <TableRow>
                  <TableCell padding="checkbox" sx={{ width: 42 }}>
                    <Checkbox
                      checked={isAllPageSelected}
                      indeterminate={
                        !isAllPageSelected &&
                        paginatedTrades.some((r) => selectedRowIds.has(r.id))
                      }
                      onChange={() => {
                        if (isAllPageSelected) {
                          setSelectedRowIds((prev) => {
                            const next = new Set(prev);
                            for (const row of paginatedTrades)
                              next.delete(row.id);
                            return next;
                          });
                        } else {
                          selectAllOnPage();
                        }
                      }}
                    />
                  </TableCell>
                  <TableCell
                    sortDirection={orderBy === 'timestamp' ? order : false}
                    sx={{
                      position: 'relative',
                      width: replayColWidths.timestamp,
                    }}
                  >
                    <TableSortLabel
                      active={orderBy === 'timestamp'}
                      direction={orderBy === 'timestamp' ? order : 'asc'}
                      onClick={() => handleSort('timestamp')}
                    >
                      Time
                    </TableSortLabel>
                    {resizeHandle('timestamp')}
                  </TableCell>
                  <TableCell
                    sortDirection={orderBy === 'direction' ? order : false}
                    sx={{
                      position: 'relative',
                      width: replayColWidths.direction,
                    }}
                  >
                    <TableSortLabel
                      active={orderBy === 'direction'}
                      direction={orderBy === 'direction' ? order : 'asc'}
                      onClick={() => handleSort('direction')}
                    >
                      Direction
                    </TableSortLabel>
                    {resizeHandle('direction')}
                  </TableCell>
                  <TableCell
                    sortDirection={orderBy === 'layer_index' ? order : false}
                    sx={{
                      position: 'relative',
                      width: replayColWidths.layer_index,
                    }}
                  >
                    <TableSortLabel
                      active={orderBy === 'layer_index'}
                      direction={orderBy === 'layer_index' ? order : 'asc'}
                      onClick={() => handleSort('layer_index')}
                    >
                      Layer
                    </TableSortLabel>
                    {resizeHandle('layer_index')}
                  </TableCell>
                  <TableCell
                    align="right"
                    sortDirection={
                      orderBy === 'retracement_count' ? order : false
                    }
                    sx={{
                      position: 'relative',
                      width: replayColWidths.retracement_count,
                    }}
                  >
                    <TableSortLabel
                      active={orderBy === 'retracement_count'}
                      direction={
                        orderBy === 'retracement_count' ? order : 'asc'
                      }
                      onClick={() => handleSort('retracement_count')}
                    >
                      Ret
                    </TableSortLabel>
                    {resizeHandle('retracement_count')}
                  </TableCell>
                  <TableCell
                    align="right"
                    sortDirection={orderBy === 'units' ? order : false}
                    sx={{ position: 'relative', width: replayColWidths.units }}
                  >
                    <TableSortLabel
                      active={orderBy === 'units'}
                      direction={orderBy === 'units' ? order : 'asc'}
                      onClick={() => handleSort('units')}
                    >
                      Units
                    </TableSortLabel>
                    {resizeHandle('units')}
                  </TableCell>
                  <TableCell
                    align="right"
                    sortDirection={orderBy === 'price' ? order : false}
                    sx={{ position: 'relative', width: replayColWidths.price }}
                  >
                    <TableSortLabel
                      active={orderBy === 'price'}
                      direction={orderBy === 'price' ? order : 'asc'}
                      onClick={() => handleSort('price')}
                    >
                      Price
                    </TableSortLabel>
                    {resizeHandle('price')}
                  </TableCell>
                  <TableCell
                    sortDirection={
                      orderBy === 'execution_method' ? order : false
                    }
                    sx={{
                      position: 'relative',
                      width: replayColWidths.execution_method,
                    }}
                  >
                    <TableSortLabel
                      active={orderBy === 'execution_method'}
                      direction={orderBy === 'execution_method' ? order : 'asc'}
                      onClick={() => handleSort('execution_method')}
                    >
                      Event
                    </TableSortLabel>
                    {resizeHandle('execution_method')}
                  </TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {paginatedTrades.map((row) => {
                  const selected = row.id === selectedTradeId;
                  const highlighted = highlightedTradeIds.has(row.id);
                  const checked = selectedRowIds.has(row.id);
                  return (
                    <TableRow
                      key={row.id}
                      ref={selected ? selectedRowRef : undefined}
                      hover
                      onClick={() => onRowSelect(row)}
                      selected={selected || highlighted}
                      sx={{
                        cursor: 'pointer',
                        height: 37,
                        ...((selected || highlighted) && {
                          backgroundColor: 'rgba(245, 158, 11, 0.15)',
                          '&.Mui-selected': {
                            backgroundColor: 'rgba(245, 158, 11, 0.15)',
                          },
                          '&.Mui-selected:hover': {
                            backgroundColor: 'rgba(245, 158, 11, 0.25)',
                          },
                        }),
                      }}
                    >
                      <TableCell padding="checkbox">
                        <Checkbox
                          checked={checked}
                          onClick={(e) => e.stopPropagation()}
                          onChange={() => toggleRowSelection(row.id)}
                        />
                      </TableCell>
                      <TableCell
                        sx={{
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        {new Date(row.timestamp).toLocaleString()}
                      </TableCell>
                      <TableCell
                        sx={{
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        {row.direction ? row.direction.toUpperCase() : ''}
                      </TableCell>
                      <TableCell
                        sx={{
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        {row.layer_index ?? '-'}
                      </TableCell>
                      <TableCell
                        align="right"
                        sx={{
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        {row.retracement_count ?? '-'}
                      </TableCell>
                      <TableCell
                        align="right"
                        sx={{
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        {row.units}
                      </TableCell>
                      <TableCell
                        align="right"
                        sx={{
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        {row.price
                          ? `¥${parseFloat(row.price).toFixed(3)}`
                          : '-'}
                      </TableCell>
                      <TableCell
                        sx={{
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        {row.execution_method_display ||
                          row.execution_method ||
                          '-'}
                      </TableCell>
                    </TableRow>
                  );
                })}
                {/* Fill empty rows to keep table height stable */}
                {paginatedTrades.length < rowsPerPage &&
                  Array.from({
                    length: rowsPerPage - paginatedTrades.length,
                  }).map((_, i) => (
                    <TableRow key={`trade-empty-${i}`} sx={{ height: 37 }}>
                      <TableCell
                        colSpan={8}
                        sx={{
                          backgroundColor: 'action.hover',
                          borderBottom: '1px solid',
                          borderColor: 'divider',
                          py: 0,
                        }}
                      />
                    </TableRow>
                  ))}
              </TableBody>
            </Table>
          </TableContainer>
          <TablePagination
            component="div"
            count={sortedTrades.length}
            page={page}
            onPageChange={(_e, newPage) => setPage(newPage)}
            rowsPerPage={rowsPerPage}
            onRowsPerPageChange={(e) => {
              const newVal = parseInt(e.target.value, 10);
              setRowsPerPage(newVal);
              setPage(0);
              setPosRowsPerPage(newVal);
              setPosPage(0);
            }}
            rowsPerPageOptions={[10, 25, 50, 100]}
          />
        </Box>

        {/* Right column: Positions */}
        <Box
          sx={{
            flex: 1,
            minWidth: 0,
            display: 'flex',
            flexDirection: 'column',
          }}
        >
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              height: 36,
              minHeight: 36,
            }}
          >
            <Typography variant="subtitle1">Positions</Typography>
            <Typography variant="caption" color="text.secondary" sx={{ ml: 1 }}>
              ({allPositions.length})
            </Typography>
            {selectedPosIds.size > 0 && (
              <Typography
                variant="caption"
                color="text.secondary"
                sx={{ ml: 0.5 }}
              >
                — {selectedPosIds.size} selected
              </Typography>
            )}
            <Tooltip title="Show open positions only">
              <ToggleButton
                value="openOnly"
                selected={showOpenPosOnly}
                onChange={() => {
                  setShowOpenPosOnly((prev) => !prev);
                  setPosPage(0);
                }}
                sx={{
                  ml: 1,
                  px: 1,
                  py: 0,
                  height: 24,
                  fontSize: '0.7rem',
                  textTransform: 'none',
                  lineHeight: 1,
                }}
              >
                Open Only
              </ToggleButton>
            </Tooltip>
            <Box sx={{ flex: 1 }} />
            <Tooltip title="Copy selected positions">
              <span>
                <IconButton
                  onClick={copySelectedPositions}
                  disabled={selectedPosIds.size === 0}
                >
                  <ContentCopyIcon fontSize="small" />
                </IconButton>
              </span>
            </Tooltip>
            <Tooltip title="Select all on page">
              <IconButton onClick={selectAllPosOnPage}>
                <SelectAllIcon fontSize="small" />
              </IconButton>
            </Tooltip>
            <Tooltip title="Reset selection">
              <span>
                <IconButton
                  onClick={resetPosSelection}
                  disabled={selectedPosIds.size === 0}
                >
                  <DeselectIcon fontSize="small" />
                </IconButton>
              </span>
            </Tooltip>
            <Tooltip title="Reload data">
              <IconButton onClick={fetchReplayData} disabled={isRefreshing}>
                <RefreshIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          </Box>

          <TableContainer component={Paper} variant="outlined">
            <Table stickyHeader sx={{ tableLayout: 'fixed', minWidth: 940 }}>
              <TableHead>
                <TableRow>
                  <TableCell padding="checkbox" sx={{ width: 42 }}>
                    <Checkbox
                      checked={isAllPosPageSelected}
                      indeterminate={
                        !isAllPosPageSelected &&
                        paginatedPositions.some((r) => selectedPosIds.has(r.id))
                      }
                      onChange={() => {
                        if (isAllPosPageSelected) {
                          setSelectedPosIds((prev) => {
                            const next = new Set(prev);
                            for (const row of paginatedPositions)
                              next.delete(row.id);
                            return next;
                          });
                        } else {
                          selectAllPosOnPage();
                        }
                      }}
                    />
                  </TableCell>
                  <TableCell
                    sx={{
                      position: 'relative',
                      width: posColWidths.entry_time,
                    }}
                    sortDirection={
                      posOrderBy === 'entry_time' ? posOrder : false
                    }
                  >
                    <TableSortLabel
                      active={posOrderBy === 'entry_time'}
                      direction={posOrderBy === 'entry_time' ? posOrder : 'asc'}
                      onClick={() => handlePosSort('entry_time')}
                    >
                      Open Time
                    </TableSortLabel>
                    {posResizeHandle('entry_time')}
                  </TableCell>
                  <TableCell
                    sx={{
                      position: 'relative',
                      width: posColWidths.exit_time,
                    }}
                    sortDirection={
                      posOrderBy === 'exit_time' ? posOrder : false
                    }
                  >
                    <TableSortLabel
                      active={posOrderBy === 'exit_time'}
                      direction={posOrderBy === 'exit_time' ? posOrder : 'asc'}
                      onClick={() => handlePosSort('exit_time')}
                    >
                      Close Time
                    </TableSortLabel>
                    {posResizeHandle('exit_time')}
                  </TableCell>
                  <TableCell
                    sx={{
                      position: 'relative',
                      width: posColWidths._status,
                    }}
                    sortDirection={posOrderBy === '_status' ? posOrder : false}
                  >
                    <TableSortLabel
                      active={posOrderBy === '_status'}
                      direction={posOrderBy === '_status' ? posOrder : 'asc'}
                      onClick={() => handlePosSort('_status')}
                    >
                      Status
                    </TableSortLabel>
                    {posResizeHandle('_status')}
                  </TableCell>
                  <TableCell
                    sx={{
                      position: 'relative',
                      width: posColWidths.direction,
                    }}
                    sortDirection={
                      posOrderBy === 'direction' ? posOrder : false
                    }
                  >
                    <TableSortLabel
                      active={posOrderBy === 'direction'}
                      direction={posOrderBy === 'direction' ? posOrder : 'asc'}
                      onClick={() => handlePosSort('direction')}
                    >
                      Dir
                    </TableSortLabel>
                    {posResizeHandle('direction')}
                  </TableCell>
                  <TableCell
                    sx={{
                      position: 'relative',
                      width: posColWidths.layer_index,
                    }}
                    sortDirection={
                      posOrderBy === 'layer_index' ? posOrder : false
                    }
                  >
                    <TableSortLabel
                      active={posOrderBy === 'layer_index'}
                      direction={
                        posOrderBy === 'layer_index' ? posOrder : 'asc'
                      }
                      onClick={() => handlePosSort('layer_index')}
                    >
                      Layer
                    </TableSortLabel>
                    {posResizeHandle('layer_index')}
                  </TableCell>
                  <TableCell
                    sx={{
                      position: 'relative',
                      width: posColWidths.retracement_count,
                    }}
                    sortDirection={
                      posOrderBy === 'retracement_count' ? posOrder : false
                    }
                  >
                    <TableSortLabel
                      active={posOrderBy === 'retracement_count'}
                      direction={
                        posOrderBy === 'retracement_count' ? posOrder : 'asc'
                      }
                      onClick={() => handlePosSort('retracement_count')}
                    >
                      Retrace
                    </TableSortLabel>
                    {posResizeHandle('retracement_count')}
                  </TableCell>
                  <TableCell
                    align="right"
                    sx={{
                      position: 'relative',
                      width: posColWidths.units,
                    }}
                    sortDirection={posOrderBy === 'units' ? posOrder : false}
                  >
                    <TableSortLabel
                      active={posOrderBy === 'units'}
                      direction={posOrderBy === 'units' ? posOrder : 'asc'}
                      onClick={() => handlePosSort('units')}
                    >
                      Units
                    </TableSortLabel>
                    {posResizeHandle('units')}
                  </TableCell>
                  <TableCell
                    align="right"
                    sx={{
                      position: 'relative',
                      width: posColWidths.entry_price,
                    }}
                    sortDirection={
                      posOrderBy === 'entry_price' ? posOrder : false
                    }
                  >
                    <TableSortLabel
                      active={posOrderBy === 'entry_price'}
                      direction={
                        posOrderBy === 'entry_price' ? posOrder : 'asc'
                      }
                      onClick={() => handlePosSort('entry_price')}
                    >
                      Entry
                    </TableSortLabel>
                    {posResizeHandle('entry_price')}
                  </TableCell>
                  <TableCell
                    align="right"
                    sx={{
                      position: 'relative',
                      width: posColWidths.exit_price,
                    }}
                    sortDirection={
                      posOrderBy === 'exit_price' ? posOrder : false
                    }
                  >
                    <TableSortLabel
                      active={posOrderBy === 'exit_price'}
                      direction={posOrderBy === 'exit_price' ? posOrder : 'asc'}
                      onClick={() => handlePosSort('exit_price')}
                    >
                      Exit
                    </TableSortLabel>
                    {posResizeHandle('exit_price')}
                  </TableCell>
                  <TableCell
                    align="right"
                    sx={{
                      position: 'relative',
                      width: posColWidths._pips,
                    }}
                    sortDirection={posOrderBy === '_pips' ? posOrder : false}
                  >
                    <TableSortLabel
                      active={posOrderBy === '_pips'}
                      direction={posOrderBy === '_pips' ? posOrder : 'asc'}
                      onClick={() => handlePosSort('_pips')}
                    >
                      Pips
                    </TableSortLabel>
                    {posResizeHandle('_pips')}
                  </TableCell>
                  <TableCell
                    align="right"
                    sx={{
                      position: 'relative',
                      width: posColWidths._pnl,
                    }}
                    sortDirection={posOrderBy === '_pnl' ? posOrder : false}
                  >
                    <TableSortLabel
                      active={posOrderBy === '_pnl'}
                      direction={posOrderBy === '_pnl' ? posOrder : 'asc'}
                      onClick={() => handlePosSort('_pnl')}
                    >
                      PnL
                    </TableSortLabel>
                    {posResizeHandle('_pnl')}
                  </TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {paginatedPositions.map((pos) => {
                  const isOpen = pos._status === 'open';
                  const entryP = pos.entry_price
                    ? parseFloat(pos.entry_price)
                    : null;
                  const exitP = pos.exit_price
                    ? parseFloat(pos.exit_price)
                    : null;
                  const units = Math.abs(pos.units ?? 0);
                  const dir = String(pos.direction).toLowerCase();
                  let pnl: number | null = null;
                  if (isOpen && currentPrice != null && entryP != null) {
                    pnl =
                      dir === 'long'
                        ? (currentPrice - entryP) * units
                        : (entryP - currentPrice) * units;
                  } else if (!isOpen && exitP != null && entryP != null) {
                    pnl =
                      dir === 'long'
                        ? (exitP - entryP) * units
                        : (entryP - exitP) * units;
                  }
                  const posSelected = pos.id === selectedPosId;
                  return (
                    <TableRow
                      key={pos.id}
                      ref={posSelected ? selectedPosRowRef : undefined}
                      hover
                      onClick={() => onPosRowSelect(pos)}
                      selected={posSelected}
                      sx={{
                        cursor: 'pointer',
                        height: 37,
                        ...(posSelected && {
                          backgroundColor: 'rgba(245, 158, 11, 0.15)',
                          '&.Mui-selected': {
                            backgroundColor: 'rgba(245, 158, 11, 0.15)',
                          },
                          '&.Mui-selected:hover': {
                            backgroundColor: 'rgba(245, 158, 11, 0.25)',
                          },
                        }),
                      }}
                    >
                      <TableCell padding="checkbox">
                        <Checkbox
                          checked={selectedPosIds.has(pos.id)}
                          onClick={(e) => e.stopPropagation()}
                          onChange={() => togglePosSelection(pos.id)}
                        />
                      </TableCell>
                      <TableCell
                        sx={{
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        {pos.entry_time
                          ? new Date(pos.entry_time).toLocaleString()
                          : '-'}
                      </TableCell>
                      <TableCell
                        sx={{
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        {pos.exit_time
                          ? new Date(pos.exit_time).toLocaleString()
                          : '-'}
                      </TableCell>
                      <TableCell>
                        <Chip
                          label={isOpen ? 'Open' : 'Closed'}
                          color={isOpen ? 'success' : 'default'}
                          variant="outlined"
                          sx={{ height: 20, fontSize: '0.7rem' }}
                        />
                      </TableCell>
                      <TableCell
                        sx={{
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                          color: dir === 'long' ? 'success.main' : 'error.main',
                        }}
                      >
                        {dir.toUpperCase()}
                      </TableCell>
                      <TableCell>{pos.layer_index ?? '-'}</TableCell>
                      <TableCell>{pos.retracement_count ?? '-'}</TableCell>
                      <TableCell align="right">{pos.units}</TableCell>
                      <TableCell align="right">
                        {entryP != null ? `¥${entryP.toFixed(3)}` : '-'}
                      </TableCell>
                      <TableCell align="right">
                        {exitP != null ? `¥${exitP.toFixed(3)}` : '-'}
                      </TableCell>
                      <TableCell
                        align="right"
                        sx={{
                          color: (() => {
                            const pips = computePosPips(
                              pos,
                              currentPrice,
                              pipSize
                            );
                            if (!pipSize) return 'text.secondary';
                            return pips >= 0 ? 'success.main' : 'error.main';
                          })(),
                          fontWeight: 'bold',
                        }}
                      >
                        {(() => {
                          if (!pipSize) return '-';
                          const hasPrice = isOpen
                            ? currentPrice != null && entryP != null
                            : exitP != null && entryP != null;
                          if (!hasPrice) return '-';
                          const pips = computePosPips(
                            pos,
                            currentPrice,
                            pipSize
                          );
                          return `${pips >= 0 ? '+' : ''}${pips.toFixed(1)}`;
                        })()}
                      </TableCell>
                      <TableCell
                        align="right"
                        sx={{
                          color:
                            pnl != null
                              ? pnl >= 0
                                ? 'success.main'
                                : 'error.main'
                              : 'text.secondary',
                          fontWeight: 'bold',
                        }}
                      >
                        {pnl != null
                          ? `${pnl >= 0 ? '+' : ''}${pnl.toFixed(2)}`
                          : '-'}
                      </TableCell>
                    </TableRow>
                  );
                })}
                {/* Fill empty rows to keep table height stable */}
                {paginatedPositions.length < posRowsPerPage &&
                  Array.from({
                    length: posRowsPerPage - paginatedPositions.length,
                  }).map((_, i) => (
                    <TableRow key={`pos-empty-${i}`} sx={{ height: 37 }}>
                      <TableCell
                        colSpan={12}
                        sx={{
                          backgroundColor: 'action.hover',
                          borderBottom: '1px solid',
                          borderColor: 'divider',
                          py: 0,
                        }}
                      />
                    </TableRow>
                  ))}
              </TableBody>
            </Table>
          </TableContainer>
          <TablePagination
            component="div"
            count={sortedPositions.length}
            page={posPage}
            onPageChange={(_e, newPage) => setPosPage(newPage)}
            rowsPerPage={posRowsPerPage}
            onRowsPerPageChange={(e) => {
              const newVal = parseInt(e.target.value, 10);
              setPosRowsPerPage(newVal);
              setPosPage(0);
              setRowsPerPage(newVal);
              setPage(0);
            }}
            rowsPerPageOptions={[10, 25, 50, 100]}
          />
        </Box>
      </Box>
    </Box>
  );
};

export default TaskReplayPanel;
