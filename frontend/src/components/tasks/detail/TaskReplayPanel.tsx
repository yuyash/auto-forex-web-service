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
  FormControl,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TablePagination,
  TableRow,
  TableSortLabel,
  Typography,
} from '@mui/material';
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
  direction: 'buy' | 'sell';
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
  latestExecution,
}) => {
  const panelRootRef = useRef<HTMLDivElement | null>(null);
  const chartContainerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<'Candlestick', Time> | null>(null);
  const markersRef = useRef<ISeriesMarkersPluginApi<Time> | null>(null);
  const highlightRef = useRef<MarketClosedHighlight | null>(null);
  const adaptiveRef = useRef<AdaptiveTimeScale | null>(null);
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

  // Column resize state
  const defaultReplayWidths: Record<string, number> = {
    sequence: 50,
    timestamp: 170,
    direction: 70,
    layer_index: 60,
    units: 80,
    price: 100,
    pnl: 100,
    execution_method: 110,
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

  // Reset to first page when sort or data changes
  useEffect(() => {
    setPage(0);
  }, [orderBy, order, trades]);

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
    const unrealizedRaw =
      latestExecution?.unrealized_pnl !== undefined
        ? Number(latestExecution.unrealized_pnl)
        : 0;
    const totalTradesRaw =
      typeof latestExecution?.total_trades === 'number'
        ? latestExecution.total_trades
        : trades.length;

    return {
      realizedPnl: Number.isFinite(realizedRaw) ? realizedRaw : 0,
      unrealizedPnl: Number.isFinite(unrealizedRaw) ? unrealizedRaw : 0,
      totalTrades: totalTradesRaw,
    };
  }, [latestExecution, trades]);

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
          if (
            !timestamp ||
            parsedTime === null ||
            (direction !== 'buy' && direction !== 'sell')
          ) {
            return null;
          }
          return {
            id: `${timestamp}-${idx}`,
            sequence: idx + 1,
            timestamp,
            timeSec: parsedTime,
            instrument: String(t.instrument || instrument),
            direction: direction as 'buy' | 'sell',
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
    // Fixed chrome: browser chrome + nav bar + breadcrumb + task header + tab bar + panel padding
    const chromeHeight = 230;
    // Summary cards row
    const summaryHeight = 85;
    // Granularity selector + caption
    const controlsHeight = 60;
    // Table: header(40) + rows(37 each) + pagination(56) + subtitle(36) + spacing(24)
    const tableRowHeight = 37;
    const currentRowsPerPage = rowsPerPageRef.current;
    const currentTradesCount = tradesRef.current.length;
    const visibleRows = Math.min(
      currentRowsPerPage,
      currentTradesCount || currentRowsPerPage
    );
    const tableHeight = 40 + tableRowHeight * visibleRows + 56 + 36 + 24 + 100;
    // Chart border/margin
    const chartChrome = 28;

    const usedHeight =
      chromeHeight + summaryHeight + controlsHeight + tableHeight + chartChrome;
    const available = window.innerHeight - usedHeight;
    return Math.max(360, Math.round(available));
  }, []);

  // Recalculate chart height when rowsPerPage changes
  useEffect(() => {
    if (!chartRef.current) return;
    const newHeight = computeChartHeight();
    chartRef.current.applyOptions({ height: newHeight });
  }, [rowsPerPage, computeChartHeight]);

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

    const observer = new ResizeObserver(() => {
      const width = container.clientWidth;
      if (width > 0) {
        chart.applyOptions({ width });
      }
    });
    observer.observe(container);
    chart.applyOptions({ width: container.clientWidth });

    const handleWindowResize = () => {
      const newHeight = computeChartHeight();
      chart.applyOptions({ height: newHeight });
    };
    window.addEventListener('resize', handleWindowResize);

    return () => {
      window.removeEventListener('resize', handleWindowResize);
      observer.disconnect();
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
      markersRef.current = null;
      highlightRef.current = null;
      adaptiveRef.current = null;
    };
  }, [isLoading, candles.length, timezone, computeChartHeight]);

  // Update candle data, market gaps, and fit chart when data changes
  useEffect(() => {
    if (!seriesRef.current || !markersRef.current) return;

    seriesRef.current.setData(candles);

    const times = candles.map((c) => Number(c.time));

    if (highlightRef.current) {
      highlightRef.current.setGaps(detectMarketGaps(times));
    }

    if (candles.length > 0) {
      chartRef.current?.timeScale().fitContent();
    }
  }, [candles]);

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

      const openSide = t.direction === 'buy' ? 'LONG' : 'SHORT';
      const closeSide = t.direction === 'buy' ? 'SHORT' : 'LONG';
      const sideLabel = isClose ? closeSide : openSide;
      const actionLabel = isClose ? 'CLOSE' : 'OPEN';
      const lotLabel = lots === null ? '' : ` ${Math.round(lots)}L`;

      return {
        time: t.timeSec,
        position:
          t.direction === 'buy' ? ('belowBar' as const) : ('aboveBar' as const),
        shape:
          t.direction === 'buy' ? ('arrowUp' as const) : ('arrowDown' as const),
        color: selected
          ? '#f59e0b'
          : t.direction === 'buy'
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
    const ts = chartRef.current?.timeScale();
    if (!ts) return;

    const range = ts.getVisibleRange();
    if (range) {
      const half = (Number(range.to) - Number(range.from)) / 2;
      const center = Number(row.timeSec);
      ts.setVisibleRange({
        from: (center - half) as Time,
        to: (center + half) as Time,
      });
    }
  };

  if (isLoading) {
    return (
      <Box sx={{ p: 4, display: 'flex', justifyContent: 'center' }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="error">{error}</Alert>
      </Box>
    );
  }

  return (
    <Box ref={panelRootRef} sx={{ p: 2 }}>
      <Stack
        direction="row"
        spacing={2}
        sx={{ mb: 1 }}
        alignItems="center"
        flexWrap="wrap"
      >
        <Typography variant="h6" sx={{ whiteSpace: 'nowrap' }}>
          Candle Replay
        </Typography>
        {isRefreshing && <CircularProgress size={16} thickness={5} />}
        <FormControl size="small" sx={{ minWidth: 160 }}>
          <InputLabel id="replay-granularity-label">Granularity</InputLabel>
          <Select
            labelId="replay-granularity-label"
            value={granularity}
            label="Granularity"
            onChange={handleGranularityChange}
          >
            {granularityOptions.map((g) => (
              <MenuItem key={g.value} value={g.value}>
                {g.label}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
        <Paper variant="outlined" sx={{ p: 1, px: 2, minWidth: 140 }}>
          <Typography variant="caption" color="text.secondary">
            Realized PnL ({pnlCurrency})
          </Typography>
          <Typography
            variant="body1"
            fontWeight="bold"
            color={
              replaySummary.realizedPnl >= 0 ? 'success.main' : 'error.main'
            }
          >
            {replaySummary.realizedPnl >= 0 ? '+' : ''}
            {replaySummary.realizedPnl.toFixed(2)} {pnlCurrency}
          </Typography>
        </Paper>
        <Paper variant="outlined" sx={{ p: 1, px: 2, minWidth: 140 }}>
          <Typography variant="caption" color="text.secondary">
            Unrealized PnL ({pnlCurrency})
          </Typography>
          <Typography
            variant="body1"
            fontWeight="bold"
            color={
              replaySummary.unrealizedPnl >= 0 ? 'success.main' : 'error.main'
            }
          >
            {replaySummary.unrealizedPnl >= 0 ? '+' : ''}
            {replaySummary.unrealizedPnl.toFixed(2)} {pnlCurrency}
          </Typography>
        </Paper>
        <Paper variant="outlined" sx={{ p: 1, px: 2, minWidth: 120 }}>
          <Typography variant="caption" color="text.secondary">
            Total Trades (count)
          </Typography>
          <Typography variant="body1" fontWeight="bold">
            {replaySummary.totalTrades} trades
          </Typography>
        </Paper>
      </Stack>

      <Typography variant="caption" color="text.secondary">
        Candles are fetched from OANDA (default account). Trade markers show
        LONG/SHORT and lot size.
      </Typography>

      <Paper variant="outlined" sx={{ mt: 1, mb: 2 }}>
        <Box ref={chartContainerRef} sx={{ width: '100%', minHeight: 360 }} />
      </Paper>

      <Typography variant="subtitle1" gutterBottom>
        Layer Trade Timeline
      </Typography>

      <TableContainer component={Paper} variant="outlined">
        <Table stickyHeader size="small" sx={{ tableLayout: 'fixed' }}>
          <TableHead>
            <TableRow>
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
                  Side
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
              return (
                <TableRow
                  key={row.id}
                  hover
                  onClick={() => onRowSelect(row)}
                  selected={selected}
                  sx={{ cursor: 'pointer' }}
                >
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
