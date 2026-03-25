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

  const { candles, isInitialLoading, error } = useWindowedCandles({
    instrument,
    granularity: 'M1',
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

  useEffect(() => {
    if (!containerRef.current || candles.length === 0) return;

    if (!chartRef.current) {
      const { upColor, downColor } = getCandleColors();
      const chart = createChart(containerRef.current, {
        height,
        layout: {
          background: { color: isDark ? '#131722' : '#ffffff' },
          textColor: isDark ? '#d1d4dc' : '#334155',
        },
        grid: {
          vertLines: { color: isDark ? '#2a2e39' : '#e2e8f0' },
          horzLines: { color: isDark ? '#2a2e39' : '#e2e8f0' },
        },
        timeScale: { timeVisible: true, secondsVisible: false },
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
      chartRef.current = chart;
      seriesRef.current = series;
      markersRef.current = createSeriesMarkers(series, []);
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
    chartRef.current?.timeScale().fitContent();
  }, [candles, markers, height, isDark]);

  useEffect(() => {
    return () => {
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
