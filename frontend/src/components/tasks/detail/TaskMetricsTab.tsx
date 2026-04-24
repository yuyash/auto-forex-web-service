/**
 * TaskMetricsTab - Time-series metrics dashboard for backtest/trading tasks.
 *
 * Renders a grid of line charts, one per metric key, using @mui/x-charts.
 */

import { useCallback, useMemo, useRef, useState } from 'react';
import {
  Box,
  Grid,
  Paper,
  Typography,
  CircularProgress,
  Alert,
} from '@mui/material';
import DragIndicatorIcon from '@mui/icons-material/DragIndicator';
import { LineChart } from '@mui/x-charts/LineChart';
import { useTranslation } from 'react-i18next';
import type { MetricPoint } from '../../../utils/fetchMetrics';
import { MetricsToolbar } from './MetricsToolbar';
import { MetricsOhlcChart } from './MetricsOhlcChart';
import { useMetricsOrder } from '../../../hooks/useMetricsOrder';
import { layoutTokens } from '../../../theme/theme';

interface TaskMetricsTabProps {
  data: MetricPoint[];
  isLoading: boolean;
  error: Error | null;
  currency?: string;
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
 * Compute the pixel width needed for the widest Y-axis tick label across
 * all metric charts.  This guarantees labels are never truncated and all
 * charts share the same right margin so their plot areas align.
 *
 * MUI X Charts internally reserves `yAxis.width` for the axis region and
 * uses `axisWidth - tickSize(6) - TICK_LABEL_GAP(2)` as the maximum label
 * width.  Labels exceeding that limit are ellipsized.  We therefore need
 * `yAxis.width = maxLabelPx + 8` and `margin.right = yAxis.width`.
 *
 * We estimate text width at fontSize 10 using ~6.2 px per character, which
 * is a safe upper bound for proportional sans-serif digits.
 */
const CHAR_WIDTH_PX = 6.5; // conservative estimate at fontSize 10
const Y_AXIS_OVERHEAD = 8; // tickSize(6) + TICK_LABEL_GAP(2)
const MIN_Y_AXIS_WIDTH = 40; // minimum to avoid overly narrow axes

/**
 * Format a Y-axis tick value exactly as the chart's valueFormatter does.
 * This must stay in sync with the valueFormatter passed to yAxis below.
 *
 * Always uses 2 decimal places for pct/currency to guarantee labels are
 * never truncated regardless of value magnitude.
 */
function formatYLabel(v: number, format?: 'pct' | 'int' | 'currency'): string {
  if (format === 'pct') return `${v.toFixed(2)}%`;
  if (format === 'currency') return v.toFixed(2);
  if (format === 'int') return Math.round(v).toLocaleString();
  return v.toFixed(2);
}

/** Compute a suitable Y-axis tick count based on the value range. */
function computeYTickCount(yValues: number[]): number {
  if (yValues.length < 2) return 4;
  const min = Math.min(...yValues);
  const max = Math.max(...yValues);
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
const CHART_CARD_HEIGHT = 260;
const OHLC_KEY = '__ohlc__';

export function TaskMetricsTab({
  data,
  isLoading,
  error,
  currency,
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

  const hasOhlc = !!(instrument && startTime);

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

  const { orderedKeys, moveItem } = useMetricsOrder(allChartKeys);

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
      const yMin = Math.min(...cd.y);
      const yMax = Math.max(...cd.y);
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
  const [dragKey, setDragKey] = useState<string | null>(null);

  const handleDragStart = useCallback((e: React.DragEvent, key: string) => {
    dragKeyRef.current = key;
    setDragKey(key);
    e.dataTransfer.effectAllowed = 'move';
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent, targetKey: string) => {
      e.preventDefault();
      const sourceKey = dragKeyRef.current;
      if (sourceKey && sourceKey !== targetKey) {
        moveItem(sourceKey, targetKey);
      }
      dragKeyRef.current = null;
      setDragKey(null);
    },
    [moveItem]
  );

  const handleDragEnd = useCallback(() => {
    dragKeyRef.current = null;
    setDragKey(null);
  }, []);

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
    if (format === 'pct') return `${val.toFixed(2)}%`;
    if (format === 'int') return Math.round(val).toLocaleString();
    if (format === 'currency') return `${val.toFixed(2)}${currencySuffix}`;
    return val.toFixed(2);
  };

  return (
    <Box
      sx={{
        px: layoutTokens.pagePadding,
        py: { xs: 1, sm: 1.5 },
        minWidth: 0,
      }}
    >
      <MetricsToolbar
        interval={interval}
        since={since}
        until={until}
        onIntervalChange={onIntervalChange}
        onSinceChange={onSinceChange}
        onUntilChange={onUntilChange}
        onRefresh={onRefresh}
        isLoading={isLoading}
      />
      <Grid
        container
        spacing={layoutTokens.sectionGap}
        justifyContent="center"
        alignItems="stretch"
        sx={{ mt: 0, minWidth: 0 }}
      >
        {orderedKeys.map((key) => {
          // OHLC chart
          if (key === OHLC_KEY) {
            return (
              <Grid
                key={OHLC_KEY}
                size={{ xs: 12, lg: 6, xl: 4 }}
                draggable
                onDragStart={(e) => handleDragStart(e, OHLC_KEY)}
                onDragOver={handleDragOver}
                onDrop={(e) => handleDrop(e, OHLC_KEY)}
                onDragEnd={handleDragEnd}
                sx={{
                  opacity: dragKey === OHLC_KEY ? 0.4 : 1,
                  cursor: 'grab',
                }}
              >
                <MetricsOhlcChart
                  instrument={instrument!}
                  startTime={startTime!}
                  endTime={endTime ?? undefined}
                  cardHeight={CHART_CARD_HEIGHT}
                  currentTickTimestamp={currentTickTimestamp}
                  currentTickPrice={currentTickPrice}
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
              size={{ xs: 12, lg: 6, xl: 4 }}
              draggable
              onDragStart={(e) => handleDragStart(e, m.key)}
              onDragOver={handleDragOver}
              onDrop={(e) => handleDrop(e, m.key)}
              onDragEnd={handleDragEnd}
              sx={{
                opacity: dragKey === m.key ? 0.4 : 1,
                cursor: 'grab',
              }}
            >
              <Paper
                variant="outlined"
                sx={{
                  p: { xs: 1, sm: 1.25 },
                  height: CHART_CARD_HEIGHT,
                  overflow: 'hidden',
                  display: 'flex',
                  flexDirection: 'column',
                  minWidth: 0,
                  width: '100%',
                }}
              >
                <Box
                  sx={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'baseline',
                    mb: 0.5,
                  }}
                >
                  <Box
                    sx={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 0.5,
                    }}
                  >
                    <DragIndicatorIcon
                      sx={{
                        fontSize: 16,
                        color: 'text.disabled',
                        cursor: 'grab',
                      }}
                    />
                    <Typography variant="subtitle2">
                      {t(`metrics.${m.key}`, {
                        defaultValue: m.key.replace(/_/g, ' '),
                      })}
                    </Typography>
                  </Box>
                  <Typography variant="body2" color="text.secondary">
                    {formatValue(lastVal, m.format)}
                  </Typography>
                </Box>
                <Box
                  sx={{
                    flex: 1,
                    minWidth: 0,
                    width: '100%',
                    display: 'flex',
                    justifyContent: 'center',
                    '& .MuiCharts-root': {
                      width: '100%',
                    },
                  }}
                >
                  <LineChart
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
                    height={200}
                    margin={{
                      left: 8,
                      right: metricYAxisWidth,
                      top: 8,
                      bottom: 36,
                    }}
                    hideLegend
                    slotProps={{
                      axisTickLabel: {
                        style: { fontSize: 10 },
                      },
                    }}
                    sx={{
                      width: '100%',
                      minWidth: 0,
                    }}
                  />
                </Box>
              </Paper>
            </Grid>
          );
        })}
      </Grid>
    </Box>
  );
}
