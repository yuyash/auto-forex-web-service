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

interface TaskMetricsTabProps {
  data: MetricPoint[];
  isLoading: boolean;
  error: Error | null;
}

/** Metrics to chart and their display order */
const CHART_METRICS: {
  key: string;
  color: string;
  format?: 'pct' | 'int' | 'currency';
}[] = [
  { key: 'current_balance', color: '#1976d2', format: 'currency' },
  { key: 'total_pnl', color: '#2e7d32' },
  { key: 'realized_pnl', color: '#388e3c' },
  { key: 'unrealized_pnl', color: '#f57c00' },
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
 * Compute a short date/time label appropriate for the data's time span.
 */
function formatTickLabel(date: Date, rangeMs: number): string {
  const DAY = 86_400_000;
  if (rangeMs <= DAY) {
    // Intraday: show HH:mm
    return date.toLocaleTimeString(undefined, {
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    });
  }
  if (rangeMs <= 30 * DAY) {
    // Up to ~1 month: show MM/DD HH:mm
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

export function TaskMetricsTab({
  data,
  isLoading,
  error,
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

  const formatValue = (val: number, format?: string) => {
    if (format === 'pct') return `${val.toFixed(2)}%`;
    if (format === 'int') return Math.round(val).toLocaleString();
    if (format === 'currency') return val.toFixed(2);
    return val.toFixed(2);
  };

  return (
    <Box sx={{ p: { xs: 1, sm: 2 } }}>
      <Grid container spacing={2}>
        {availableMetrics.map((m) => {
          const cd = chartDataMap[m.key];
          if (!cd || cd.x.length < 2) return null;
          const lastVal = cd.y[cd.y.length - 1];
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
                      tickNumber: 5,
                      tickLabelStyle: { fontSize: 10 },
                      valueFormatter: (v: Date) => {
                        const rangeMs =
                          cd.x[cd.x.length - 1].getTime() - cd.x[0].getTime();
                        return formatTickLabel(v, rangeMs);
                      },
                    },
                  ]}
                  yAxis={[
                    {
                      tickNumber: 6,
                      valueFormatter:
                        m.format === 'pct'
                          ? (v: number | null) =>
                              v != null ? `${v.toFixed(1)}%` : ''
                          : undefined,
                    },
                  ]}
                  series={[
                    {
                      data: cd.y,
                      color: m.color,
                      showMark: false,
                    },
                  ]}
                  grid={{ vertical: true, horizontal: true }}
                  height={200}
                  margin={{ left: 60, right: 16, top: 8, bottom: 36 }}
                  hideLegend
                />
              </Paper>
            </Grid>
          );
        })}
      </Grid>
    </Box>
  );
}
