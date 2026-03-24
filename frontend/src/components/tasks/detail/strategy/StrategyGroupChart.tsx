import { useEffect, useRef } from 'react';
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
import { Alert, Box, CircularProgress } from '@mui/material';
import { useTheme } from '@mui/material/styles';
import { useTranslation } from 'react-i18next';
import { useWindowedCandles } from '../../../../hooks/useWindowedCandles';
import { getCandleColors } from '../../../../utils/candleColors';
import type { DisplayCycleStep } from '../../../../types/strategyVisualization';
import { buildCycleMarkers } from './buildCycleMarkers';

/* ------------------------------------------------------------------ */
/*  Chart component                                                    */
/* ------------------------------------------------------------------ */

export interface StrategyGroupChartProps {
  instrument: string;
  startTime: string;
  endTime: string | null;
  steps: DisplayCycleStep[];
  height?: number;
}

const GRANULARITY = 'M5';

export function StrategyGroupChart({
  instrument,
  startTime,
  endTime,
  steps,
  height = 300,
}: StrategyGroupChartProps) {
  const theme = useTheme();
  const { t } = useTranslation(['common']);
  const isDark = theme.palette.mode === 'dark';

  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<'Candlestick', Time> | null>(null);
  const markersRef = useRef<ISeriesMarkersPluginApi<Time> | null>(null);

  const effectiveEndTime = endTime ?? new Date().toISOString();

  const {
    candles,
    isInitialLoading,
    error: candleError,
  } = useWindowedCandles({
    instrument,
    granularity: GRANULARITY,
    startTime,
    endTime: effectiveEndTime,
  });

  /* ---- create / destroy chart ---- */
  useEffect(() => {
    if (!containerRef.current || candles.length === 0) return;
    if (chartRef.current) return; // already created

    const container = containerRef.current;
    const chart = createChart(container, {
      height,
      layout: {
        background: { color: isDark ? '#131722' : '#ffffff' },
        textColor: isDark ? '#ffffff' : '#334155',
      },
      grid: {
        vertLines: { visible: false },
        horzLines: { color: isDark ? '#2a2e39' : '#e2e8f0' },
      },
      rightPriceScale: { borderColor: isDark ? '#2a2e39' : '#cbd5e1' },
      timeScale: {
        borderColor: isDark ? '#2a2e39' : '#cbd5e1',
        timeVisible: true,
        secondsVisible: false,
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

    chartRef.current = chart;
    seriesRef.current = series;

    const observer = new ResizeObserver(() => {
      const w = container.clientWidth;
      if (w > 0) chart.applyOptions({ width: w });
    });
    observer.observe(container);
    chart.applyOptions({ width: container.clientWidth });

    return () => {
      observer.disconnect();
      chartRef.current = null;
      seriesRef.current = null;
      markersRef.current = null;
      requestAnimationFrame(() => {
        try {
          chart.remove();
        } catch {
          /* already disposed */
        }
      });
    };
  }, [candles.length, height, isDark]);

  /* ---- sync candle data + markers ---- */
  useEffect(() => {
    const series = seriesRef.current;
    const chart = chartRef.current;
    if (!series || !chart || candles.length === 0) return;

    const candleData = candles.map((c) => ({
      time: c.time as UTCTimestamp,
      open: c.open,
      high: c.high,
      low: c.low,
      close: c.close,
    }));

    series.setData(candleData);

    const candleTimes = candles.map((c) => c.time);
    const markers = buildCycleMarkers(steps, candleTimes);

    if (markersRef.current) {
      markersRef.current.setMarkers(markers);
    } else {
      markersRef.current = createSeriesMarkers(series, markers);
    }

    chart.timeScale().fitContent();
  }, [candles, steps]);

  /* ---- render ---- */
  if (candleError) {
    return (
      <Alert severity="warning" sx={{ my: 1 }}>
        {t('common:strategyVisualization.chartLoadError')}
      </Alert>
    );
  }

  if (isInitialLoading) {
    return (
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          height,
        }}
      >
        <CircularProgress size={28} />
      </Box>
    );
  }

  return (
    <Box ref={containerRef} sx={{ width: '100%', height, minHeight: height }} />
  );
}

export default StrategyGroupChart;
