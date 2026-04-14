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
import DragIndicatorIcon from '@mui/icons-material/DragIndicator';
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
import { SequencePositionLine } from '../../../utils/SequencePositionLine';

interface MetricsOhlcChartProps {
  instrument: string;
  startTime: string;
  endTime?: string;
  /** Fixed height for the outer Paper card (should match metric chart cards) */
  cardHeight?: number;
  /** Current tick timestamp for the sequence position line */
  currentTickTimestamp?: string | null;
  /** Current tick price for the sequence position line */
  currentTickPrice?: number | null;
}

const GRANULARITY_OPTIONS = [
  'Auto',
  'M1',
  'M5',
  'M15',
  'H1',
  'H4',
  'D',
] as const;

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
  cardHeight,
  currentTickTimestamp,
  currentTickPrice,
}: MetricsOhlcChartProps) {
  const theme = useTheme();
  const { t } = useTranslation('common');
  const isDark = theme.palette.mode === 'dark';
  const containerRef = useRef<HTMLDivElement>(null);
  const headerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const observerRef = useRef<ResizeObserver | null>(null);
  const seqLineRef = useRef<SequencePositionLine | null>(null);
  const [chartHeight, setChartHeight] = useState(200);
  const [liveEndTime, setLiveEndTime] = useState(
    () => endTime ?? new Date().toISOString()
  );

  // Compute chart canvas height to fill the card minus header and padding
  useEffect(() => {
    if (!cardHeight || !headerRef.current) return;
    const headerH = headerRef.current.offsetHeight;
    // Paper padding: p=1.5 = 12px top + 12px bottom = 24px, mb:0.5 = 4px
    const available = cardHeight - 24 - headerH - 4;
    setChartHeight(Math.max(100, available));
  }, [cardHeight]);

  useEffect(() => {
    if (endTime) {
      setLiveEndTime(endTime);
    }
  }, [endTime]);

  const fallbackEnd = endTime ?? liveEndTime;

  const resolvedAutoGranularity = useMemo(
    () => autoGranularity(startTime, fallbackEnd),
    [startTime, fallbackEnd]
  );
  const [granularity, setGranularity] = useState<string>('Auto');

  // The actual granularity used for data fetching
  const effectiveGranularity =
    granularity === 'Auto' ? resolvedAutoGranularity : granularity;

  const fullRangeEdgeCount = useMemo(() => {
    const GRANULARITY_SECONDS: Record<string, number> = {
      M1: 60,
      M5: 300,
      M15: 900,
      H1: 3600,
      H4: 14400,
      D: 86400,
    };
    const granSec = GRANULARITY_SECONDS[effectiveGranularity] ?? 60;
    const startSec = Math.floor(new Date(startTime).getTime() / 1000);
    const endSec = Math.floor(new Date(fallbackEnd).getTime() / 1000);
    const span = Math.max(60, endSec - startSec);
    return Math.ceil((span / granSec) * 1.2) + 10;
  }, [startTime, fallbackEnd, effectiveGranularity]);

  const { candles, isInitialLoading, error, replaceWithCountWindow } =
    useWindowedCandles({
      instrument,
      granularity: effectiveGranularity,
      startTime,
      endTime: fallbackEnd,
      initialCount: fullRangeEdgeCount,
      edgeCount: fullRangeEdgeCount,
    });

  const paddedRange = useMemo(() => {
    if (candles.length === 0) return null;
    const startSec = Math.floor(new Date(startTime).getTime() / 1000);
    const endSec = Math.floor(new Date(fallbackEnd).getTime() / 1000);
    const span = Math.max(60, endSec - startSec);
    const leftPad = Math.max(60, Math.floor(span * 0.05));
    const rightPad = Math.max(60, Math.floor((span + leftPad) / 3));
    return {
      from: (startSec - leftPad) as Time,
      to: (endSec + rightPad) as Time,
    };
  }, [startTime, fallbackEnd, candles]);

  const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;

  const destroyChart = useCallback(() => {
    observerRef.current?.disconnect();
    observerRef.current = null;
    seqLineRef.current?.clear();
    seqLineRef.current = null;
    chartRef.current?.remove();
    chartRef.current = null;
    seriesRef.current = null;
  }, []);

  useEffect(() => {
    destroyChart();
  }, [effectiveGranularity, isDark, destroyChart]);

  useEffect(() => {
    return destroyChart;
  }, [destroyChart]);

  useEffect(() => {
    if (!containerRef.current || candles.length === 0) return;

    if (!chartRef.current) {
      const container = containerRef.current;
      const { upColor, downColor } = getCandleColors();
      const chart = createChart(container, {
        height: chartHeight,
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

      // Attach sequence position line for current tick indicator
      const seqLine = new SequencePositionLine({
        maxExtrapolation: Infinity,
      });
      series.attachPrimitive(seqLine);
      seqLineRef.current = seqLine;

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
  }, [candles, chartHeight, isDark, paddedRange, timezone]);

  const handleResetZoom = useCallback(() => {
    if (paddedRange && chartRef.current) {
      chartRef.current.timeScale().setVisibleRange(paddedRange);
    } else {
      chartRef.current?.timeScale().fitContent();
    }
  }, [paddedRange]);

  // Update sequence position line when current tick changes
  useEffect(() => {
    if (!seqLineRef.current) return;
    if (currentTickTimestamp) {
      seqLineRef.current.setPosition(
        currentTickTimestamp,
        currentTickPrice ?? null
      );
    } else {
      seqLineRef.current.clear();
    }
  }, [currentTickTimestamp, currentTickPrice]);

  const handleReload = useCallback(() => {
    destroyChart();
    if (!endTime) {
      setLiveEndTime(new Date().toISOString());
      return;
    }
    void replaceWithCountWindow();
  }, [destroyChart, endTime, replaceWithCountWindow]);

  const displayInstrument = instrument.replace('_', '/');

  if (isInitialLoading) {
    return (
      <Paper
        variant="outlined"
        sx={{
          p: 1.5,
          ...(cardHeight ? { height: cardHeight, overflow: 'hidden' } : {}),
        }}
      >
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
      <Paper
        variant="outlined"
        sx={{
          p: 1.5,
          ...(cardHeight ? { height: cardHeight, overflow: 'hidden' } : {}),
        }}
      >
        <Typography variant="subtitle2" sx={{ mb: 1 }}>
          {displayInstrument}
        </Typography>
        <Alert severity="warning">{error}</Alert>
      </Paper>
    );
  }

  if (candles.length === 0) {
    return (
      <Paper
        variant="outlined"
        sx={{
          p: 1.5,
          ...(cardHeight ? { height: cardHeight, overflow: 'hidden' } : {}),
        }}
      >
        <Typography variant="subtitle2" sx={{ mb: 1 }}>
          {displayInstrument}
        </Typography>
        <Alert severity="info">{t('metrics.noData')}</Alert>
      </Paper>
    );
  }

  return (
    <Paper
      variant="outlined"
      sx={{
        p: 1.5,
        ...(cardHeight ? { height: cardHeight, overflow: 'hidden' } : {}),
      }}
    >
      <Box
        ref={headerRef}
        sx={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          mb: 0.5,
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
          <DragIndicatorIcon
            sx={{ fontSize: 16, color: 'text.disabled', cursor: 'grab' }}
          />
          <Typography variant="subtitle2">{displayInstrument}</Typography>
        </Box>
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
                sx={{
                  px: { xs: 0.5, sm: 1 },
                  py: 0.15,
                  fontSize: { xs: '0.6rem', sm: '0.7rem' },
                  minWidth: { xs: 28, sm: 'auto' },
                }}
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
