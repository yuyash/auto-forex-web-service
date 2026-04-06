/**
 * MetricsOhlcChart - OHLC candlestick chart for the metrics tab.
 *
 * Displays the instrument's price action over the task's time range
 * using lightweight-charts, matching the granularity to the data span.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Box,
  Paper,
  Typography,
  CircularProgress,
  Alert,
  ToggleButton,
  ToggleButtonGroup,
  IconButton,
  Tooltip,
} from '@mui/material';
import ZoomOutMapIcon from '@mui/icons-material/ZoomOutMap';
import RefreshIcon from '@mui/icons-material/Refresh';
import {
  CandlestickSeries,
  createChart,
  type IChartApi,
  type ISeriesApi,
  type CandlestickData,
  type Time,
} from 'lightweight-charts';
import { useTheme } from '@mui/material/styles';
import { useTranslation } from 'react-i18next';
import { useWindowedCandles } from '../../../hooks/useWindowedCandles';
import { getCandleColors } from '../../../utils/candleColors';
import {
  AdaptiveTimeScale,
  createSuppressedTickMarkFormatter,
  createTooltipTimeFormatter,
} from '../../../utils/adaptiveTimeScalePlugin';

interface MetricsOhlcChartProps {
  instrument: string;
  startTime: string;
  endTime?: string;
  height?: number;
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

export function MetricsOhlcChart({
  instrument,
  startTime,
  endTime,
  height = 300,
}: MetricsOhlcChartProps) {
  const theme = useTheme();
  const { t } = useTranslation('common');
  const isDark = theme.palette.mode === 'dark';
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const observerRef = useRef<ResizeObserver | null>(null);

  const fallbackEnd = endTime ?? new Date().toISOString();

  const defaultGranularity = useMemo(
    () => autoGranularity(startTime, fallbackEnd),
    [startTime, fallbackEnd]
  );
  const [granularity, setGranularity] = useState(defaultGranularity);

  useEffect(() => {
    setGranularity(defaultGranularity);
  }, [defaultGranularity]);

  const fullRangeEdgeCount = useMemo(() => {
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
    const endSec = Math.floor(new Date(fallbackEnd).getTime() / 1000);
    const span = Math.max(60, endSec - startSec);
    return Math.ceil((span / granSec) * 1.2) + 10;
  }, [startTime, fallbackEnd, granularity]);

  const { candles, isInitialLoading, error, replaceWithCountWindow } =
    useWindowedCandles({
      instrument,
      granularity,
      startTime,
      endTime: fallbackEnd,
      initialCount: fullRangeEdgeCount,
      edgeCount: fullRangeEdgeCount,
    });

  const paddedRange = useMemo(() => {
    if (candles.length === 0) return null;
    const startSec = Math.floor(new Date(startTime).getTime() / 1000);
    const endSec = Math.floor(new Date(fallbackEnd).getTime() / 1000);
    const span = endSec - startSec;
    const pad = Math.max(60, Math.floor(span * 0.05));
    return { from: (startSec - pad) as Time, to: (endSec + pad) as Time };
  }, [startTime, fallbackEnd, candles]);

  const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;

  const destroyChart = useCallback(() => {
    observerRef.current?.disconnect();
    observerRef.current = null;
    chartRef.current?.remove();
    chartRef.current = null;
    seriesRef.current = null;
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

    if (paddedRange && chartRef.current) {
      chartRef.current.timeScale().setVisibleRange(paddedRange);
    } else {
      chartRef.current?.timeScale().fitContent();
    }
  }, [candles, height, isDark, paddedRange, timezone]);

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

  const displayInstrument = instrument.replace('_', '/');

  if (isInitialLoading) {
    return (
      <Paper variant="outlined" sx={{ p: 1.5 }}>
        <Typography variant="subtitle2" sx={{ mb: 1 }}>
          {displayInstrument}
        </Typography>
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
          <CircularProgress size={24} />
        </Box>
      </Paper>
    );
  }

  if (error) {
    return (
      <Paper variant="outlined" sx={{ p: 1.5 }}>
        <Typography variant="subtitle2" sx={{ mb: 1 }}>
          {displayInstrument}
        </Typography>
        <Alert severity="warning">{error}</Alert>
      </Paper>
    );
  }

  if (candles.length === 0) {
    return (
      <Paper variant="outlined" sx={{ p: 1.5 }}>
        <Typography variant="subtitle2" sx={{ mb: 1 }}>
          {displayInstrument}
        </Typography>
        <Alert severity="info">{t('metrics.noData')}</Alert>
      </Paper>
    );
  }

  return (
    <Paper variant="outlined" sx={{ p: 1.5 }}>
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          mb: 0.5,
        }}
      >
        <Typography variant="subtitle2">{displayInstrument}</Typography>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
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
                sx={{ px: 1, py: 0.15, fontSize: '0.7rem' }}
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
          <Tooltip title="Reload">
            <IconButton onClick={handleReload} size="small">
              <RefreshIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </Box>
      </Box>
      <Box ref={containerRef} sx={{ width: '100%' }} />
    </Paper>
  );
}
