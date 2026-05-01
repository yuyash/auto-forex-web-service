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
import VisibilityIcon from '@mui/icons-material/Visibility';
import VisibilityOffIcon from '@mui/icons-material/VisibilityOff';
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
  lastTickTimestamp?: string | null;
  selectedTradeIds?: Set<string>;
  onMarkerClick?: (tradeId: string) => void;
}

const GRANULARITY_OPTIONS = ['M1', 'M5', 'M15', 'H1', 'H4', 'D'] as const;

function autoGranularity(startTime: string, endTime: string): string {
  const startSec = Math.floor(new Date(startTime).getTime() / 1000);
  const endSec = Math.floor(new Date(endTime).getTime() / 1000);
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
  lastTickTimestamp,
  selectedTradeIds,
  onMarkerClick,
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
  const [chartInstance, setChartInstance] = useState<IChartApi | null>(null);

  // Marker visibility toggle (default: visible)
  const [markersVisible, setMarkersVisible] = useState(true);

  // Keep a ref to the built markers for click-to-trade mapping
  const builtMarkersRef = useRef<ReturnType<typeof buildCycleMarkers>>([]);

  const fallbackEnd = lastTickTimestamp ?? new Date().toISOString();
  const effectiveEndTime = endTime ?? fallbackEnd;

  const defaultGranularity = useMemo(
    () => (startTime ? autoGranularity(startTime, effectiveEndTime) : 'M1'),
    [startTime, effectiveEndTime]
  );
  const [granularity, setGranularity] = useState(defaultGranularity);

  useEffect(() => {
    setGranularity(defaultGranularity);
  }, [defaultGranularity]);

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
    const endSec = Math.floor(new Date(effectiveEndTime).getTime() / 1000);
    const span = Math.max(60, endSec - startSec);
    return Math.ceil((span / granSec) * 1.2) + 10;
  }, [startTime, effectiveEndTime, granularity]);

  const { candles, isInitialLoading, error, replaceWithCountWindow } =
    useWindowedCandles({
      instrument,
      granularity,
      startTime,
      endTime: effectiveEndTime,
      initialCount: fullRangeEdgeCount,
      edgeCount: fullRangeEdgeCount,
    });

  const candleTimes = useMemo(() => candles.map((c) => c.time), [candles]);
  const markers = useMemo(() => {
    const built = buildCycleMarkers(
      trades,
      candleTimes as number[],
      selectedTradeIds,
      markersVisible
    );
    builtMarkersRef.current = built;
    return built;
  }, [trades, candleTimes, selectedTradeIds, markersVisible]);

  const paddedRange = useMemo(() => {
    if (!startTime || candles.length === 0) return null;
    const startSec = Math.floor(new Date(startTime).getTime() / 1000);
    const endSec = Math.floor(new Date(effectiveEndTime).getTime() / 1000);
    const span = endSec - startSec;
    const pad = Math.max(60, Math.floor(span * 0.1));
    return { from: (startSec - pad) as Time, to: (endSec + pad) as Time };
  }, [startTime, effectiveEndTime, candles]);

  const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;

  const destroyChart = useCallback(() => {
    observerRef.current?.disconnect();
    observerRef.current = null;
    chartRef.current?.remove();
    chartRef.current = null;
    seriesRef.current = null;
    markersRef.current = null;
    setChartInstance(null);
  }, []);

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
        handleScroll: { vertTouchDrag: false },
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

      // Handle marker click → find closest trade
      if (onMarkerClick) {
        chart.subscribeClick((param) => {
          if (!param.time || !param.point) return;
          const clickedTime = Number(param.time);
          // Find the marker closest to the clicked time
          const built = builtMarkersRef.current;
          let closest: (typeof built)[number] | null = null;
          let closestDist = Infinity;
          for (const m of built) {
            const dist = Math.abs(Number(m.time) - clickedTime);
            if (dist < closestDist) {
              closestDist = dist;
              closest = m;
            }
          }
          // Only trigger if click is reasonably close to a marker
          if (closest?.tradeId && closestDist < 120) {
            onMarkerClick(closest.tradeId);
          }
        });
      }

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
  }, [candles, markers, height, isDark, paddedRange, timezone, onMarkerClick]);

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
        <Tooltip title={markersVisible ? 'Hide markers' : 'Show markers'}>
          <IconButton
            onClick={() => setMarkersVisible((v) => !v)}
            size="small"
            color={markersVisible ? 'primary' : 'default'}
          >
            {markersVisible ? (
              <VisibilityIcon fontSize="small" />
            ) : (
              <VisibilityOffIcon fontSize="small" />
            )}
          </IconButton>
        </Tooltip>
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
