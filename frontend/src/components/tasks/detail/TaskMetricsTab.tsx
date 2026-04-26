/**
 * TaskMetricsTab - Time-series metrics dashboard for backtest/trading tasks.
 *
 * Renders a grid of line charts, one per metric key, using @mui/x-charts.
 */

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ComponentProps,
} from 'react';
import { Box, Grid, Alert, CircularProgress, Typography } from '@mui/material';
import DragIndicatorIcon from '@mui/icons-material/DragIndicator';
import { LineChart } from '@mui/x-charts/LineChart';
import { useTranslation } from 'react-i18next';
import type { MetricPoint } from '../../../utils/fetchMetrics';
import { MetricsToolbar } from './MetricsToolbar';
import { MetricsOhlcChart } from './MetricsOhlcChart';
import { ChartPanel } from './ChartPanel';
import {
  MetricsChartOrderDialog,
  type MetricsChartOrderItem,
} from './MetricsChartOrderDialog';
import { useMetricsOrder } from '../../../hooks/useMetricsOrder';
import { layoutTokens, spacingTokens } from '../../../theme/density';

interface TaskMetricsTabProps {
  data: MetricPoint[];
  isLoading: boolean;
  error: Error | null;
  currency?: string;
  dataSource?: string;
  resumeCursorTimestamp?: string | null;
  consistencyWarnings?: Array<Record<string, unknown>>;
  interval: number;
  since: string;
  until: string;
  onIntervalChange: (interval: number) => void;
  onSinceChange: (since: string) => void;
  onUntilChange: (until: string) => void;
  onRefresh: () => void;
  /** Instrument identifier for the OHLC chart (e.g. "USD_JPY") */
  instrument?: string;
  /** ISO start time for the OHLC chart range */
  startTime?: string;
  /** ISO end time for the OHLC chart range */
  endTime?: string | null;
  /** Current tick timestamp for the sequence position line */
  currentTickTimestamp?: string | null;
  /** Current tick price for the sequence position line */
  currentTickPrice?: number | null;
}

/** Metrics to chart and their display order */
const CHART_METRICS: {
  key: string;
  color: string;
  format?: 'pct' | 'int' | 'currency';
}[] = [
  { key: 'current_balance', color: '#1976d2', format: 'currency' },
  { key: 'total_pnl', color: '#2e7d32', format: 'currency' },
  { key: 'realized_pnl', color: '#388e3c', format: 'currency' },
  { key: 'unrealized_pnl', color: '#f57c00', format: 'currency' },
  { key: 'total_return', color: '#7b1fa2', format: 'pct' },
  { key: 'margin_ratio', color: '#d32f2f', format: 'pct' },
  { key: 'open_positions', color: '#0288d1', format: 'int' },
  { key: 'closed_positions', color: '#455a64', format: 'int' },
  { key: 'total_trades', color: '#5d4037', format: 'int' },
  { key: 'win_rate', color: '#00796b', format: 'pct' },
  { key: 'winning_trades', color: '#2e7d32', format: 'int' },
  { key: 'losing_trades', color: '#c62828', format: 'int' },
  { key: 'ticks_processed', color: '#546e7a', format: 'int' },
];

/** Keys whose raw value is a ratio (0–1) that must be multiplied by 100 for display */
const RATIO_KEYS = new Set(['margin_ratio']);

/**
 * Compute a short date/time label appropriate for the data's time span
 * and the current granularity.
 */
function formatTickLabel(
  date: Date,
  rangeMs: number,
  intervalMin: number
): string {
  const DAY = 86_400_000;
  if (rangeMs <= DAY) {
    return date.toLocaleTimeString(undefined, {
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    });
  }
  if (rangeMs <= 7 * DAY) {
    // Up to ~1 week: show MM/DD HH:mm
    return (
      date.toLocaleDateString(undefined, {
        month: '2-digit',
        day: '2-digit',
      }) +
      ' ' +
      date.toLocaleTimeString(undefined, {
        hour: '2-digit',
        minute: '2-digit',
        hour12: false,
      })
    );
  }
  if (rangeMs <= 90 * DAY) {
    // Up to ~3 months: show MM/DD
    if (intervalMin < 60) {
      return (
        date.toLocaleDateString(undefined, {
          month: '2-digit',
          day: '2-digit',
        }) +
        ' ' +
        date.toLocaleTimeString(undefined, {
          hour: '2-digit',
          minute: '2-digit',
          hour12: false,
        })
      );
    }
    return date.toLocaleDateString(undefined, {
      month: '2-digit',
      day: '2-digit',
    });
  }
  // Longer: show YYYY/MM/DD
  return date.toLocaleDateString(undefined, {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  });
}

/**
 * Format tooltip date/time based on granularity.
 */
function formatTooltipDate(date: Date, intervalMin: number): string {
  if (intervalMin >= 1440) {
    // Daily: date only
    return date.toLocaleDateString(undefined, {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    });
  }
  if (intervalMin >= 240) {
    // 4h: date + hour
    return (
      date.toLocaleDateString(undefined, {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
      }) +
      ' ' +
      date.toLocaleTimeString(undefined, {
        hour: '2-digit',
        minute: '2-digit',
        hour12: false,
      })
    );
  }
  // Sub-hourly: full date + time
  return (
    date.toLocaleDateString(undefined, {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    }) +
    ' ' +
    date.toLocaleTimeString(undefined, {
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    })
  );
}

/**
 * Compute the pixel width needed for each metric chart's Y-axis tick labels.
 * Axis labels are intentionally compact because these cards prioritize the
 * plot area over high-precision tick text.
 *
 * MUI X Charts internally reserves `yAxis.width` for the axis region and
 * uses `axisWidth - tickSize(6) - TICK_LABEL_GAP(2)` as the maximum label
 * width.  Labels exceeding that limit are ellipsized.  We therefore need
 * `yAxis.width = maxLabelPx + 8` and `margin.right = yAxis.width`.
 *
 * We estimate text width at fontSize 10 using a conservative proportional
 * sans-serif digit width.
 */
const CHAR_WIDTH_PX = 6;
const Y_AXIS_OVERHEAD = 8; // tickSize(6) + TICK_LABEL_GAP(2)
const MIN_Y_AXIS_WIDTH = 34;

/**
 * Format a Y-axis tick value exactly as the chart's valueFormatter does.
 * This must stay in sync with the valueFormatter passed to yAxis below.
 *
 * Avoid fixed two-decimal labels; they consume too much horizontal space in
 * small chart cards and do not add useful precision for trend reading.
 */
function formatYLabel(v: number, format?: 'pct' | 'int' | 'currency'): string {
  if (format === 'pct') return `${v.toFixed(1)}%`;
  if (format === 'currency') return v.toFixed(0);
  if (format === 'int') return Math.round(v).toLocaleString();
  return v.toFixed(1);
}

/** Compute a suitable Y-axis tick count based on the value range. */
function computeYTickCount(yValues: number[]): number {
  if (yValues.length < 2) return 4;
  let min = yValues[0];
  let max = yValues[0];
  for (let i = 1; i < yValues.length; i += 1) {
    const value = yValues[i];
    if (value < min) min = value;
    if (value > max) max = value;
  }
  const range = max - min;
  if (range === 0) return 2;
  // Aim for 4-5 ticks for most charts
  return 5;
}

/** Compute a suitable X-axis tick count based on data point count and range. */
function computeXTickCount(dataLen: number): number {
  if (dataLen <= 10) return dataLen;
  if (dataLen <= 50) return 8;
  return 10;
}

/** Fixed height for all chart cards to ensure consistent grid layout */
const CHART_CARD_HEIGHT = 360;
const LINE_CHART_FALLBACK_HEIGHT = CHART_CARD_HEIGHT - 52;
const OHLC_KEY = '__ohlc__';
const MIN_CHART_MEASURE_PX = 1;
const LINE_CHART_LEFT_MARGIN = 8;
const LINE_CHART_RIGHT_MARGIN = 8;
const LINE_CHART_TOP_MARGIN = 4;
const LINE_CHART_BOTTOM_MARGIN = 22;

function FillLineChart({
  fallbackHeight,
  ...chartProps
}: ComponentProps<typeof LineChart> & { fallbackHeight: number }) {
  const hostRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ width: 0, height: 0 });

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return undefined;

    const updateSize = () => {
      const rect = host.getBoundingClientRect();
      const nextWidth = Math.max(
        MIN_CHART_MEASURE_PX,
        Math.floor(host.clientWidth || rect.width)
      );
      const measuredHeight = Math.floor(host.clientHeight || rect.height);
      const nextHeight = Math.max(
        MIN_CHART_MEASURE_PX,
        measuredHeight > MIN_CHART_MEASURE_PX ? measuredHeight : fallbackHeight
      );
      setSize((current) =>
        current.width === nextWidth && current.height === nextHeight
          ? current
          : { width: nextWidth, height: nextHeight }
      );
    };

    updateSize();

    if (typeof ResizeObserver === 'undefined') {
      window.addEventListener('resize', updateSize);
      return () => window.removeEventListener('resize', updateSize);
    }

    const observer = new ResizeObserver(updateSize);
    observer.observe(host);
    return () => observer.disconnect();
  }, [fallbackHeight]);

  return (
    <Box
      ref={hostRef}
      sx={{
        width: '100%',
        height: '100%',
        flex: '1 1 auto',
        alignSelf: 'stretch',
        minWidth: 0,
        minHeight: 0,
        '& > *': {
          width: '100% !important',
          height: '100% !important',
        },
        '& > [class*="MuiChartsWrapper-root"]': {
          width: '100% !important',
          height: '100% !important',
        },
        '& svg.MuiChartsSurface-root': {
          width: '100% !important',
          height: '100% !important',
        },
      }}
    >
      {size.width > 0 && size.height > 0 ? (
        <LineChart {...chartProps} width={size.width} height={size.height} />
      ) : null}
    </Box>
  );
}

export function TaskMetricsTab({
  data,
  isLoading,
  error,
  currency,
  consistencyWarnings = [],
  interval,
  since,
  until,
  onIntervalChange,
  onSinceChange,
  onUntilChange,
  onRefresh,
  instrument,
  startTime,
  endTime,
  currentTickTimestamp,
  currentTickPrice,
}: TaskMetricsTabProps) {
  const { t } = useTranslation('common');
  const [ohlcRefreshToken, setOhlcRefreshToken] = useState(0);
  const [orderDialogOpen, setOrderDialogOpen] = useState(false);

  const hasOhlc = !!(instrument && startTime);

  const handleRefresh = useCallback(() => {
    setOhlcRefreshToken((value) => value + 1);
    void onRefresh();
  }, [onRefresh]);

  // Determine which metrics actually have data
  const availableMetrics = useMemo(() => {
    if (data.length === 0) return [];
    const keysWithData = new Set<string>();
    for (const point of data) {
      for (const [k, v] of Object.entries(point.metrics)) {
        if (v != null && v !== '' && !isNaN(Number(v))) {
          keysWithData.add(k);
        }
      }
    }
    return CHART_METRICS.filter((m) => keysWithData.has(m.key));
  }, [data]);

  // Build the list of all chart keys (OHLC first, then metrics) for ordering
  const allChartKeys = useMemo(() => {
    const keys: string[] = [];
    if (hasOhlc) keys.push(OHLC_KEY);
    for (const m of availableMetrics) keys.push(m.key);
    return keys;
  }, [availableMetrics, hasOhlc]);

  const { orderedKeys, moveItem, setOrder, resetOrder } =
    useMetricsOrder(allChartKeys);

  // Map metric key → metric config for quick lookup
  const metricsMap = useMemo(() => {
    const map = new Map<string, (typeof CHART_METRICS)[number]>();
    for (const m of CHART_METRICS) map.set(m.key, m);
    return map;
  }, []);

  // Compute effective interval from data range (for formatting)
  const effectiveInterval = useMemo(() => {
    if (interval > 0) return interval;
    if (data.length >= 2) {
      const rangeS = data[data.length - 1].t - data[0].t;
      const DAY = 86_400;
      if (rangeS <= 14 * DAY) return 1;
      if (rangeS <= 31 * DAY) return 5;
      if (rangeS <= 93 * DAY) return 15;
      if (rangeS <= 183 * DAY) return 60;
      if (rangeS <= 366 * DAY) return 240;
      return 1440;
    }
    return 1;
  }, [interval, data]);

  // Build chart data per metric
  const chartDataMap = useMemo(() => {
    const map: Record<string, { x: Date[]; y: number[] }> = {};
    for (const m of availableMetrics) {
      const x: Date[] = [];
      const y: number[] = [];
      const scale = RATIO_KEYS.has(m.key) ? 100 : 1;
      for (const point of data) {
        const val = point.metrics[m.key];
        if (val != null && val !== '') {
          const num = Number(val);
          if (!isNaN(num)) {
            x.push(new Date(point.t * 1000));
            y.push(num * scale);
          }
        }
      }
      if (x.length > 0) {
        map[m.key] = { x, y };
      }
    }
    return map;
  }, [data, availableMetrics]);

  // Compute per-metric Y-axis width so each chart uses only the space
  // its own labels need, avoiding wasted horizontal space.
  // A 20% padding is added to account for MUI's "nice" tick rounding that
  // may produce values slightly outside the data range.
  const yAxisWidthMap = useMemo(() => {
    const map: Record<string, number> = {};
    for (const m of availableMetrics) {
      const cd = chartDataMap[m.key];
      if (!cd || cd.y.length === 0) continue;
      let maxChars = 0;
      let yMin = cd.y[0];
      let yMax = cd.y[0];
      for (let i = 1; i < cd.y.length; i += 1) {
        const value = cd.y[i];
        if (value < yMin) yMin = value;
        if (value > yMax) yMax = value;
      }
      for (const v of [yMin, yMax, yMin * 1.2, yMax * 1.2]) {
        const label = formatYLabel(v, m.format);
        if (label.length > maxChars) maxChars = label.length;
      }
      const labelPx = maxChars * CHAR_WIDTH_PX;
      map[m.key] = Math.max(
        MIN_Y_AXIS_WIDTH,
        Math.ceil(labelPx) + Y_AXIS_OVERHEAD
      );
    }
    return map;
  }, [availableMetrics, chartDataMap]);

  // --- Drag-and-drop reorder state ---
  const dragKeyRef = useRef<string | null>(null);
  const lastDragTargetRef = useRef<string | null>(null);
  const [dragKey, setDragKey] = useState<string | null>(null);
  const [dragOverKey, setDragOverKey] = useState<string | null>(null);

  const handleDragStart = useCallback((e: React.DragEvent, key: string) => {
    dragKeyRef.current = key;
    lastDragTargetRef.current = null;
    setDragKey(key);
    setDragOverKey(null);
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', key);
  }, []);

  const handleDragOver = useCallback(
    (e: React.DragEvent, targetKey: string) => {
      e.preventDefault();
      e.dataTransfer.dropEffect = 'move';
      setDragOverKey(targetKey);

      const sourceKey = dragKeyRef.current;
      if (
        sourceKey &&
        sourceKey !== targetKey &&
        lastDragTargetRef.current !== targetKey
      ) {
        moveItem(sourceKey, targetKey);
        lastDragTargetRef.current = targetKey;
      }
    },
    [moveItem]
  );

  const handleDrop = useCallback(
    (e: React.DragEvent, targetKey: string) => {
      e.preventDefault();
      const sourceKey = dragKeyRef.current;
      if (sourceKey && sourceKey !== targetKey) {
        moveItem(sourceKey, targetKey);
      }
      dragKeyRef.current = null;
      lastDragTargetRef.current = null;
      setDragKey(null);
      setDragOverKey(null);
    },
    [moveItem]
  );

  const handleDragEnd = useCallback(() => {
    dragKeyRef.current = null;
    lastDragTargetRef.current = null;
    setDragKey(null);
    setDragOverKey(null);
  }, []);

  const chartOrderItems = useMemo<MetricsChartOrderItem[]>(() => {
    const items: MetricsChartOrderItem[] = [];
    for (const key of orderedKeys) {
      if (key === OHLC_KEY) {
        items.push({
          key,
          label: instrument ?? t('metrics.ohlcChart', 'OHLC chart'),
          color: '#26a69a',
        });
        continue;
      }
      const metric = metricsMap.get(key);
      if (!metric) continue;
      items.push({
        key,
        label: t(`metrics.${metric.key}`, {
          defaultValue: metric.key.replace(/_/g, ' '),
        }),
        color: metric.color,
      });
    }
    return items;
  }, [instrument, metricsMap, orderedKeys, t]);

  if (isLoading && data.length === 0) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Box sx={{ p: 2 }}>
        <Alert severity="error">{String(error)}</Alert>
      </Box>
    );
  }

  if (data.length === 0) {
    return (
      <Box sx={{ p: 3 }}>
        <Typography color="text.secondary">{t('metrics.noData')}</Typography>
      </Box>
    );
  }

  const currencySuffix = currency ? ` ${currency}` : '';

  const formatValue = (val: number, format?: string) => {
    if (format === 'pct') return `${val.toFixed(1)}%`;
    if (format === 'int') return Math.round(val).toLocaleString();
    if (format === 'currency') return `${val.toFixed(0)}${currencySuffix}`;
    return val.toFixed(1);
  };

  return (
    <Box
      sx={{
        px: layoutTokens.pagePadding,
        py: { xs: 1, sm: 1.5 },
        minWidth: 0,
        width: '100%',
        maxWidth: { xs: '100%', xl: 1920 },
        mx: 'auto',
      }}
    >
      <MetricsToolbar
        interval={interval}
        since={since}
        until={until}
        onIntervalChange={onIntervalChange}
        onSinceChange={onSinceChange}
        onUntilChange={onUntilChange}
        onRefresh={handleRefresh}
        onConfigureCharts={() => setOrderDialogOpen(true)}
        isLoading={isLoading}
      />
      {consistencyWarnings.length > 0 ? (
        <Alert severity="warning" sx={{ mb: 1.5 }}>
          {consistencyWarnings.length} continuity warning(s) detected after
          resume. Review the latest metric jump before trusting this run.
        </Alert>
      ) : null}
      <Grid
        container
        spacing={layoutTokens.sectionGap}
        justifyContent="center"
        alignItems="stretch"
        sx={{ mt: 0, minWidth: 0, width: '100%' }}
      >
        {orderedKeys.map((key) => {
          // OHLC chart
          if (key === OHLC_KEY) {
            return (
              <Grid
                key={OHLC_KEY}
                size={{ xs: 12, lg: 6 }}
                draggable
                onDragStart={(e) => handleDragStart(e, OHLC_KEY)}
                onDragOver={(e) => handleDragOver(e, OHLC_KEY)}
                onDrop={(e) => handleDrop(e, OHLC_KEY)}
                onDragEnd={handleDragEnd}
                sx={{
                  opacity: dragKey === OHLC_KEY ? 0.4 : 1,
                  cursor: 'grab',
                  minWidth: 0,
                  transition:
                    'opacity 120ms ease, transform 120ms ease, outline-color 120ms ease',
                  transform:
                    dragOverKey === OHLC_KEY && dragKey !== OHLC_KEY
                      ? 'translateY(-2px)'
                      : 'none',
                  outline: '2px solid',
                  outlineColor:
                    dragOverKey === OHLC_KEY && dragKey !== OHLC_KEY
                      ? 'primary.main'
                      : 'transparent',
                  outlineOffset: 3,
                  borderRadius: 1,
                }}
              >
                <MetricsOhlcChart
                  instrument={instrument!}
                  startTime={startTime!}
                  endTime={endTime ?? undefined}
                  cardHeight={CHART_CARD_HEIGHT}
                  currentTickTimestamp={currentTickTimestamp}
                  currentTickPrice={currentTickPrice}
                  refreshToken={ohlcRefreshToken}
                />
              </Grid>
            );
          }

          // Metric line chart
          const m = metricsMap.get(key);
          if (!m) return null;
          const cd = chartDataMap[m.key];
          if (!cd || cd.x.length < 2) return null;
          const lastVal = cd.y[cd.y.length - 1];
          const rangeMs = cd.x[cd.x.length - 1].getTime() - cd.x[0].getTime();
          const yTickCount = computeYTickCount(cd.y);
          const xTickCount = computeXTickCount(cd.x.length);
          const metricYAxisWidth = yAxisWidthMap[m.key] ?? MIN_Y_AXIS_WIDTH;
          return (
            <Grid
              key={m.key}
              size={{ xs: 12, lg: 6 }}
              draggable
              onDragStart={(e) => handleDragStart(e, m.key)}
              onDragOver={(e) => handleDragOver(e, m.key)}
              onDrop={(e) => handleDrop(e, m.key)}
              onDragEnd={handleDragEnd}
              sx={{
                opacity: dragKey === m.key ? 0.4 : 1,
                cursor: 'grab',
                minWidth: 0,
                transition:
                  'opacity 120ms ease, transform 120ms ease, outline-color 120ms ease',
                transform:
                  dragOverKey === m.key && dragKey !== m.key
                    ? 'translateY(-2px)'
                    : 'none',
                outline: '2px solid',
                outlineColor:
                  dragOverKey === m.key && dragKey !== m.key
                    ? 'primary.main'
                    : 'transparent',
                outlineOffset: 3,
                borderRadius: 1,
              }}
            >
              <ChartPanel
                title={t(`metrics.${m.key}`, {
                  defaultValue: m.key.replace(/_/g, ' '),
                })}
                valueLabel={formatValue(lastVal, m.format)}
                height={CHART_CARD_HEIGHT}
                headerPrefix={
                  <DragIndicatorIcon
                    sx={{
                      fontSize: 16,
                      color: 'text.disabled',
                      cursor: 'grab',
                      mr: spacingTokens.xxs,
                    }}
                  />
                }
              >
                <FillLineChart
                  fallbackHeight={LINE_CHART_FALLBACK_HEIGHT}
                  xAxis={[
                    {
                      data: cd.x,
                      scaleType: 'time' as const,
                      tickNumber: xTickCount,
                      tickLabelStyle: { fontSize: 10 },
                      valueFormatter: (
                        v: Date,
                        context: { location: string }
                      ) => {
                        if (context.location === 'tooltip') {
                          return formatTooltipDate(v, effectiveInterval);
                        }
                        return formatTickLabel(v, rangeMs, effectiveInterval);
                      },
                    },
                  ]}
                  yAxis={[
                    {
                      position: 'right',
                      width: metricYAxisWidth,
                      tickNumber: yTickCount,
                      valueFormatter: (v: number | null) =>
                        v != null ? formatYLabel(v, m.format) : '',
                    },
                  ]}
                  series={[
                    {
                      data: cd.y,
                      color: m.color,
                      showMark: false,
                      valueFormatter: (v: number | null) =>
                        v != null ? formatValue(v, m.format) : '',
                    },
                  ]}
                  axisHighlight={{ x: 'line', y: 'none' }}
                  grid={{ vertical: true, horizontal: true }}
                  margin={{
                    left: LINE_CHART_LEFT_MARGIN,
                    right: LINE_CHART_RIGHT_MARGIN,
                    top: LINE_CHART_TOP_MARGIN,
                    bottom: LINE_CHART_BOTTOM_MARGIN,
                  }}
                  hideLegend
                  slotProps={{
                    axisTickLabel: {
                      style: { fontSize: 10 },
                    },
                  }}
                />
              </ChartPanel>
            </Grid>
          );
        })}
      </Grid>
      <MetricsChartOrderDialog
        key={
          orderDialogOpen
            ? `open-${chartOrderItems.map((item) => item.key).join('|')}`
            : 'closed'
        }
        open={orderDialogOpen}
        items={chartOrderItems}
        onClose={() => setOrderDialogOpen(false)}
        onSave={setOrder}
        onReset={resetOrder}
      />
    </Box>
  );
}
