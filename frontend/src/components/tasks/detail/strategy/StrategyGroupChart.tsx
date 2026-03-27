import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Box,
  CircularProgress,
  Alert,
  IconButton,
  ToggleButton,
  ToggleButtonGroup,
  Tooltip,
} from '@mui/material';
import ZoomOutMapIcon from '@mui/icons-material/ZoomOutMap';
import RefreshIcon from '@mui/icons-material/Refresh';
import {
  CandlestickSeries,
  createChart,
  createSeriesMarkers,
  type IChartApi,
  type ISeriesApi,
  type CandlestickData,
  type Time,
} from 'lightweight-charts';
import { useTheme } from '@mui/material/styles';
import { useWindowedCandles } from '../../../../hooks/useWindowedCandles';
import { getCandleColors } from '../../../../utils/candleColors';
import {
  AdaptiveTimeScale,
  createSuppressedTickMarkFormatter,
  createTooltipTimeFormatter,
} from '../../../../utils/adaptiveTimeScalePlugin';
import type { CycleTrade } from '../../../../types/strategyVisualization';
import type { TaskType } from '../../../../types/common';
import { buildCycleMarkers } from './buildCycleMarkers';
import { useMetricsOverlay } from '../MetricsOverlayChart';

interface StrategyGroupChartProps {
  instrument: string;
  startTime: string;
  endTime: string | null;
  trades: CycleTrade[];
  height?: number;
  taskId?: string | number;
  taskType?: TaskType;
  executionRunId?: string;
}

const GRANULARITY_OPTIONS = ['M1', 'M5', 'M15', 'H1', 'H4', 'D'] as const;

function autoGranularity(startTime: string, endTime: string | null): string {
  const startSec = Math.floor(new Date(startTime).getTime() / 1000);
  const endSec = endTime
    ? Math.floor(new Date(endTime).getTime() / 1000)
    : startSec + 3600;
  const span = Math.max(60, endSec - startSec);
  if (span > 30 * 86400) return 'D';
  if (span > 7 * 86400) return 'H4';
  if (span > 2 * 86400) return 'H1';
  if (span > 12 * 3600) return 'M15';
  if (span > 4 * 3600) return 'M5';
  return 'M1';
}

export function StrategyGroupChart({
  instrument,
  startTime,
  endTime,
  trades,
  height = 300,
  taskId,
  taskType,
  executionRunId,
}: StrategyGroupChartProps) {
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const markersRef = useRef<ReturnType<
    typeof createSeriesMarkers<Time>
  > | null>(null);
  const observerRef = useRef<ResizeObserver | null>(null);
  // Expose chart instance as state so the metrics overlay hook can react to it
  const [chartInstance, setChartInstance] = useState<IChartApi | null>(null);

  const defaultGranularity = useMemo(
    () => (startTime ? autoGranularity(startTime, endTime) : 'M1'),
    [startTime, endTime]
  );
  const [granularity, setGranularity] = useState(defaultGranularity);

  // Reset granularity when cycle changes
  useEffect(() => {
    setGranularity(defaultGranularity);
  }, [defaultGranularity]);

  // Calculate edgeCount to cover the full cycle range so the initial load
  // fetches candles from start to end instead of only the most recent portion.
  const fullRangeEdgeCount = useMemo(() => {
    if (!startTime) return 500;
    const GRANULARITY_SECONDS: Record<string, number> = {
      M1: 60,
      M5: 300,
      M15: 900,
      H1: 3600,
      H4: 14400,
      D: 86400,
    };
    const granSec = GRANULARITY_SECONDS[granularity] ?? 60;
    const startSec = Math.floor(new Date(startTime).getTime() / 1000);
    const endSec = endTime
      ? Math.floor(new Date(endTime).getTime() / 1000)
      : Math.floor(Date.now() / 1000);
    const span = Math.max(60, endSec - startSec);
    // Add 10% padding on each side
    return Math.ceil((span / granSec) * 1.2) + 10;
  }, [startTime, endTime, granularity]);

  const { candles, isInitialLoading, error, replaceWithCountWindow } =
    useWindowedCandles({
      instrument,
      granularity,
      startTime,
      endTime: endTime ?? undefined,
      initialCount: fullRangeEdgeCount,
      edgeCount: fullRangeEdgeCount,
    });

  const candleTimes = useMemo(() => candles.map((c) => c.time), [candles]);
  const markers = useMemo(
    () => buildCycleMarkers(trades, candleTimes),
    [trades, candleTimes]
  );

  const paddedRange = useMemo(() => {
    if (!startTime || candles.length === 0) return null;
    const startSec = Math.floor(new Date(startTime).getTime() / 1000);
    const endSec = endTime
      ? Math.floor(new Date(endTime).getTime() / 1000)
      : candles[candles.length - 1].time;
    const span = endSec - startSec;
    const pad = Math.max(60, Math.floor(span * 0.1));
    return { from: (startSec - pad) as Time, to: (endSec + pad) as Time };
  }, [startTime, endTime, candles]);

  const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;

  // Destroy chart when key inputs change so it's fully recreated
  const destroyChart = useCallback(() => {
    observerRef.current?.disconnect();
    observerRef.current = null;
    chartRef.current?.remove();
    chartRef.current = null;
    seriesRef.current = null;
    markersRef.current = null;
    setChartInstance(null);
  }, []);

  // Recreate chart when granularity or theme changes
  useEffect(() => {
    destroyChart();
  }, [granularity, isDark, destroyChart]);

  useEffect(() => {
    return destroyChart;
  }, [destroyChart]);

  useEffect(() => {
    if (!containerRef.current || candles.length === 0) return;

    if (!chartRef.current) {
      const container = containerRef.current;
      const { upColor, downColor } = getCandleColors();
      const chart = createChart(container, {
        height,
        width: container.clientWidth,
        layout: {
          background: { color: isDark ? '#131722' : '#ffffff' },
          textColor: isDark ? '#d1d4dc' : '#334155',
        },
        grid: {
          vertLines: { visible: false },
          horzLines: { color: isDark ? '#2a2e39' : '#e2e8f0' },
        },
        handleScroll: {
          vertTouchDrag: false,
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
        rightPriceScale: { borderColor: isDark ? '#2a2e39' : '#cbd5e1' },
      });
      const series = chart.addSeries(CandlestickSeries, {
        upColor,
        downColor,
        wickUpColor: upColor,
        wickDownColor: downColor,
        borderUpColor: upColor,
        borderDownColor: downColor,
      });
      const adaptive = new AdaptiveTimeScale(
        { timezone },
        isDark ? '#d1d4dc' : '#334155',
        isDark ? '#2a2e39' : '#e2e8f0'
      );
      series.attachPrimitive(adaptive);

      chartRef.current = chart;
      seriesRef.current = series;
      markersRef.current = createSeriesMarkers(series, []);
      setChartInstance(chart);

      const observer = new ResizeObserver(() => {
        const w = container.clientWidth;
        if (w > 0) chart.applyOptions({ width: w });
      });
      observer.observe(container);
      observerRef.current = observer;
    }

    seriesRef.current?.setData(
      candles.map(
        (c) =>
          ({
            time: c.time as Time,
            open: c.open,
            high: c.high,
            low: c.low,
            close: c.close,
          }) as CandlestickData<Time>
      )
    );
    markersRef.current?.setMarkers(markers);

    if (paddedRange && chartRef.current) {
      chartRef.current.timeScale().setVisibleRange(paddedRange);
    } else {
      chartRef.current?.timeScale().fitContent();
    }
  }, [candles, markers, height, isDark, paddedRange, timezone]);

  // Attach metrics overlay (ATR / Margin Ratio) when task context is available
  useMetricsOverlay({
    taskId: taskId ? String(taskId) : '',
    taskType: taskType ?? ('' as TaskType),
    executionRunId,
    chart: chartInstance,
    candleTimestamps: candleTimes as number[],
  });

  const handleResetZoom = useCallback(() => {
    if (paddedRange && chartRef.current) {
      chartRef.current.timeScale().setVisibleRange(paddedRange);
    } else {
      chartRef.current?.timeScale().fitContent();
    }
  }, [paddedRange]);

  const handleReload = useCallback(() => {
    destroyChart();
    void replaceWithCountWindow();
  }, [destroyChart, replaceWithCountWindow]);

  if (isInitialLoading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
        <CircularProgress size={24} />
      </Box>
    );
  }

  if (error) {
    return <Alert severity="warning">{error}</Alert>;
  }

  if (candles.length === 0) {
    return <Alert severity="info">No chart data available</Alert>;
  }

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 1 }}>
        <ToggleButtonGroup
          value={granularity}
          exclusive
          onChange={(_, v) => {
            if (v) setGranularity(v);
          }}
          size="small"
        >
          {GRANULARITY_OPTIONS.map((g) => (
            <ToggleButton
              key={g}
              value={g}
              sx={{ px: 1.5, py: 0.25, fontSize: '0.75rem' }}
            >
              {g}
            </ToggleButton>
          ))}
        </ToggleButtonGroup>
        <Tooltip title="Reset zoom">
          <IconButton onClick={handleResetZoom} size="small">
            <ZoomOutMapIcon fontSize="small" />
          </IconButton>
        </Tooltip>
        <Tooltip title="Reload candles">
          <IconButton onClick={handleReload} size="small">
            <RefreshIcon fontSize="small" />
          </IconButton>
        </Tooltip>
      </Box>
      <Box ref={containerRef} sx={{ width: '100%' }} />
    </Box>
  );
}
