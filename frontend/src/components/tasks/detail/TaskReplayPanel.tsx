import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Alert,
  Box,
  CircularProgress,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';
import {
  LineSeries,
  createChart,
  createSeriesMarkers,
  type IChartApi,
  type ISeriesApi,
  type ISeriesMarkersPluginApi,
  type LineData,
  type Time,
  type UTCTimestamp,
} from 'lightweight-charts';
import { TradingService } from '../../../api/generated/services/TradingService';
import { getAuthToken } from '../../../api/client';
import { TaskType } from '../../../types/common';
import { handleAuthErrorStatus } from '../../../utils/authEvents';

type TickPoint = LineData<Time>;

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
}

const toUtcTimestamp = (iso: string): UTCTimestamp =>
  Math.floor(new Date(iso).getTime() / 1000) as UTCTimestamp;

const toRfc3339Seconds = (value: string): string => {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toISOString().replace(/\.\d{3}Z$/, 'Z');
};

const fetchTicks = async (
  instrument: string,
  startTime?: string,
  endTime?: string
): Promise<Record<string, unknown>> => {
  const params = new URLSearchParams();
  params.set('instrument', instrument);
  params.set('count', '20000');
  if (startTime) params.set('from_time', toRfc3339Seconds(startTime));
  if (endTime) params.set('to_time', toRfc3339Seconds(endTime));

  const response = await fetch(`/api/market/ticks/?${params.toString()}`, {
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
    context: 'task_replay_ticks',
  });

  const body = (await response.json().catch(() => ({}))) as Record<string, unknown>;
  if (!response.ok) {
    const errorMessage =
      typeof body.error === 'string'
        ? body.error
        : typeof body.detail === 'string'
          ? body.detail
          : `Failed to load ticks (HTTP ${response.status})`;
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
}) => {
  const chartContainerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<'Line', Time> | null>(null);
  const markersRef = useRef<ISeriesMarkersPluginApi<Time> | null>(null);
  const tradesRef = useRef<ReplayTrade[]>([]);
  const [ticks, setTicks] = useState<TickPoint[]>([]);
  const [trades, setTrades] = useState<ReplayTrade[]>([]);
  const [selectedTradeId, setSelectedTradeId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const hasTickData = useMemo(() => ticks.length > 0, [ticks]);

  const fetchReplayData = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);

      const tickResponse = await fetchTicks(instrument, startTime, endTime);
      const rawTicks = Array.isArray(tickResponse?.ticks)
        ? tickResponse.ticks
        : [];
      const tickBySecond = new Map<number, number>();
      rawTicks
        .map((t: Record<string, unknown>) => {
          const timestamp = String(t.timestamp || '');
          const mid = Number(t.mid);
          if (!timestamp || Number.isNaN(mid)) {
            return null;
          }
          return {
            time: toUtcTimestamp(timestamp),
            value: mid,
          } as TickPoint;
        })
        .filter((v: TickPoint | null): v is TickPoint => v !== null)
        .forEach((p) => tickBySecond.set(Number(p.time), p.value));

      const tickPoints: TickPoint[] = Array.from(tickBySecond.entries())
        .sort((a, b) => a[0] - b[0])
        .map(([time, value]) => ({ time: time as UTCTimestamp, value }));
      setTicks(tickPoints);

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
          const direction = String(t.direction || '').toLowerCase();
          if (!timestamp || (direction !== 'buy' && direction !== 'sell')) {
            return null;
          }
          return {
            id: `${timestamp}-${idx}`,
            sequence: idx + 1,
            timestamp,
            timeSec: toUtcTimestamp(timestamp),
            instrument: String(t.instrument || instrument),
            direction: direction as 'buy' | 'sell',
            units: String(t.units ?? ''),
            price: String(t.price ?? ''),
            execution_method: String(t.execution_method || ''),
            layer_index:
              t.layer_index === null || t.layer_index === undefined
                ? null
                : Number(t.layer_index),
            pnl:
              t.pnl === null || t.pnl === undefined ? undefined : String(t.pnl),
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
  }, [instrument, startTime, endTime, taskType, taskId]);

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
    if (!chartContainerRef.current || chartRef.current) return;
    const container = chartContainerRef.current;
    const chart = createChart(container, {
      height: 420,
      layout: {
        background: { color: '#0b1220' },
        textColor: '#dbe1ee',
      },
      grid: {
        vertLines: { color: '#1f2937' },
        horzLines: { color: '#1f2937' },
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
      rightPriceScale: { borderColor: '#334155' },
      timeScale: { borderColor: '#334155', timeVisible: true, secondsVisible: false },
    });
    const series = chart.addSeries(LineSeries, {
      color: '#60a5fa',
      lineWidth: 2,
      crosshairMarkerVisible: false,
    });
    const markers = createSeriesMarkers(series, []);

    chartRef.current = chart;
    seriesRef.current = series;
    markersRef.current = markers;

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
  }, []);

  useEffect(() => {
    if (!seriesRef.current || !markersRef.current) return;
    seriesRef.current.setData(ticks);

    const markerRows = trades.map((t) => {
      const selected = t.id === selectedTradeId;
      return {
        time: t.timeSec,
        position: t.direction === 'buy' ? 'belowBar' : 'aboveBar',
        shape: t.direction === 'buy' ? 'arrowUp' : 'arrowDown',
        color: selected ? '#f59e0b' : t.direction === 'buy' ? '#22c55e' : '#ef4444',
        text: `L${t.layer_index ?? '-'} ${t.direction.toUpperCase()}`,
      };
    });

    const layerChangeMarkers = trades
      .filter((t, idx, arr) => idx > 0 && arr[idx - 1].layer_index !== t.layer_index)
      .map((t) => ({
        time: t.timeSec,
        position: 'inBar' as const,
        shape: 'square' as const,
        color: '#60a5fa',
        text: `Layer -> ${t.layer_index ?? '-'}`,
      }));

    markersRef.current.setMarkers([...markerRows, ...layerChangeMarkers]);
    if (ticks.length > 0) {
      chartRef.current?.timeScale().fitContent();
    }
  }, [ticks, trades, selectedTradeId]);

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
        <Typography variant="h6">Tick Replay</Typography>
        <Typography variant="caption" color="text.secondary">
          {hasTickData ? `${ticks.length} ticks` : 'No ticks in selected range'}
        </Typography>
      </Stack>

      <Typography variant="caption" color="text.secondary">
        Mouse wheel / pinch to zoom. Tick(mid) series with trade/layer markers.
      </Typography>

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
