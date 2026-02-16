import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
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
  TableRow,
  Typography,
} from '@mui/material';
import type { SelectChangeEvent } from '@mui/material/Select';
import {
  TickMarkType,
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
import { TradingService } from '../../../api/generated/services/TradingService';
import { getAuthToken } from '../../../api/client';
import { useSupportedGranularities } from '../../../hooks/useMarketConfig';
import { TaskType } from '../../../types/common';
import { handleAuthErrorStatus } from '../../../utils/authEvents';

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

const FALLBACK_GRANULARITIES = [
  { value: 'M1', label: '1 Minute' },
  { value: 'M5', label: '5 Minutes' },
  { value: 'M15', label: '15 Minutes' },
  { value: 'M30', label: '30 Minutes' },
  { value: 'H1', label: '1 Hour' },
  { value: 'H4', label: '4 Hours' },
  { value: 'D', label: 'Daily' },
];

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

const toDate = (time: Time): Date => {
  if (typeof time === 'number') return new Date(time * 1000);
  if (typeof time === 'string') return new Date(time);
  return new Date(Date.UTC(time.year, time.month - 1, time.day));
};

const normalizeAxisLabel = (label: string): string =>
  label.replace(/,\s*/g, ' ').replace(/\s+/g, ' ').trim();

const tickMarkFormatterWithRange =
  (visibleRangeSpanSecRef: React.MutableRefObject<number | null>) =>
  (time: Time, tickMarkType: TickMarkType, locale: string): string => {
  const date = toDate(time);
  if (Number.isNaN(date.getTime())) return '';
  const spanSec = visibleRangeSpanSecRef.current ?? 0;
  const spanDays = spanSec / 86400;

  // Long range: date only.
  if (spanDays >= 45) {
    return normalizeAxisLabel(
      new Intl.DateTimeFormat(locale, {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
      }).format(date)
    );
  }

  // Medium range: date + time mixed formatting.
  if (spanDays >= 2) {
    if (tickMarkType === TickMarkType.Year || tickMarkType === TickMarkType.Month) {
      return normalizeAxisLabel(
        new Intl.DateTimeFormat(locale, {
          year: 'numeric',
          month: '2-digit',
          day: '2-digit',
        }).format(date)
      );
    }
    return normalizeAxisLabel(
      new Intl.DateTimeFormat(locale, {
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        hour12: false,
      }).format(date)
    );
  }

  // Short range: time only.
  if (tickMarkType === TickMarkType.TimeWithSeconds) {
    return normalizeAxisLabel(
      new Intl.DateTimeFormat(locale, {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false,
      }).format(date)
    );
  }
  return normalizeAxisLabel(
    new Intl.DateTimeFormat(locale, {
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    }).format(date)
  );
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
  if (!Number.isFinite(fromMs) || !Number.isFinite(toMs) || toMs <= fromMs) return 'H1';

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
      return token ? { Authorization: `Bearer ${token}` } : {};
    })(),
  });

  handleAuthErrorStatus(response.status, {
    source: 'http',
    status: response.status,
    context: 'task_replay_candles',
  });

  const body = (await response.json().catch(() => ({}))) as Record<string, unknown>;
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
  const chartContainerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<'Candlestick', Time> | null>(null);
  const markersRef = useRef<ISeriesMarkersPluginApi<Time> | null>(null);
  const tradesRef = useRef<ReplayTrade[]>([]);
  const visibleRangeSpanSecRef = useRef<number | null>(null);

  const [candles, setCandles] = useState<CandlePoint[]>([]);
  const [trades, setTrades] = useState<ReplayTrade[]>([]);
  const [selectedTradeId, setSelectedTradeId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { granularities } = useSupportedGranularities();

  const granularityOptions = useMemo(
    () => (granularities.length > 0 ? granularities : FALLBACK_GRANULARITIES),
    [granularities]
  );

  const recommendedGranularity = useMemo(() => {
    const availableValues = granularityOptions
      .map((g) => g.value)
      .filter((v) => !!GRANULARITY_MINUTES[v]);
    return recommendGranularity(startTime, endTime, availableValues);
  }, [granularityOptions, startTime, endTime]);

  const [granularity, setGranularity] = useState<string>('H1');
  const pnlCurrency = instrument?.includes('_') ? instrument.split('_')[1] : 'N/A';

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

  const fetchReplayData = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);

      const candleResponse = await fetchCandles(instrument, granularity, startTime, endTime);
      const rawCandles = Array.isArray(candleResponse?.candles) ? candleResponse.candles : [];
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

      const candlePoints: CandlePoint[] = Array.from(candleByTime.values()).sort(
        (a, b) => Number(a.time) - Number(b.time)
      );
      setCandles(candlePoints);

      const tradeResponse =
        taskType === TaskType.BACKTEST
          ? await TradingService.tradingTasksBacktestTradesList(String(taskId))
          : await TradingService.tradingTasksTradingTradesList(String(taskId));

      const rawTrades = Array.isArray(tradeResponse?.results)
        ? tradeResponse.results
        : Array.isArray(tradeResponse)
          ? tradeResponse
          : [];

      const tradeRows: ReplayTrade[] = rawTrades
        .map((t: Record<string, unknown>, idx: number) => {
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
            layer_index:
              t.layer_index === null || t.layer_index === undefined ? null : Number(t.layer_index),
            pnl: t.pnl === null || t.pnl === undefined ? undefined : String(t.pnl),
          };
        })
        .filter((v: ReplayTrade | null): v is ReplayTrade => v !== null)
        .sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());

      setTrades(tradeRows);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load replay data');
    } finally {
      setIsLoading(false);
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

  useEffect(() => {
    if (isLoading) return;
    if (!chartContainerRef.current || chartRef.current) return;

    const container = chartContainerRef.current;
    const chart = createChart(container, {
      height: 420,
      layout: {
        background: { color: '#ffffff' },
        textColor: '#334155',
      },
      grid: {
        vertLines: { color: '#e2e8f0' },
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
        tickMarkFormatter: tickMarkFormatterWithRange(visibleRangeSpanSecRef),
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

    chart.timeScale().subscribeVisibleTimeRangeChange((range) => {
      if (!range) return;
      const from = Number(range.from);
      const to = Number(range.to);
      if (Number.isFinite(from) && Number.isFinite(to) && to > from) {
        visibleRangeSpanSecRef.current = to - from;
      }
    });

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

    return () => {
      observer.disconnect();
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
      markersRef.current = null;
    };
  }, [isLoading]);

  useEffect(() => {
    if (!seriesRef.current || !markersRef.current) return;

    seriesRef.current.setData(candles);

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
        position: t.direction === 'buy' ? 'belowBar' : 'aboveBar',
        shape: t.direction === 'buy' ? 'arrowUp' : 'arrowDown',
        color: selected ? '#f59e0b' : t.direction === 'buy' ? '#16a34a' : '#ef4444',
        text: `${actionLabel} ${sideLabel}${lotLabel}`,
      };
    });

    markersRef.current.setMarkers(tradeMarkers);

    if (candles.length > 0) {
      chartRef.current?.timeScale().fitContent();
    }
  }, [candles, trades, selectedTradeId]);

  const handleGranularityChange = (e: SelectChangeEvent) => {
    setGranularity(String(e.target.value));
  };

  const onRowSelect = (row: ReplayTrade) => {
    setSelectedTradeId(row.id);
    const center = Number(row.timeSec);
    chartRef.current?.timeScale().setVisibleRange({
      from: (center - 1800) as Time,
      to: (center + 1800) as Time,
    });
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
    <Box sx={{ p: 2 }}>
      <Stack direction="row" spacing={2} sx={{ mb: 1 }} alignItems="center">
        <Typography variant="h6">Candle Replay</Typography>
        <FormControl size="small" sx={{ minWidth: 200 }}>
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
        <Typography variant="caption" color="text.secondary">
          Auto recommendation: {recommendedGranularity}
        </Typography>
      </Stack>

      <Typography variant="caption" color="text.secondary">
        Candles are fetched from OANDA (default account). Trade markers show LONG/SHORT and lot size.
      </Typography>

      <Box sx={{ mt: 2, mb: 2 }}>
        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
          <Paper variant="outlined" sx={{ p: 1.5, minWidth: 180 }}>
            <Typography variant="caption" color="text.secondary">
              Realized PnL ({pnlCurrency})
            </Typography>
            <Typography
              variant="h6"
              color={replaySummary.realizedPnl >= 0 ? 'success.main' : 'error.main'}
            >
              {replaySummary.realizedPnl >= 0 ? '+' : ''}
              {replaySummary.realizedPnl.toFixed(2)} {pnlCurrency}
            </Typography>
          </Paper>
          <Paper variant="outlined" sx={{ p: 1.5, minWidth: 180 }}>
            <Typography variant="caption" color="text.secondary">
              Unrealized PnL ({pnlCurrency})
            </Typography>
            <Typography
              variant="h6"
              color={replaySummary.unrealizedPnl >= 0 ? 'success.main' : 'error.main'}
            >
              {replaySummary.unrealizedPnl >= 0 ? '+' : ''}
              {replaySummary.unrealizedPnl.toFixed(2)} {pnlCurrency}
            </Typography>
          </Paper>
          <Paper variant="outlined" sx={{ p: 1.5, minWidth: 180 }}>
            <Typography variant="caption" color="text.secondary">
              Total Trades (count)
            </Typography>
            <Typography variant="h6">{replaySummary.totalTrades} trades</Typography>
          </Paper>
        </Stack>
      </Box>

      <Paper variant="outlined" sx={{ mt: 1, mb: 2 }}>
        <Box ref={chartContainerRef} sx={{ width: '100%', minHeight: 420 }} />
      </Paper>

      <Typography variant="subtitle1" gutterBottom>
        Layer Trade Timeline
      </Typography>

      <TableContainer component={Paper} variant="outlined" sx={{ maxHeight: 320 }}>
        <Table stickyHeader size="small">
          <TableHead>
            <TableRow>
              <TableCell>#</TableCell>
              <TableCell>Time</TableCell>
              <TableCell>Side</TableCell>
              <TableCell>Layer</TableCell>
              <TableCell align="right">Units</TableCell>
              <TableCell align="right">Price</TableCell>
              <TableCell align="right">PnL</TableCell>
              <TableCell>Event</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {trades.map((row) => {
              const selected = row.id === selectedTradeId;
              return (
                <TableRow
                  key={row.id}
                  hover
                  onClick={() => onRowSelect(row)}
                  selected={selected}
                  sx={{ cursor: 'pointer' }}
                >
                  <TableCell>{row.sequence}</TableCell>
                  <TableCell>{new Date(row.timestamp).toLocaleString()}</TableCell>
                  <TableCell>{row.direction.toUpperCase()}</TableCell>
                  <TableCell>{row.layer_index ?? '-'}</TableCell>
                  <TableCell align="right">{row.units}</TableCell>
                  <TableCell align="right">{row.price}</TableCell>
                  <TableCell align="right">{row.pnl ?? '-'}</TableCell>
                  <TableCell>{row.execution_method || '-'}</TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </TableContainer>
    </Box>
  );
};

export default TaskReplayPanel;
