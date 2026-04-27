import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Box,
  Button,
  CircularProgress,
  Alert,
  IconButton,
  MenuItem,
  Select,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Tooltip,
} from '@mui/material';
import CheckIcon from '@mui/icons-material/Check';
import ZoomOutMapIcon from '@mui/icons-material/ZoomOutMap';
import RefreshIcon from '@mui/icons-material/Refresh';
import UpdateIcon from '@mui/icons-material/Update';
import VisibilityIcon from '@mui/icons-material/Visibility';
import VisibilityOffIcon from '@mui/icons-material/VisibilityOff';
import {
  CandlestickSeries,
  LineStyle,
  createChart,
  createSeriesMarkers,
  type IChartApi,
  type ISeriesApi,
  type CandlestickData,
  type Time,
} from 'lightweight-charts';
import { useTheme } from '@mui/material/styles';
import { useTranslation } from 'react-i18next';
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
  focusedTradeId?: string | null;
  onMarkerClick?: (tradeId: string) => void;
  priceLines?: StrategyPriceLine[];
}

export interface StrategyPriceLine {
  price: number;
  title: string;
  color: string;
  lineStyle?: LineStyle;
}

const GRANULARITY_OPTIONS = [
  'AUTO',
  'M1',
  'M5',
  'M15',
  'H1',
  'H4',
  'D',
] as const;
const RELATIVE_RANGE_OPTIONS = [
  { label: '1h', seconds: 1 * 3600 },
  { label: '3h', seconds: 3 * 3600 },
  { label: '6h', seconds: 6 * 3600 },
  { label: '12h', seconds: 12 * 3600 },
  { label: '24h', seconds: 24 * 3600 },
  { label: '72h', seconds: 72 * 3600 },
  { label: '1w', seconds: 7 * 86400 },
  { label: '2w', seconds: 14 * 86400 },
  { label: '4w', seconds: 28 * 86400 },
] as const;
const DEFAULT_RELATIVE_RANGE_SECONDS = 3600;

type RangeMode = 'relative' | 'absolute';
type ChartGranularity = (typeof GRANULARITY_OPTIONS)[number];

interface ChartRange {
  from: string;
  to: string;
}

function autoGranularity(startTime: string, endTime: string): string {
  const startSec = isoToSec(startTime);
  const endSec = isoToSec(endTime);
  if (startSec == null || endSec == null) return 'M1';
  const span = Math.max(60, endSec - startSec);
  if (span > 30 * 86400) return 'D';
  if (span > 7 * 86400) return 'H4';
  if (span > 2 * 86400) return 'H1';
  if (span > 12 * 3600) return 'M15';
  if (span > 4 * 3600) return 'M5';
  return 'M1';
}

function isoToSec(value?: string | null): number | null {
  if (!value) return null;
  const ms = new Date(value).getTime();
  return Number.isFinite(ms) ? Math.floor(ms / 1000) : null;
}

function secToIso(value: number): string {
  return new Date(value * 1000).toISOString();
}

function toDateTimeInputValue(value?: string | null): string {
  if (!value) return '';
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return '';
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 16);
}

function fromDateTimeInputValue(value: string): string | null {
  if (!value) return null;
  const ms = new Date(value).getTime();
  return Number.isFinite(ms) ? new Date(ms).toISOString() : null;
}

function buildInitialChartRange(
  startTime: string,
  effectiveEndTime: string,
  relativeRangeSeconds = DEFAULT_RELATIVE_RANGE_SECONDS
): ChartRange {
  const startSec = isoToSec(startTime);
  const endSec = isoToSec(effectiveEndTime);
  if (startSec == null || endSec == null || endSec <= startSec) {
    return { from: startTime, to: effectiveEndTime };
  }
  return {
    from: secToIso(Math.max(startSec, endSec - relativeRangeSeconds)),
    to: effectiveEndTime,
  };
}

function rangeToSeconds(
  range: ChartRange
): { from: number; to: number } | null {
  const from = isoToSec(range.from);
  const to = isoToSec(range.to);
  if (from == null || to == null || to <= from) return null;
  return { from, to };
}

function isValidCandle(candle: {
  time?: unknown;
  open?: unknown;
  high?: unknown;
  low?: unknown;
  close?: unknown;
}): candle is CandlestickData<Time> {
  return (
    Number.isFinite(candle.time) &&
    Number.isFinite(candle.open) &&
    Number.isFinite(candle.high) &&
    Number.isFinite(candle.low) &&
    Number.isFinite(candle.close)
  );
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
  focusedTradeId,
  onMarkerClick,
  priceLines = [],
}: StrategyGroupChartProps) {
  const theme = useTheme();
  const { t } = useTranslation('strategy');
  const isDark = theme.palette.mode === 'dark';
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const markersRef = useRef<ReturnType<
    typeof createSeriesMarkers<Time>
  > | null>(null);
  const observerRef = useRef<ResizeObserver | null>(null);
  const priceLinesRef = useRef<
    ReturnType<ISeriesApi<'Candlestick'>['createPriceLine']>[]
  >([]);
  const [chartInstance, setChartInstance] = useState<IChartApi | null>(null);
  const shouldApplyRangeRef = useRef(true);
  const rangeLoadTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const previousInstrumentRef = useRef(instrument);
  const currentVisibleRangeRef = useRef<{ from: number; to: number } | null>(
    null
  );
  const granularityRef = useRef<ChartGranularity>('AUTO');

  // Marker visibility toggle (default: visible)
  const [markersVisible, setMarkersVisible] = useState(true);

  // Keep a ref to the built markers for click-to-trade mapping
  const builtMarkersRef = useRef<ReturnType<typeof buildCycleMarkers>>([]);
  const fallbackEndRef = useRef(new Date().toISOString());

  const tickEnd =
    lastTickTimestamp && isoToSec(lastTickTimestamp) != null
      ? lastTickTimestamp
      : null;
  const propEnd = endTime && isoToSec(endTime) != null ? endTime : null;
  const effectiveEndTime = tickEnd ?? propEnd ?? fallbackEndRef.current;
  const latestAvailableEndRef = useRef(effectiveEndTime);
  const [rangeMode, setRangeMode] = useState<RangeMode>('relative');
  const [relativeRangeSeconds, setRelativeRangeSeconds] = useState(
    DEFAULT_RELATIVE_RANGE_SECONDS
  );
  const [chartRange, setChartRange] = useState<ChartRange>(() =>
    buildInitialChartRange(startTime, effectiveEndTime)
  );
  const [absoluteStart, setAbsoluteStart] = useState(() =>
    toDateTimeInputValue(startTime)
  );
  const [absoluteEnd, setAbsoluteEnd] = useState(() =>
    toDateTimeInputValue(effectiveEndTime)
  );

  useEffect(() => {
    latestAvailableEndRef.current = effectiveEndTime;
  }, [effectiveEndTime]);

  useEffect(() => {
    if (previousInstrumentRef.current === instrument) return;
    previousInstrumentRef.current = instrument;
    const nextRange = buildInitialChartRange(
      startTime,
      latestAvailableEndRef.current
    );
    setChartRange(nextRange);
    setAbsoluteStart(toDateTimeInputValue(nextRange.from));
    setAbsoluteEnd(toDateTimeInputValue(nextRange.to));
    shouldApplyRangeRef.current = true;
  }, [instrument, startTime]);

  const defaultAutoGranularity = useMemo(
    () =>
      chartRange.from && chartRange.to
        ? autoGranularity(chartRange.from, chartRange.to)
        : 'M1',
    [chartRange]
  );
  const [granularity, setGranularity] = useState<ChartGranularity>('AUTO');
  const [autoGranularityValue, setAutoGranularityValue] = useState(
    defaultAutoGranularity
  );
  const effectiveGranularity =
    granularity === 'AUTO' ? autoGranularityValue : granularity;

  useEffect(() => {
    granularityRef.current = granularity;
  }, [granularity]);

  useEffect(() => {
    if (granularity === 'AUTO') {
      setAutoGranularityValue(defaultAutoGranularity);
    }
  }, [defaultAutoGranularity, granularity]);

  const fullRangeEdgeCount = useMemo(() => {
    if (!chartRange.from) return 500;
    const GRANULARITY_SECONDS: Record<string, number> = {
      M1: 60,
      M5: 300,
      M15: 900,
      H1: 3600,
      H4: 14400,
      D: 86400,
    };
    const granSec = GRANULARITY_SECONDS[effectiveGranularity] ?? 60;
    const startSec = isoToSec(chartRange.from);
    const endSec = isoToSec(chartRange.to);
    if (startSec == null || endSec == null) return 500;
    const span = Math.max(60, endSec - startSec);
    return Math.ceil((span / granSec) * 1.2) + 10;
  }, [chartRange, effectiveGranularity]);

  const { candles, isInitialLoading, error, ensureRange, replaceWithRange } =
    useWindowedCandles({
      instrument,
      granularity: effectiveGranularity,
      startTime: chartRange.from,
      endTime: chartRange.to,
      initialCount: fullRangeEdgeCount,
      edgeCount: fullRangeEdgeCount,
    });
  const validCandles = useMemo(
    () =>
      candles.filter(isValidCandle).map((c) => ({
        time: c.time as Time,
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
      })),
    [candles]
  );

  const candleTimes = useMemo(
    () => validCandles.map((c) => Number(c.time)),
    [validCandles]
  );
  const markers = useMemo(() => {
    const built = buildCycleMarkers(
      trades,
      candleTimes,
      selectedTradeIds,
      markersVisible
    ).filter((marker) => Number.isFinite(Number(marker.time)));
    builtMarkersRef.current = built;
    return built;
  }, [trades, candleTimes, selectedTradeIds, markersVisible]);

  const paddedRange = useMemo(() => {
    if (!chartRange.from || validCandles.length === 0) return null;
    const startSec = isoToSec(chartRange.from);
    const endSec = isoToSec(chartRange.to);
    if (startSec == null || endSec == null || endSec <= startSec) return null;
    const span = endSec - startSec;
    const pad = Math.max(60, Math.floor(span * 0.1));
    return { from: (startSec - pad) as Time, to: (endSec + pad) as Time };
  }, [chartRange, validCandles]);

  const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;

  const destroyChart = useCallback(() => {
    if (rangeLoadTimerRef.current) {
      clearTimeout(rangeLoadTimerRef.current);
      rangeLoadTimerRef.current = null;
    }
    observerRef.current?.disconnect();
    observerRef.current = null;
    chartRef.current?.remove();
    chartRef.current = null;
    seriesRef.current = null;
    markersRef.current = null;
    priceLinesRef.current = [];
    setChartInstance(null);
  }, []);

  useEffect(() => {
    destroyChart();
  }, [effectiveGranularity, isDark, destroyChart]);

  useEffect(() => {
    return destroyChart;
  }, [destroyChart]);

  useEffect(() => {
    if (!containerRef.current || validCandles.length === 0) return;

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
      chart.timeScale().subscribeVisibleTimeRangeChange((range) => {
        if (!range || range.from == null || range.to == null) return;
        const from = Number(range.from);
        const to = Number(range.to);
        if (Number.isFinite(from) && Number.isFinite(to) && to > from) {
          currentVisibleRangeRef.current = { from, to };
          if (granularityRef.current === 'AUTO') {
            setAutoGranularityValue(
              autoGranularity(secToIso(from), secToIso(to))
            );
          }
          if (rangeLoadTimerRef.current) {
            clearTimeout(rangeLoadTimerRef.current);
          }
          rangeLoadTimerRef.current = setTimeout(() => {
            void ensureRange({ from, to });
          }, 250);
        }
      });

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

    seriesRef.current?.setData(validCandles);
    markersRef.current?.setMarkers(markers);
    for (const line of priceLinesRef.current) {
      seriesRef.current?.removePriceLine(line);
    }
    priceLinesRef.current = [];
    for (const line of priceLines) {
      if (!Number.isFinite(line.price)) continue;
      const created = seriesRef.current?.createPriceLine({
        price: line.price,
        color: line.color,
        lineWidth: 1,
        lineStyle: line.lineStyle ?? LineStyle.Dashed,
        axisLabelVisible: true,
        title: line.title,
      });
      if (created) priceLinesRef.current.push(created);
    }

    if (shouldApplyRangeRef.current && paddedRange && chartRef.current) {
      chartRef.current.timeScale().setVisibleRange(paddedRange);
      shouldApplyRangeRef.current = false;
    } else if (shouldApplyRangeRef.current) {
      chartRef.current?.timeScale().fitContent();
      shouldApplyRangeRef.current = false;
    }
  }, [
    validCandles,
    markers,
    height,
    isDark,
    paddedRange,
    timezone,
    onMarkerClick,
    priceLines,
    effectiveGranularity,
    ensureRange,
  ]);

  useMetricsOverlay({
    taskId: taskId ? String(taskId) : '',
    taskType: taskType ?? ('' as TaskType),
    executionRunId,
    chart: chartInstance,
    candleTimestamps: candleTimes,
  });

  const handleResetZoom = useCallback(() => {
    if (paddedRange && chartRef.current) {
      chartRef.current.timeScale().setVisibleRange(paddedRange);
    } else {
      chartRef.current?.timeScale().fitContent();
    }
  }, [paddedRange]);

  useEffect(() => {
    if (!focusedTradeId || !chartRef.current || candleTimes.length === 0) {
      return;
    }
    const marker = builtMarkersRef.current.find(
      (item) => item.tradeId === focusedTradeId
    );
    if (!marker) return;
    const markerTime = Number(marker.time);
    const index = (candleTimes as number[]).findIndex(
      (time) => time === markerTime
    );
    if (index < 0) return;
    const left = Math.max(0, index - 10);
    const right = Math.min(candleTimes.length - 1, index + 10);
    chartRef.current.timeScale().setVisibleRange({
      from: candleTimes[left] as Time,
      to: candleTimes[right] as Time,
    });
  }, [focusedTradeId, candleTimes]);

  const handleReload = useCallback(() => {
    const visibleRange = currentVisibleRangeRef.current;
    const fallbackRange = rangeToSeconds(chartRange);
    const range = visibleRange ?? fallbackRange;
    if (!range) return;
    void replaceWithRange(range, { preserveOnEmpty: true });
  }, [chartRange, replaceWithRange]);

  const applyChartRange = useCallback(
    (nextRange: ChartRange) => {
      const seconds = rangeToSeconds(nextRange);
      if (!seconds) return;
      setChartRange(nextRange);
      setAbsoluteStart(toDateTimeInputValue(nextRange.from));
      setAbsoluteEnd(toDateTimeInputValue(nextRange.to));
      shouldApplyRangeRef.current = true;
      const current = rangeToSeconds(chartRange);
      if (
        current &&
        current.from === seconds.from &&
        current.to === seconds.to
      ) {
        void replaceWithRange(seconds);
      }
    },
    [chartRange, replaceWithRange]
  );

  const handleApplyRange = useCallback(() => {
    if (rangeMode === 'relative') {
      const latestEndSec = isoToSec(latestAvailableEndRef.current);
      const minStartSec = isoToSec(startTime) ?? 0;
      if (latestEndSec == null) return;
      applyChartRange({
        from: secToIso(
          Math.max(minStartSec, latestEndSec - relativeRangeSeconds)
        ),
        to: secToIso(latestEndSec),
      });
      return;
    }

    const from = fromDateTimeInputValue(absoluteStart);
    const to = fromDateTimeInputValue(absoluteEnd);
    if (!from || !to) return;
    applyChartRange({ from, to });
  }, [
    absoluteEnd,
    absoluteStart,
    applyChartRange,
    rangeMode,
    relativeRangeSeconds,
    startTime,
  ]);

  const handleShowLatest = useCallback(() => {
    const latestEndSec = isoToSec(latestAvailableEndRef.current);
    if (latestEndSec == null) return;
    const current = rangeToSeconds(chartRange);
    const span =
      rangeMode === 'relative'
        ? relativeRangeSeconds
        : Math.max(60, (current?.to ?? latestEndSec) - (current?.from ?? 0));
    const minStartSec = isoToSec(startTime) ?? 0;
    applyChartRange({
      from: secToIso(Math.max(minStartSec, latestEndSec - span)),
      to: secToIso(latestEndSec),
    });
  }, [applyChartRange, chartRange, rangeMode, relativeRangeSeconds, startTime]);

  if (isInitialLoading && !chartInstance) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
        <CircularProgress size={24} />
      </Box>
    );
  }

  if (error) {
    return <Alert severity="warning">{error}</Alert>;
  }

  if (validCandles.length === 0 && !chartInstance) {
    return <Alert severity="info">No chart data available</Alert>;
  }

  return (
    <Box sx={{ position: 'relative' }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 1 }}>
        <ToggleButtonGroup
          value={granularity}
          exclusive
          onChange={(_, v) => {
            if (v) setGranularity(v as ChartGranularity);
          }}
          size="small"
          sx={{
            height: 32,
            '& .MuiToggleButton-root': {
              height: 32,
              minHeight: 32,
              py: 0,
            },
          }}
        >
          {GRANULARITY_OPTIONS.map((g) => (
            <ToggleButton
              key={g}
              value={g}
              sx={{ px: 1.5, fontSize: '0.75rem' }}
            >
              {g}
            </ToggleButton>
          ))}
        </ToggleButtonGroup>
        <ToggleButtonGroup
          value={rangeMode}
          exclusive
          onChange={(_, value: RangeMode | null) => {
            if (value) setRangeMode(value);
          }}
          size="small"
          sx={{
            height: 32,
            '& .MuiToggleButton-root': {
              height: 32,
              minHeight: 32,
              py: 0,
            },
          }}
        >
          <ToggleButton value="relative" sx={{ px: 1.25 }}>
            {t('chartControls.relative')}
          </ToggleButton>
          <ToggleButton value="absolute" sx={{ px: 1.25 }}>
            {t('chartControls.absolute')}
          </ToggleButton>
        </ToggleButtonGroup>
        {rangeMode === 'relative' ? (
          <Select
            size="small"
            value={String(relativeRangeSeconds)}
            onChange={(event) =>
              setRelativeRangeSeconds(Number(event.target.value))
            }
            sx={{
              height: 32,
              minWidth: 76,
              '& .MuiSelect-select': {
                display: 'flex',
                alignItems: 'center',
                height: 32,
                py: 0,
              },
            }}
          >
            {RELATIVE_RANGE_OPTIONS.map((option) => (
              <MenuItem key={option.seconds} value={String(option.seconds)}>
                {option.label}
              </MenuItem>
            ))}
          </Select>
        ) : (
          <>
            <TextField
              size="small"
              type="datetime-local"
              value={absoluteStart}
              onChange={(event) => setAbsoluteStart(event.target.value)}
              inputProps={{ step: 60 }}
              sx={{
                width: 185,
                '& .MuiInputBase-root': { height: 32 },
                '& input': { py: 0 },
              }}
            />
            <TextField
              size="small"
              type="datetime-local"
              value={absoluteEnd}
              onChange={(event) => setAbsoluteEnd(event.target.value)}
              inputProps={{ step: 60 }}
              sx={{
                width: 185,
                '& .MuiInputBase-root': { height: 32 },
                '& input': { py: 0 },
              }}
            />
          </>
        )}
        <Tooltip title={t('chartControls.applyRange')}>
          <Button
            size="small"
            variant="outlined"
            startIcon={<CheckIcon fontSize="small" />}
            onClick={handleApplyRange}
            sx={{ height: 32, minHeight: 32, py: 0 }}
          >
            {t('chartControls.apply')}
          </Button>
        </Tooltip>
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
        <Tooltip title={t('chartControls.reloadRange')}>
          <IconButton onClick={handleReload} size="small">
            <RefreshIcon fontSize="small" />
          </IconButton>
        </Tooltip>
        <Tooltip title={t('chartControls.latestRange')}>
          <IconButton onClick={handleShowLatest} size="small">
            <UpdateIcon fontSize="small" />
          </IconButton>
        </Tooltip>
      </Box>
      <Box ref={containerRef} sx={{ width: '100%', height }} />
      {isInitialLoading && (
        <Box
          sx={{
            position: 'absolute',
            inset: 0,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            bgcolor: 'rgba(255,255,255,0.35)',
            pointerEvents: 'none',
          }}
        >
          <CircularProgress size={24} />
        </Box>
      )}
    </Box>
  );
}
