/**
 * ExecutionComparisonDialog
 *
 * Full-screen dialog that compares multiple task executions side-by-side.
 * Shows: task config diff, strategy config diff, result metrics diff,
 * and overlaid time-series metric charts.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Alert,
  AppBar,
  Box,
  CircularProgress,
  Dialog,
  Grid,
  IconButton,
  Paper,
  Slide,
  Tab,
  Tabs,
  ToggleButton,
  ToggleButtonGroup,
  Toolbar,
  Tooltip,
  Typography,
} from '@mui/material';
import type { TransitionProps } from '@mui/material/transitions';
import {
  Close as CloseIcon,
  ExpandMore as ExpandMoreIcon,
  ExpandLess as ExpandLessIcon,
} from '@mui/icons-material';
import { LineChart } from '@mui/x-charts/LineChart';
import React from 'react';
import type { TaskExecution } from '../../../types/execution';
import { TaskType } from '../../../types/common';
import {
  fetchPaginatedMetrics,
  type MetricPoint,
} from '../../../utils/fetchMetrics';

/** Palette for up to 10 executions */
const EXEC_COLORS = [
  '#1976d2',
  '#d32f2f',
  '#2e7d32',
  '#f57c00',
  '#7b1fa2',
  '#00838f',
  '#c2185b',
  '#455a64',
  '#6d4c41',
  '#00695c',
];

const INTERVAL_OPTIONS = [
  { value: 0, label: 'Auto' },
  { value: 1, label: '1m' },
  { value: 5, label: '5m' },
  { value: 15, label: '15m' },
  { value: 60, label: '1h' },
  { value: 240, label: '4h' },
  { value: 1440, label: '1d' },
] as const;

const CHART_METRICS: {
  key: string;
  format?: 'pct' | 'int' | 'currency';
}[] = [
  { key: 'current_balance', format: 'currency' },
  { key: 'total_pnl', format: 'currency' },
  { key: 'realized_pnl', format: 'currency' },
  { key: 'unrealized_pnl', format: 'currency' },
  { key: 'total_return', format: 'pct' },
  { key: 'margin_ratio', format: 'pct' },
  { key: 'open_positions', format: 'int' },
  { key: 'closed_positions', format: 'int' },
  { key: 'total_trades', format: 'int' },
  { key: 'win_rate', format: 'pct' },
  { key: 'winning_trades', format: 'int' },
  { key: 'losing_trades', format: 'int' },
  { key: 'ticks_processed', format: 'int' },
];

const RATIO_KEYS = new Set(['margin_ratio']);
const CHART_HEIGHT = 220;

interface ExecutionComparisonDialogProps {
  open: boolean;
  onClose: () => void;
  executions: TaskExecution[];
  taskId: string;
  taskType: TaskType;
}

const SlideUp = React.forwardRef(function Transition(
  props: TransitionProps & { children: React.ReactElement },
  ref: React.Ref<unknown>
) {
  return <Slide direction="up" ref={ref} {...props} />;
});

/** Compute auto interval based on the total time range in seconds. */
function computeAutoInterval(rangeSec: number): number {
  const DAY = 86_400;
  if (rangeSec <= 14 * DAY) return 1;
  if (rangeSec <= 31 * DAY) return 5;
  if (rangeSec <= 93 * DAY) return 15;
  if (rangeSec <= 183 * DAY) return 60;
  if (rangeSec <= 366 * DAY) return 240;
  return 1440;
}

function formatYLabel(v: number, format?: 'pct' | 'int' | 'currency'): string {
  if (format === 'pct') return `${v.toFixed(2)}%`;
  if (format === 'currency') return v.toFixed(2);
  if (format === 'int') return Math.round(v).toLocaleString();
  return v.toFixed(2);
}

function formatTickLabel(date: Date, rangeMs: number): string {
  const DAY = 86_400_000;
  if (rangeMs <= DAY) {
    return date.toLocaleTimeString(undefined, {
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    });
  }
  if (rangeMs <= 7 * DAY) {
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

/** Flatten a nested object into dot-separated key-value pairs. */
function flattenObject(
  obj: Record<string, unknown>,
  prefix = ''
): Record<string, string> {
  const result: Record<string, string> = {};
  for (const [k, v] of Object.entries(obj)) {
    const key = prefix ? `${prefix}.${k}` : k;
    if (v != null && typeof v === 'object' && !Array.isArray(v)) {
      Object.assign(result, flattenObject(v as Record<string, unknown>, key));
    } else {
      result[key] = v == null ? '-' : String(v);
    }
  }
  return result;
}

/** Result metric keys to display in the results comparison. */
const RESULT_KEYS = [
  'total_return',
  'total_pnl',
  'total_pnl_quote',
  'realized_pnl_quote',
  'unrealized_pnl_quote',
  'total_trades',
  'winning_trades',
  'losing_trades',
  'win_rate',
  'max_drawdown',
  'sharpe_ratio',
  'profit_factor',
  'average_win',
  'average_loss',
  'pnl_currency',
  'quote_currency',
];

export function ExecutionComparisonDialog({
  open,
  onClose,
  executions,
  taskId,
  taskType,
}: ExecutionComparisonDialogProps) {
  const { t } = useTranslation('common');
  const [tabIndex, setTabIndex] = useState(0);
  const [interval, setInterval_] = useState(0);
  const [metricsData, setMetricsData] = useState<Map<string, MetricPoint[]>>(
    new Map()
  );
  const [metricsLoading, setMetricsLoading] = useState(false);
  const [metricsError, setMetricsError] = useState<string | null>(null);
  const mountedRef = useRef(true);

  // Sort executions by execution_number for consistent ordering
  const sorted = useMemo(
    () =>
      [...executions].sort((a, b) => a.execution_number - b.execution_number),
    [executions]
  );

  // Compute per-execution intervals so each execution uses a granularity
  // appropriate for its own duration, not the union range of all executions.
  const perExecIntervals = useMemo(() => {
    const map = new Map<string, number>();
    for (const exec of sorted) {
      if (interval > 0) {
        map.set(exec.id, interval);
        continue;
      }
      const start = exec.started_at
        ? new Date(exec.started_at).getTime() / 1000
        : 0;
      const end = exec.completed_at
        ? new Date(exec.completed_at).getTime() / 1000
        : Date.now() / 1000;
      if (start > 0 && end > start) {
        map.set(exec.id, computeAutoInterval(end - start));
      } else {
        map.set(exec.id, 1);
      }
    }
    return map;
  }, [sorted, interval]);

  // Fetch metrics for all executions
  const fetchAllMetrics = useCallback(async () => {
    setMetricsLoading(true);
    setMetricsError(null);
    try {
      const entries = await Promise.all(
        sorted.map(async (exec) => {
          const execInterval = perExecIntervals.get(exec.id) ?? 1;
          const points = await fetchPaginatedMetrics({
            taskId,
            taskType,
            executionRunId: exec.id,
            interval: execInterval > 1 ? execInterval : undefined,
            pageSize: 500,
          });
          return [exec.id, points] as const;
        })
      );
      if (mountedRef.current) {
        setMetricsData(new Map(entries));
      }
    } catch {
      if (mountedRef.current) {
        setMetricsError(t('comparison.error'));
      }
    } finally {
      if (mountedRef.current) {
        setMetricsLoading(false);
      }
    }
  }, [sorted, taskId, taskType, perExecIntervals, t]);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    if (open && tabIndex === 3) {
      fetchAllMetrics();
    }
  }, [open, tabIndex, fetchAllMetrics]);

  // Preload metrics when dialog opens
  useEffect(() => {
    if (open) {
      fetchAllMetrics();
    }
  }, [open]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <Dialog
      open={open}
      onClose={onClose}
      fullScreen
      TransitionComponent={SlideUp}
    >
      <AppBar sx={{ position: 'relative' }} color="default" elevation={1}>
        <Toolbar
          sx={{
            flexDirection: { xs: 'column', sm: 'row' },
            alignItems: { xs: 'flex-start', sm: 'center' },
            gap: 1,
            py: { xs: 1, sm: 0 },
          }}
        >
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              width: { xs: '100%', sm: 'auto' },
            }}
          >
            <IconButton edge="start" onClick={onClose} aria-label="close">
              <CloseIcon />
            </IconButton>
            <Typography sx={{ ml: 1 }} variant="h6">
              {t('comparison.title')}
            </Typography>
          </Box>
          {/* Legend chips */}
          <Box
            sx={{
              display: 'flex',
              gap: 0.5,
              flexWrap: 'wrap',
              pl: { xs: 1, sm: 0 },
            }}
          >
            {sorted.map((exec, i) => (
              <Box
                key={exec.id}
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 0.5,
                  px: 1,
                  py: 0.25,
                  borderRadius: 1,
                  bgcolor: 'action.hover',
                }}
              >
                <Box
                  sx={{
                    width: 12,
                    height: 12,
                    borderRadius: '50%',
                    bgcolor: EXEC_COLORS[i % EXEC_COLORS.length],
                  }}
                />
                <Typography variant="caption">
                  #{exec.execution_number}
                </Typography>
              </Box>
            ))}
          </Box>
        </Toolbar>
        <Tabs
          value={tabIndex}
          onChange={(_e, v) => setTabIndex(v)}
          sx={{ px: 2 }}
        >
          <Tab label={t('comparison.taskConfig')} />
          <Tab label={t('comparison.strategyConfig')} />
          <Tab label={t('comparison.results')} />
          <Tab label={t('comparison.metricsOverlay')} />
        </Tabs>
      </AppBar>

      <Box sx={{ flex: 1, overflow: 'auto', p: 2 }}>
        {tabIndex === 0 && (
          <ConfigComparisonPanel executions={sorted} type="task" />
        )}
        {tabIndex === 1 && (
          <ConfigComparisonPanel executions={sorted} type="strategy" />
        )}
        {tabIndex === 2 && <ResultsComparisonPanel executions={sorted} />}
        {tabIndex === 3 && (
          <MetricsOverlayPanel
            executions={sorted}
            metricsData={metricsData}
            isLoading={metricsLoading}
            error={metricsError}
            interval={interval}
            onIntervalChange={setInterval_}
            onRefresh={fetchAllMetrics}
          />
        )}
      </Box>
    </Dialog>
  );
}

/* ------------------------------------------------------------------ */
/*  Config Comparison Panel (task config or strategy config)          */
/* ------------------------------------------------------------------ */

function ConfigComparisonPanel({
  executions,
  type,
}: {
  executions: TaskExecution[];
  type: 'task' | 'strategy';
}) {
  const { t } = useTranslation('common');

  const configs = useMemo(() => {
    return executions.map((exec) => {
      const raw =
        type === 'task'
          ? (exec.task_config ?? {})
          : (exec.strategy_config ?? {});
      return flattenObject(raw as Record<string, unknown>);
    });
  }, [executions, type]);

  // Collect all unique keys across all configs
  const allKeys = useMemo(() => {
    const keys = new Set<string>();
    for (const cfg of configs) {
      for (const k of Object.keys(cfg)) keys.add(k);
    }
    return [...keys].sort();
  }, [configs]);

  // Determine which keys differ
  const diffKeys = useMemo(() => {
    return new Set(
      allKeys.filter((key) => {
        const values = configs.map((c) => c[key] ?? '-');
        return values.some((v) => v !== values[0]);
      })
    );
  }, [allKeys, configs]);

  const [showAll, setShowAll] = useState(false);
  const displayKeys = showAll
    ? allKeys
    : allKeys.filter((k) => diffKeys.has(k));

  if (allKeys.length === 0) {
    return <Alert severity="info">{t('comparison.noSnapshot')}</Alert>;
  }

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', mb: 2, gap: 1 }}>
        <Typography variant="subtitle2" color="text.secondary">
          {diffKeys.size > 0
            ? `${diffKeys.size} ${t('comparison.configDiff').toLowerCase()}`
            : t('comparison.noDifferences')}
        </Typography>
        <IconButton size="small" onClick={() => setShowAll((v) => !v)}>
          {showAll ? <ExpandLessIcon /> : <ExpandMoreIcon />}
        </IconButton>
        <Typography variant="caption" color="text.secondary">
          {showAll ? 'Show diff only' : 'Show all'}
        </Typography>
      </Box>

      {displayKeys.length === 0 && !showAll && (
        <Typography color="text.secondary">
          {t('comparison.noDifferences')}
        </Typography>
      )}

      <Box sx={{ overflowX: 'auto' }}>
        <Box
          component="table"
          sx={{
            width: '100%',
            borderCollapse: 'collapse',
            '& th, & td': {
              border: '1px solid',
              borderColor: 'divider',
              px: 1.5,
              py: 0.75,
              fontSize: '0.8125rem',
              verticalAlign: 'top',
            },
            '& th': {
              bgcolor: 'action.hover',
              fontWeight: 600,
              whiteSpace: 'nowrap',
            },
          }}
        >
          <thead>
            <tr>
              <th style={{ minWidth: 180 }}>Key</th>
              {executions.map((exec, i) => (
                <th key={exec.id} style={{ minWidth: 160 }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                    <Box
                      sx={{
                        width: 10,
                        height: 10,
                        borderRadius: '50%',
                        bgcolor: EXEC_COLORS[i % EXEC_COLORS.length],
                        flexShrink: 0,
                      }}
                    />
                    {t('comparison.execution', {
                      number: exec.execution_number,
                    })}
                  </Box>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {displayKeys.map((key) => {
              const isDiff = diffKeys.has(key);
              return (
                <tr key={key}>
                  <td>
                    <Typography
                      variant="body2"
                      fontWeight={isDiff ? 600 : 400}
                      sx={{ fontFamily: 'monospace', fontSize: '0.75rem' }}
                    >
                      {key
                        .replace(/^parameters\./, '')
                        .replace(/_/g, ' ')
                        .replace(/\b\w/g, (c) => c.toUpperCase())}
                    </Typography>
                  </td>
                  {configs.map((cfg, i) => (
                    <td
                      key={executions[i].id}
                      style={{
                        backgroundColor: isDiff
                          ? 'rgba(255,235,59,0.08)'
                          : undefined,
                      }}
                    >
                      <Typography
                        variant="body2"
                        sx={{
                          fontFamily: 'monospace',
                          fontSize: '0.75rem',
                          wordBreak: 'break-all',
                        }}
                      >
                        {cfg[key] ?? '-'}
                      </Typography>
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </Box>
      </Box>
    </Box>
  );
}

/* ------------------------------------------------------------------ */
/*  Results Comparison Panel                                          */
/* ------------------------------------------------------------------ */

function ResultsComparisonPanel({
  executions,
}: {
  executions: TaskExecution[];
}) {
  const { t } = useTranslation('common');

  const resultRows = useMemo(() => {
    return RESULT_KEYS.map((key) => {
      const values = executions.map((exec) => {
        const v = exec.metrics?.[key];
        if (v == null) return '-';
        return String(v);
      });
      return { key, values };
    }).filter((row) => row.values.some((v) => v !== '-'));
  }, [executions]);

  if (resultRows.length === 0) {
    return <Alert severity="info">{t('comparison.noSnapshot')}</Alert>;
  }

  return (
    <Box sx={{ overflowX: 'auto' }}>
      <Box
        component="table"
        sx={{
          width: '100%',
          borderCollapse: 'collapse',
          '& th, & td': {
            border: '1px solid',
            borderColor: 'divider',
            px: 1.5,
            py: 0.75,
            fontSize: '0.8125rem',
          },
          '& th': {
            bgcolor: 'action.hover',
            fontWeight: 600,
            whiteSpace: 'nowrap',
          },
        }}
      >
        <thead>
          <tr>
            <th style={{ minWidth: 180 }}>Metric</th>
            {executions.map((exec, i) => (
              <th key={exec.id} style={{ minWidth: 140 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                  <Box
                    sx={{
                      width: 10,
                      height: 10,
                      borderRadius: '50%',
                      bgcolor: EXEC_COLORS[i % EXEC_COLORS.length],
                      flexShrink: 0,
                    }}
                  />
                  {t('comparison.execution', {
                    number: exec.execution_number,
                  })}
                </Box>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {resultRows.map(({ key, values }) => {
            const allSame = values.every((v) => v === values[0]);
            return (
              <tr key={key}>
                <td>
                  <Typography
                    variant="body2"
                    fontWeight={allSame ? 400 : 600}
                    sx={{ fontFamily: 'monospace', fontSize: '0.75rem' }}
                  >
                    {t(`metrics.${key}`, {
                      defaultValue: key.replace(/_/g, ' '),
                    })}
                  </Typography>
                </td>
                {values.map((v, i) => {
                  const num = parseFloat(v);
                  const isPnl =
                    key.includes('pnl') ||
                    key === 'total_return' ||
                    key === 'average_win' ||
                    key === 'average_loss';
                  const color =
                    isPnl && !isNaN(num)
                      ? num >= 0
                        ? 'success.main'
                        : 'error.main'
                      : undefined;
                  // Format value with currency/percent suffix
                  let display = v;
                  if (v !== '-' && !isNaN(num)) {
                    const exec = executions[i];
                    const acctCcy = exec.metrics?.pnl_currency || '';
                    const quoteCcy = exec.metrics?.quote_currency || '';
                    if (
                      key === 'total_return' ||
                      key === 'win_rate' ||
                      key === 'max_drawdown'
                    ) {
                      display = `${num >= 0 ? '+' : ''}${num.toFixed(2)}%`;
                    } else if (key.endsWith('_quote')) {
                      display = `${num >= 0 ? '+' : ''}${num.toFixed(2)}${quoteCcy ? ` ${quoteCcy}` : ''}`;
                    } else if (
                      key.includes('pnl') ||
                      key === 'average_win' ||
                      key === 'average_loss'
                    ) {
                      display = `${num >= 0 ? '+' : ''}${num.toFixed(2)}${acctCcy ? ` ${acctCcy}` : ''}`;
                    }
                  }
                  return (
                    <td
                      key={executions[i].id}
                      style={{
                        textAlign: 'right',
                        backgroundColor: allSame
                          ? undefined
                          : 'rgba(255,235,59,0.08)',
                      }}
                    >
                      <Typography
                        variant="body2"
                        color={color}
                        sx={{
                          fontFamily: 'monospace',
                          fontSize: '0.75rem',
                        }}
                      >
                        {display}
                      </Typography>
                    </td>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
      </Box>
    </Box>
  );
}

/* ------------------------------------------------------------------ */
/*  Metrics Overlay Panel                                             */
/* ------------------------------------------------------------------ */

function MetricsOverlayPanel({
  executions,
  metricsData,
  isLoading,
  error,
  interval,
  onIntervalChange,
  onRefresh,
}: {
  executions: TaskExecution[];
  metricsData: Map<string, MetricPoint[]>;
  isLoading: boolean;
  error: string | null;
  interval: number;
  onIntervalChange: (v: number) => void;
  onRefresh: () => void;
}) {
  const { t } = useTranslation('common');

  // Determine which metric keys have data across any execution
  const availableMetrics = useMemo(() => {
    const keysWithData = new Set<string>();
    for (const points of metricsData.values()) {
      for (const point of points) {
        for (const [k, v] of Object.entries(point.metrics)) {
          if (v != null && v !== '' && !isNaN(Number(v))) {
            keysWithData.add(k);
          }
        }
      }
    }
    return CHART_METRICS.filter((m) => keysWithData.has(m.key));
  }, [metricsData]);

  // Build chart data: for each metric, build series per execution
  const chartDataMap = useMemo(() => {
    const map: Record<string, { execIndex: number; x: Date[]; y: number[] }[]> =
      {};

    for (const m of availableMetrics) {
      const series: { execIndex: number; x: Date[]; y: number[] }[] = [];
      const scale = RATIO_KEYS.has(m.key) ? 100 : 1;

      executions.forEach((exec, idx) => {
        const points = metricsData.get(exec.id) ?? [];
        const x: Date[] = [];
        const y: number[] = [];
        for (const point of points) {
          const val = point.metrics[m.key];
          if (val != null && val !== '') {
            const num = Number(val);
            if (!isNaN(num)) {
              x.push(new Date(point.t * 1000));
              y.push(num * scale);
            }
          }
        }
        if (x.length >= 2) {
          series.push({ execIndex: idx, x, y });
        }
      });

      if (series.length > 0) {
        map[m.key] = series;
      }
    }
    return map;
  }, [availableMetrics, executions, metricsData]);

  if (isLoading && metricsData.size === 0) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return <Alert severity="error">{error}</Alert>;
  }

  return (
    <Box>
      {/* Granularity toolbar */}
      <Box sx={{ mb: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
        <ToggleButtonGroup
          value={interval}
          exclusive
          onChange={(_e, val) => {
            if (val !== null) onIntervalChange(val);
          }}
          size="small"
          aria-label="Granularity"
        >
          {INTERVAL_OPTIONS.map((opt) => (
            <ToggleButton
              key={opt.value}
              value={opt.value}
              sx={{ px: 1.5, py: 0.25, fontSize: '0.75rem' }}
            >
              {opt.label}
            </ToggleButton>
          ))}
        </ToggleButtonGroup>
        <Tooltip title="Refresh">
          <span>
            <IconButton size="small" onClick={onRefresh} disabled={isLoading}>
              {isLoading ? (
                <CircularProgress size={16} />
              ) : (
                <Typography variant="caption">↻</Typography>
              )}
            </IconButton>
          </span>
        </Tooltip>
      </Box>

      {availableMetrics.length === 0 && (
        <Typography color="text.secondary">{t('metrics.noData')}</Typography>
      )}

      <Grid container spacing={2}>
        {availableMetrics.map((m) => {
          const series = chartDataMap[m.key];
          if (!series || series.length === 0) return null;

          // Merge all x values to compute a shared domain
          const allX = series.flatMap((s) => s.x);
          const minX = new Date(Math.min(...allX.map((d) => d.getTime())));
          const maxX = new Date(Math.max(...allX.map((d) => d.getTime())));
          const rangeMs = maxX.getTime() - minX.getTime();

          return (
            <Grid key={m.key} size={{ xs: 12, md: 6 }}>
              <Paper
                variant="outlined"
                sx={{ p: 1.5, height: CHART_HEIGHT + 40, overflow: 'hidden' }}
              >
                <Typography variant="subtitle2" sx={{ mb: 0.5 }}>
                  {t(`metrics.${m.key}`, {
                    defaultValue: m.key.replace(/_/g, ' '),
                  })}
                </Typography>
                <LineChart
                  xAxis={[
                    {
                      scaleType: 'time' as const,
                      data: allX.length > 0 ? [minX, maxX] : undefined,
                      min: minX,
                      max: maxX,
                      tickNumber: 8,
                      tickLabelStyle: { fontSize: 10 },
                      valueFormatter: (v: Date, ctx: { location: string }) => {
                        if (ctx.location === 'tooltip') {
                          return v.toLocaleString();
                        }
                        return formatTickLabel(v, rangeMs);
                      },
                    },
                  ]}
                  yAxis={[
                    {
                      position: 'right',
                      width: 60,
                      tickNumber: 5,
                      valueFormatter: (v: number | null) =>
                        v != null ? formatYLabel(v, m.format) : '',
                    },
                  ]}
                  series={series.map((s) => ({
                    data: s.y,
                    color: EXEC_COLORS[s.execIndex % EXEC_COLORS.length],
                    showMark: false,
                    label: `#${executions[s.execIndex].execution_number}`,
                    xData: s.x,
                  }))}
                  axisHighlight={{ x: 'line', y: 'none' }}
                  grid={{ vertical: true, horizontal: true }}
                  height={CHART_HEIGHT}
                  margin={{ left: 8, right: 68, top: 8, bottom: 36 }}
                  slotProps={{
                    axisTickLabel: { style: { fontSize: 10 } },
                    legend: {
                      direction: 'row',
                      position: {
                        vertical: 'top',
                        horizontal: 'left',
                      },
                      padding: 0,
                      itemMarkWidth: 8,
                      itemMarkHeight: 8,
                      labelStyle: { fontSize: 10 },
                    } as Record<string, unknown>,
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
