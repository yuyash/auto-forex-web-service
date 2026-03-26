import { useEffect, useRef, useMemo } from 'react';
import { Box, CircularProgress, Alert } from '@mui/material';
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
import { buildCycleMarkers } from './buildCycleMarkers';

interface StrategyGroupChartProps {
  instrument: string;
  startTime: string;
  endTime: string | null;
  trades: CycleTrade[];
  height?: number;
}

export function StrategyGroupChart({
  instrument,
  startTime,
  endTime,
  trades,
  height = 300,
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

  const granularity = useMemo(() => {
    if (!startTime) return 'M1';
    const startSec = Math.floor(new Date(startTime).getTime() / 1000);
    const endSec = endTime
      ? Math.floor(new Date(endTime).getTime() / 1000)
      : startSec + 3600;
    const spanSec = Math.max(60, endSec - startSec);
    if (spanSec > 30 * 86400) return 'D';
    if (spanSec > 7 * 86400) return 'H4';
    if (spanSec > 2 * 86400) return 'H1';
    if (spanSec > 12 * 3600) return 'M15';
    if (spanSec > 4 * 3600) return 'M5';
    return 'M1';
  }, [startTime, endTime]);

  const { candles, isInitialLoading, error } = useWindowedCandles({
    instrument,
    granularity,
    startTime,
    endTime: endTime ?? undefined,
    initialCount: 500,
    edgeCount: 200,
  });

  const candleTimes = useMemo(() => candles.map((c) => c.time), [candles]);
  const markers = useMemo(
    () => buildCycleMarkers(trades, candleTimes),
    [trades, candleTimes]
  );

  // Padded visible range: cycle period + 10% on each side
  const paddedRange = useMemo(() => {
    if (!startTime || candles.length === 0) return null;
    const startSec = Math.floor(new Date(startTime).getTime() / 1000);
    const endSec = endTime
      ? Math.floor(new Date(endTime).getTime() / 1000)
      : candles[candles.length - 1].time;
    const span = endSec - startSec;
    const pad = Math.max(60, Math.floor(span * 0.1));
    return {
      from: (startSec - pad) as Time,
      to: (endSec + pad) as Time,
    };
  }, [startTime, endTime, candles]);

  const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;

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

      // Attach adaptive time scale for proper time labels
      const adaptive = new AdaptiveTimeScale(
        { timezone },
        isDark ? '#d1d4dc' : '#334155',
        isDark ? '#2a2e39' : '#e2e8f0'
      );
      series.attachPrimitive(adaptive);

      chartRef.current = chart;
      seriesRef.current = series;
      markersRef.current = createSeriesMarkers(series, []);

      // Resize observer for responsive width
      const observer = new ResizeObserver(() => {
        const w = container.clientWidth;
        if (w > 0) chart.applyOptions({ width: w });
      });
      observer.observe(container);
      observerRef.current = observer;
    }

    const series = seriesRef.current;
    if (series) {
      series.setData(
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
    }
    if (markersRef.current) {
      markersRef.current.setMarkers(markers);
    }

    // Set padded visible range instead of fitContent
    if (paddedRange && chartRef.current) {
      chartRef.current.timeScale().setVisibleRange(paddedRange);
    } else {
      chartRef.current?.timeScale().fitContent();
    }
  }, [candles, markers, height, isDark, paddedRange, timezone]);

  useEffect(() => {
    return () => {
      observerRef.current?.disconnect();
      observerRef.current = null;
      chartRef.current?.remove();
      chartRef.current = null;
      seriesRef.current = null;
      markersRef.current = null;
    };
  }, []);

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

  return <Box ref={containerRef} sx={{ width: '100%' }} />;
}
