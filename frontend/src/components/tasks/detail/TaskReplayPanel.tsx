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
} from '@mui/material';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import SelectAllIcon from '@mui/icons-material/SelectAll';
import DeselectIcon from '@mui/icons-material/Deselect';
import RefreshIcon from '@mui/icons-material/Refresh';
import type { SelectChangeEvent } from '@mui/material/Select';
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
import { fetchAllTrades } from '../../../utils/fetchAllTrades';
import { useSupportedGranularities } from '../../../hooks/useMarketConfig';
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
  direction: 'long' | 'short';
  units: string;
  price: string;
  execution_method?: string;
  execution_method_display?: string;
  layer_index?: number | null;
  pnl?: string;
};

interface TaskReplayPanelProps {
  taskId: string | number;
  taskType: TaskType;
  instrument: string;
  startTime?: string;
  endTime?: string;
  enableRealTimeUpdates?: boolean;
  currentTick?: { timestamp: string; price: string | null } | null;
  latestExecution?: {
    realized_pnl?: string;
    unrealized_pnl?: string;
    total_trades?: number;
  };
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
};

export const TaskReplayPanel: React.FC<TaskReplayPanelProps> = ({
  taskId,
  taskType,
  instrument,
  startTime,
  endTime,
  enableRealTimeUpdates = false,
  currentTick,
  latestExecution,
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
  const timezone = user?.timezone || 'UTC';

  const [candles, setCandles] = useState<CandlePoint[]>([]);
  const [trades, setTrades] = useState<ReplayTrade[]>([]);
  const [selectedTradeId, setSelectedTradeId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { granularities } = useSupportedGranularities();

  // Auto-follow: track whether the chart should auto-scroll to the position line
  const [autoFollow, setAutoFollow] = useState(true);
  // Guard flag so our own setVisibleRange calls don't disable auto-follow
  const programmaticScrollRef = useRef(false);

  // Re-enable auto-follow when real-time updates are turned on (task started)
  useEffect(() => {
    if (enableRealTimeUpdates) {
      setAutoFollow(true);
    }
  }, [enableRealTimeUpdates]);

  type SortableKey =
    | 'sequence'
    | 'timestamp'
    | 'direction'
    | 'layer_index'
    | 'units'
    | 'price'
    | 'pnl'
    | 'execution_method';
  const [orderBy, setOrderBy] = useState<SortableKey>('timestamp');
  const [order, setOrder] = useState<'asc' | 'desc'>('asc');
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(10);

  // Row selection for copy
  const [selectedRowIds, setSelectedRowIds] = useState<Set<string>>(new Set());

  // Column resize state
  const defaultReplayWidths: Record<string, number> = {
    sequence: 40,
    timestamp: 150,
    direction: 55,
    layer_index: 50,
    units: 65,
    price: 85,
    pnl: 85,
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
        case 'sequence':
          cmp = a.sequence - b.sequence;
          break;
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
        case 'units':
          cmp = Number(a.units) - Number(b.units);
          break;
        case 'price':
          cmp = Number(a.price) - Number(b.price);
          break;
        case 'pnl':
          cmp = (Number(a.pnl) || 0) - (Number(b.pnl) || 0);
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
      '#',
      'Time',
      'Direction',
      'Layer',
      'Units',
      'Price',
      'PnL',
      'Event',
    ].join('\t');
    const rows = sortedTrades
      .filter((r) => selectedRowIds.has(r.id))
      .map((r) =>
        [
          r.sequence,
          new Date(r.timestamp).toLocaleString(),
          r.direction.toUpperCase(),
          r.layer_index ?? '-',
          r.units,
          r.price ? `¥${parseFloat(r.price).toFixed(3)}` : '-',
          r.pnl ? `¥${parseFloat(r.pnl).toFixed(3)}` : '-',
          r.execution_method_display || r.execution_method || '-',
        ].join('\t')
      );
    navigator.clipboard.writeText([header, ...rows].join('\n'));
  }, [selectedRowIds, sortedTrades]);

  // Reset to first page when sort changes (not on data refresh)
  useEffect(() => {
    setPage(0);
  }, [orderBy, order]);

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
  const pnlCurrency = instrument?.includes('_')
    ? instrument.split('_')[1]
    : 'N/A';

  const replaySummary = useMemo(() => {
    const pnlFromTrades = trades.reduce((sum, trade) => {
      const pnl = Number(trade.pnl);
      return Number.isFinite(pnl) ? sum + pnl : sum;
    }, 0);

    const realizedRaw =
      latestExecution?.realized_pnl !== undefined
        ? Number(latestExecution.realized_pnl)
        : pnlFromTrades;

    // Compute unrealized PnL from open trades using current tick price.
    // Use close_timestamp (not pnl) to detect open trades — matches backend logic.
    const tickPrice =
      currentTick?.price != null ? parseFloat(currentTick.price) : null;
    const unrealizedFromTrades = trades.reduce((sum, trade) => {
      const raw = trade as unknown as Record<string, unknown>;
      const isOpen = raw.close_timestamp == null;
      if (!isOpen) return sum;
      if (tickPrice == null) return sum;
      const openPrice =
        raw.open_price != null ? parseFloat(String(raw.open_price)) : NaN;
      if (!Number.isFinite(openPrice)) return sum;
      const units = Math.abs(Number(trade.units));
      if (!Number.isFinite(units)) return sum;
      const dir = trade.direction;
      const pnl =
        dir === 'long'
          ? (tickPrice - openPrice) * units
          : (openPrice - tickPrice) * units;
      return sum + pnl;
    }, 0);

    const unrealizedRaw =
      tickPrice != null
        ? unrealizedFromTrades
        : latestExecution?.unrealized_pnl !== undefined
          ? Number(latestExecution.unrealized_pnl)
          : 0;

    const totalTradesRaw =
      typeof latestExecution?.total_trades === 'number'
        ? latestExecution.total_trades
        : trades.length;

    const openTradesCount = trades.filter((t) => {
      const raw = t as unknown as Record<string, unknown>;
      return raw.close_timestamp == null;
    }).length;

    return {
      realizedPnl: Number.isFinite(realizedRaw) ? realizedRaw : 0,
      unrealizedPnl: Number.isFinite(unrealizedRaw) ? unrealizedRaw : 0,
      totalTrades: totalTradesRaw,
      openTrades: openTradesCount,
    };
  }, [latestExecution, trades, currentTick?.price]);

  useEffect(() => {
    setGranularity(recommendedGranularity);
  }, [recommendedGranularity, instrument, startTime, endTime]);

  const hasLoadedOnce = useRef(false);

  const fetchReplayData = useCallback(async () => {
    const isInitialLoad = !hasLoadedOnce.current;
    try {
      if (isInitialLoad) {
        setIsLoading(true);
      } else {
        setIsRefreshing(true);
      }
      setError(null);

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
      setCandles(candlePoints);

      const rawTrades = await fetchAllTrades(String(taskId), taskType);

      const tradeRows: ReplayTrade[] = rawTrades
        .map((t: Record<string, unknown>, idx: number): ReplayTrade | null => {
          const timestamp = String(t.timestamp || '');
          const parsedTime = parseUtcTimestamp(timestamp);
          const direction = String(t.direction || '').toLowerCase();
          const mappedDirection =
            direction === 'buy'
              ? 'long'
              : direction === 'sell'
                ? 'short'
                : direction;
          if (
            !timestamp ||
            parsedTime === null ||
            (mappedDirection !== 'long' && mappedDirection !== 'short')
          ) {
            return null;
          }
          return {
            id: `${timestamp}-${idx}`,
            sequence: idx + 1,
            timestamp,
            timeSec: parsedTime,
            instrument: String(t.instrument || instrument),
            direction: mappedDirection as 'long' | 'short',
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
            pnl:
              t.pnl === null || t.pnl === undefined ? undefined : String(t.pnl),
          };
        })
        .filter((v): v is ReplayTrade => v !== null)
        .sort(
          (a, b) =>
            new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
        );

      setTrades(tradeRows);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load replay data');
    } finally {
      hasLoadedOnce.current = true;
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, [instrument, granularity, startTime, endTime, taskType, taskId]);

  useEffect(() => {
    fetchReplayData();
  }, [fetchReplayData]);

  useEffect(() => {
    if (!enableRealTimeUpdates) return undefined;
    const id = setInterval(fetchReplayData, 5000);
    return () => clearInterval(id);
  }, [enableRealTimeUpdates, fetchReplayData]);

  useEffect(() => {
    tradesRef.current = trades;
  }, [trades]);

  const rowsPerPageRef = useRef(rowsPerPage);
  useEffect(() => {
    rowsPerPageRef.current = rowsPerPage;
  }, [rowsPerPage]);

  const computeChartHeight = useCallback(() => {
    const container = chartContainerRef.current;
    if (!container) return 360;
    // Measure how much space the chart container actually has
    // by reading the flex-computed height of its wrapper
    const wrapper = container.parentElement;
    if (wrapper && wrapper.clientHeight > 0) {
      return Math.max(200, wrapper.clientHeight);
    }
    // Fallback: calculate from panel position
    const panelTop = panelRootRef.current?.getBoundingClientRect().top ?? 230;
    const tableRowHeight = 37;
    const currentRowsPerPage = rowsPerPageRef.current;
    const tableMinHeight = 40 + tableRowHeight * currentRowsPerPage;
    const fixedContent = 16 + 85 + 60 + tableMinHeight + 56 + 36 + 24 + 28;
    const available = window.innerHeight - panelTop - fixedContent;
    return Math.max(200, Math.round(available));
  }, []);

  // Chart height is managed by flex layout + ResizeObserver

  useEffect(() => {
    if (isLoading || candles.length === 0) return;
    if (!chartContainerRef.current || chartRef.current) return;

    const container = chartContainerRef.current;

    const dynamicHeight = computeChartHeight();
    const chart = createChart(container, {
      height: dynamicHeight,
      layout: {
        background: { color: '#ffffff' },
        textColor: '#334155',
      },
      grid: {
        vertLines: { visible: false },
        horzLines: { color: '#e2e8f0' },
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
      rightPriceScale: { borderColor: '#cbd5e1' },
      timeScale: {
        borderColor: '#cbd5e1',
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
    seriesRef.current = series;
    markersRef.current = markers;

    const highlight = new MarketClosedHighlight();
    series.attachPrimitive(highlight);
    highlightRef.current = highlight;

    const adaptive = new AdaptiveTimeScale({ timezone });
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
      setSelectedTradeId(nearest.id);
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
      requestAnimationFrame(() => {
        programmaticScrollRef.current = false;
      });
    });
    observer.observe(container);
    // Guard initial layout so it doesn't disable auto-follow
    programmaticScrollRef.current = true;
    chart.applyOptions({ width: container.clientWidth });
    requestAnimationFrame(() => {
      programmaticScrollRef.current = false;
    });

    return () => {
      observer.disconnect();
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
      markersRef.current = null;
      highlightRef.current = null;
      adaptiveRef.current = null;
      sequenceLineRef.current = null;
      hasInitialFit.current = false;
    };
  }, [isLoading, candles.length, timezone, computeChartHeight]);

  // Track whether this is the first candle load (for initial fitContent)
  const hasInitialFit = useRef(false);

  // Update candle data, market gaps, and fit chart when data changes
  useEffect(() => {
    if (!seriesRef.current || !markersRef.current) return;

    seriesRef.current.setData(candles);

    const times = candles.map((c) => Number(c.time));

    if (highlightRef.current) {
      highlightRef.current.setGaps(detectMarketGaps(times));
    }

    // Only fit content on the very first load — preserve user's zoom/pan on updates
    if (candles.length > 0 && !hasInitialFit.current) {
      programmaticScrollRef.current = true;
      chartRef.current?.timeScale().fitContent();
      hasInitialFit.current = true;
      requestAnimationFrame(() => {
        programmaticScrollRef.current = false;
      });
    }
  }, [candles]);

  // Auto-follow: show ~40 candles worth of data with the position line centred.
  // The visible half-width adapts to the selected granularity so the zoom
  // level always feels natural regardless of candle size.
  const AUTO_FOLLOW_CANDLES = 500;

  // Update sequence position line when current tick changes
  useEffect(() => {
    if (!sequenceLineRef.current) return;
    if (!enableRealTimeUpdates || !currentTick?.timestamp) {
      sequenceLineRef.current.clear();
      return;
    }
    const price =
      currentTick.price != null ? parseFloat(currentTick.price) : null;
    sequenceLineRef.current.setPosition(currentTick.timestamp, price);

    // Auto-scroll: centre the chart on the current tick (only when auto-follow is on)
    if (autoFollow) {
      const ts = chartRef.current?.timeScale();
      if (ts) {
        const centerSec = Math.floor(
          new Date(currentTick.timestamp).getTime() / 1000
        );
        if (Number.isFinite(centerSec)) {
          const candleMin = GRANULARITY_MINUTES[granularity] ?? 60;
          const halfSec = (AUTO_FOLLOW_CANDLES / 2) * candleMin * 60;
          programmaticScrollRef.current = true;
          ts.setVisibleRange({
            from: (centerSec - halfSec) as Time,
            to: (centerSec + halfSec) as Time,
          });
          // Reset guard after the subscription fires (next microtask)
          requestAnimationFrame(() => {
            programmaticScrollRef.current = false;
          });
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
  ]);

  // Update trade markers when trades or selection changes (without resetting the view)
  useEffect(() => {
    if (!seriesRef.current || !markersRef.current) return;

    const tradeMarkers = trades.map((t) => {
      const selected = t.id === selectedTradeId;
      const units = Number(t.units);
      const lots = Number.isFinite(units) ? Math.abs(units) / LOT_UNITS : null;
      const executionMethod = String(t.execution_method || '').toLowerCase();
      const hasNumericPnl =
        t.pnl !== undefined &&
        t.pnl !== null &&
        t.pnl !== '' &&
        Number.isFinite(Number(t.pnl));
      const isCloseByMethod =
        executionMethod === 'take_profit' ||
        executionMethod === 'margin_protection' ||
        executionMethod === 'volatility_lock';
      const isClose = hasNumericPnl || isCloseByMethod;

      const openSide = t.direction === 'long' ? 'LONG' : 'SHORT';
      const closeSide = t.direction === 'long' ? 'SHORT' : 'LONG';
      const sideLabel = isClose ? closeSide : openSide;
      const actionLabel = isClose ? 'CLOSE' : 'OPEN';
      const lotLabel = lots === null ? '' : ` ${Math.round(lots)}L`;

      return {
        time: t.timeSec,
        position:
          t.direction === 'long'
            ? ('belowBar' as const)
            : ('aboveBar' as const),
        shape:
          t.direction === 'long'
            ? ('arrowUp' as const)
            : ('arrowDown' as const),
        color: selected
          ? '#f59e0b'
          : t.direction === 'long'
            ? '#16a34a'
            : '#ef4444',
        text: `${actionLabel} ${sideLabel}${lotLabel}`,
      };
    });

    markersRef.current.setMarkers(tradeMarkers);
  }, [trades, selectedTradeId]);

  const handleGranularityChange = (e: SelectChangeEvent) => {
    setGranularity(String(e.target.value));
  };

  const onRowSelect = (row: ReplayTrade) => {
    setSelectedTradeId(row.id);
    setAutoFollow(false);
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
    ts.setVisibleRange({
      from: (target - half) as Time,
      to: (target + half) as Time,
    });
    requestAnimationFrame(() => {
      programmaticScrollRef.current = false;
    });
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

  if (error) {
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
        pb: 0,
        display: 'flex',
        flexDirection: 'column',
        flex: 1,
        minHeight: 0,
        overflow: 'hidden',
        boxSizing: 'border-box',
      }}
    >
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
            Open Trades (count)
          </Typography>
          <Typography variant="body2" fontWeight="bold" lineHeight={1.4}>
            {replaySummary.openTrades} trades
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
          size="small"
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
            size="small"
            variant={autoFollow ? 'contained' : 'outlined'}
            onClick={() => setAutoFollow(true)}
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
      </Box>

      <Paper
        variant="outlined"
        sx={{ mt: 1, mb: 1, flex: 1, minHeight: 200, display: 'flex' }}
      >
        <Box ref={chartContainerRef} sx={{ width: '100%', flex: 1 }} />
      </Paper>

      <Box sx={{ display: 'flex', alignItems: 'center', flexShrink: 0 }}>
        <Typography variant="subtitle1">Layer Trade Timeline</Typography>
        {selectedRowIds.size > 0 && (
          <Typography variant="caption" color="text.secondary" sx={{ ml: 1 }}>
            ({selectedRowIds.size} selected)
          </Typography>
        )}
        <Box sx={{ flex: 1 }} />
        <Tooltip title="Copy selected rows">
          <span>
            <IconButton
              size="small"
              onClick={copySelectedRows}
              disabled={selectedRowIds.size === 0}
            >
              <ContentCopyIcon fontSize="small" />
            </IconButton>
          </span>
        </Tooltip>
        <Tooltip title="Select all on page">
          <IconButton size="small" onClick={selectAllOnPage}>
            <SelectAllIcon fontSize="small" />
          </IconButton>
        </Tooltip>
        <Tooltip title="Reset selection">
          <span>
            <IconButton
              size="small"
              onClick={resetSelection}
              disabled={selectedRowIds.size === 0}
            >
              <DeselectIcon fontSize="small" />
            </IconButton>
          </span>
        </Tooltip>
        <Tooltip title="Reload data">
          <IconButton
            size="small"
            onClick={fetchReplayData}
            disabled={isRefreshing}
          >
            <RefreshIcon fontSize="small" />
          </IconButton>
        </Tooltip>
      </Box>

      <TableContainer
        component={Paper}
        variant="outlined"
        sx={{ flex: 1, minHeight: 0, overflow: 'auto' }}
      >
        <Table stickyHeader size="small" sx={{ tableLayout: 'fixed' }}>
          <TableHead>
            <TableRow>
              <TableCell padding="checkbox" sx={{ width: 42 }}>
                <Checkbox
                  size="small"
                  checked={isAllPageSelected}
                  indeterminate={
                    !isAllPageSelected &&
                    paginatedTrades.some((r) => selectedRowIds.has(r.id))
                  }
                  onChange={() => {
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
                />
              </TableCell>
              <TableCell
                sortDirection={orderBy === 'sequence' ? order : false}
                sx={{ position: 'relative', width: replayColWidths.sequence }}
              >
                <TableSortLabel
                  active={orderBy === 'sequence'}
                  direction={orderBy === 'sequence' ? order : 'asc'}
                  onClick={() => handleSort('sequence')}
                >
                  #
                </TableSortLabel>
                {resizeHandle('sequence')}
              </TableCell>
              <TableCell
                sortDirection={orderBy === 'timestamp' ? order : false}
                sx={{ position: 'relative', width: replayColWidths.timestamp }}
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
                sx={{ position: 'relative', width: replayColWidths.direction }}
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
                align="right"
                sortDirection={orderBy === 'pnl' ? order : false}
                sx={{ position: 'relative', width: replayColWidths.pnl }}
              >
                <TableSortLabel
                  active={orderBy === 'pnl'}
                  direction={orderBy === 'pnl' ? order : 'asc'}
                  onClick={() => handleSort('pnl')}
                >
                  PnL
                </TableSortLabel>
                {resizeHandle('pnl')}
              </TableCell>
              <TableCell
                sortDirection={orderBy === 'execution_method' ? order : false}
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
              const checked = selectedRowIds.has(row.id);
              return (
                <TableRow
                  key={row.id}
                  hover
                  onClick={() => onRowSelect(row)}
                  selected={selected}
                  sx={{ cursor: 'pointer' }}
                >
                  <TableCell padding="checkbox">
                    <Checkbox
                      size="small"
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
                    {row.sequence}
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
                    {row.direction.toUpperCase()}
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
                    {row.price ? `¥${parseFloat(row.price).toFixed(3)}` : '-'}
                  </TableCell>
                  <TableCell
                    align="right"
                    sx={{
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {row.pnl ? `¥${parseFloat(row.pnl).toFixed(3)}` : '-'}
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
          setRowsPerPage(parseInt(e.target.value, 10));
          setPage(0);
        }}
        rowsPerPageOptions={[10, 25, 50, 100]}
      />
    </Box>
  );
};

export default TaskReplayPanel;
