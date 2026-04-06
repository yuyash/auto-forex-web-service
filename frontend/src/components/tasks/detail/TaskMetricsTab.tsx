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
 * Estimate the pixel width needed for the Y-axis including tick marks
 * and internal gaps.
 *
 * MUI X-Charts defaults the Y-axis width to only 45 px
 * (DEFAULT_AXIS_SIZE_WIDTH).  The label rendering budget is even
 * smaller: axisWidth − tickSize(6) − TICK_LABEL_GAP(2) = 37 px.
 * Any label wider than that gets truncated with "…".
 *
 * This function computes a width large enough for the longest label
 * and is used as both the yAxis `width` prop (controls the label
 * clipping rectangle) and the chart `margin.left` (reserves space
 * in the SVG).
 */
function estimateYAxisWidth(
  yValues: number[],
  format?: 'pct' | 'int' | 'currency'
): number {
  if (yValues.length === 0) return 20;
  const min = Math.min(...yValues);
  const max = Math.max(...yValues);
  const samples = [min, max];

  let maxLen = 0;
  for (const v of samples) {
    let label: string;
    if (format === 'pct') {
      label = `${v.toFixed(1)}%`;
    } else if (format === 'currency') {
      label = v.toFixed(1);
    } else if (format === 'int') {
      label = Math.round(v).toLocaleString();
    } else {
      label = v.toFixed(1);
    }
    if (label.length > maxLen) maxLen = label.length;
  }
  // ~3.5px per char at fontSize 10, plus tick/gap overhead
  return Math.max(20, maxLen * 3.5 + 6);
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

  // Compute per-chart Y-axis label width so each chart fits its own labels
  // without wasting space on charts with shorter labels.
  const perChartLeftMargin = useMemo(() => {
    const map: Record<string, number> = {};
    for (const m of availableMetrics) {
      const cd = chartDataMap[m.key];
      if (!cd || cd.y.length < 2) continue;
      map[m.key] = estimateYAxisWidth(cd.y, m.format);
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
          const leftMargin = perChartLeftMargin[m.key] ?? 20;
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
                      valueFormatter:
                        m.format === 'pct'
                          ? (v: number | null) =>
                              v != null ? `${v.toFixed(1)}%` : ''
                          : m.format === 'currency'
                            ? (v: number | null) =>
                                v != null ? v.toFixed(1) : ''
                            : undefined,
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
