/**
 * TaskMetricsTab - Time-series metrics dashboard for backtest/trading tasks.
 *
 * Renders a grid of line charts, one per metric key, using @mui/x-charts.
 */

import { useMemo } from 'react';
import {
  Box,
  Grid,
  Paper,
  Typography,
  CircularProgress,
  Alert,
} from '@mui/material';
import { LineChart } from '@mui/x-charts/LineChart';
import { useTranslation } from 'react-i18next';
import type { MetricPoint } from '../../../utils/fetchMetrics';
import { MetricsToolbar } from './MetricsToolbar';

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
 * MUI X-Charts internal constants that eat into the yAxis `width` budget.
 * The actual label clipping rect = width − TICK_SIZE − TICK_LABEL_GAP.
 * Source: @mui/x-charts/internals (DEFAULT_TICK_SIZE=6, TICK_LABEL_GAP=2).
 */
const Y_AXIS_OVERHEAD = 6 + 2; // tickSize + tickLabelGap

/** Shared off-screen canvas for measuring text width. */
let _measureCtx: CanvasRenderingContext2D | null = null;
function getTextMeasureCtx(): CanvasRenderingContext2D {
  if (!_measureCtx) {
    const canvas = document.createElement('canvas');
    _measureCtx = canvas.getContext('2d')!;
  }
  return _measureCtx;
}

/** Font string matching the tick label style applied to the chart. */
const TICK_FONT = '10px "Roboto", "Helvetica", "Arial", sans-serif';

/**
 * Format a Y-axis tick value exactly as the chart's valueFormatter does.
 * This must stay in sync with the valueFormatter passed to yAxis below.
 */
function formatYLabel(v: number, format?: 'pct' | 'int' | 'currency'): string {
  if (format === 'pct') return `${v.toFixed(1)}%`;
  if (format === 'currency') return v.toFixed(1);
  if (format === 'int') return Math.round(v).toLocaleString();
  return v.toFixed(1);
}

/**
 * Generate representative Y-axis tick values that d3's linear scale would
 * produce, so we can measure the widest label.  We use a simple nice-number
 * approach: compute a human-friendly step from the data range and the
 * desired tick count, then enumerate ticks from the rounded min to max.
 */
function generateRepresentativeTicks(
  yValues: number[],
  tickCount: number
): number[] {
  if (yValues.length === 0) return [0];
  const rawMin = Math.min(...yValues);
  const rawMax = Math.max(...yValues);
  if (rawMin === rawMax) return [rawMin];

  const range = rawMax - rawMin;
  // d3-scale niceNum: round the step to a "nice" number
  const roughStep = range / Math.max(tickCount - 1, 1);
  const mag = Math.pow(10, Math.floor(Math.log10(roughStep)));
  const residual = roughStep / mag;
  let niceStep: number;
  if (residual <= 1.5) niceStep = 1 * mag;
  else if (residual <= 3) niceStep = 2 * mag;
  else if (residual <= 7) niceStep = 5 * mag;
  else niceStep = 10 * mag;

  const niceMin = Math.floor(rawMin / niceStep) * niceStep;
  const niceMax = Math.ceil(rawMax / niceStep) * niceStep;

  const ticks: number[] = [];
  for (let v = niceMin; v <= niceMax + niceStep * 0.01; v += niceStep) {
    ticks.push(v);
  }
  return ticks;
}

/**
 * Measure the exact pixel width needed for the Y-axis so that no label
 * is ever truncated, while adding no unnecessary padding.
 *
 * Uses Canvas.measureText() for pixel-accurate measurement, and
 * generates representative tick values to cover all labels the chart
 * will actually render (not just min/max).
 *
 * Returns a value suitable for both yAxis `width` and margin `left`.
 */
function measureYAxisWidth(
  yValues: number[],
  tickCount: number,
  format?: 'pct' | 'int' | 'currency'
): number {
  const ticks = generateRepresentativeTicks(yValues, tickCount);
  const ctx = getTextMeasureCtx();
  ctx.font = TICK_FONT;

  let maxPx = 0;
  for (const v of ticks) {
    const label = formatYLabel(v, format);
    const w = ctx.measureText(label).width;
    if (w > maxPx) maxPx = w;
  }

  // Total = measured label width + MUI internal overhead + 2px safety
  return Math.ceil(maxPx) + Y_AXIS_OVERHEAD + 2;
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
}: TaskMetricsTabProps) {
  const { t } = useTranslation('common');

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

  // Compute per-chart Y-axis width using pixel-accurate text measurement.
  // Each chart gets exactly the width it needs — no more, no less.
  const perChartLeftMargin = useMemo(() => {
    const map: Record<string, number> = {};
    for (const m of availableMetrics) {
      const cd = chartDataMap[m.key];
      if (!cd || cd.y.length < 2) continue;
      const tickCount = computeYTickCount(cd.y);
      map[m.key] = measureYAxisWidth(cd.y, tickCount, m.format);
    }
    return map;
  }, [availableMetrics, chartDataMap]);

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
    <Box sx={{ p: { xs: 1, sm: 2 } }}>
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
      <Grid container spacing={2}>
        {availableMetrics.map((m) => {
          const cd = chartDataMap[m.key];
          if (!cd || cd.x.length < 2) return null;
          const lastVal = cd.y[cd.y.length - 1];
          const rangeMs = cd.x[cd.x.length - 1].getTime() - cd.x[0].getTime();
          const yTickCount = computeYTickCount(cd.y);
          const xTickCount = computeXTickCount(cd.x.length);
          const leftMargin = perChartLeftMargin[m.key] ?? 45;
          return (
            <Grid key={m.key} size={{ xs: 12, md: 6 }}>
              <Paper variant="outlined" sx={{ p: 1.5 }}>
                <Box
                  sx={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'baseline',
                    mb: 0.5,
                  }}
                >
                  <Typography variant="subtitle2">
                    {t(`metrics.${m.key}`, {
                      defaultValue: m.key.replace(/_/g, ' '),
                    })}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    {formatValue(lastVal, m.format)}
                  </Typography>
                </Box>
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
                      width: leftMargin,
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
                    left: leftMargin,
                    right: 16,
                    top: 8,
                    bottom: 36,
                  }}
                  hideLegend
                  slotProps={{
                    axisTickLabel: {
                      style: { fontSize: 10 },
                    },
                  }}
                />
              </Paper>
            </Grid>
          );
        })}
      </Grid>
    </Box>
  );
}
