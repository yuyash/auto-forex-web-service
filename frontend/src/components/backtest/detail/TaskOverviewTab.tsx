import { useEffect, useState } from 'react';

import {
  Box,
  Paper,
  Typography,
  Alert,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  CircularProgress,
  type SelectChangeEvent,
} from '@mui/material';
import Grid from '@mui/material/Grid';
import { MetricCard } from '../../tasks/display/MetricCard';
import { EquityCurveChart } from '../../tasks/charts/EquityCurveChart';
import { backtestTasksApi } from '../../../services/api/backtestTasks';
import type { BacktestTask } from '../../../types/backtestTask';
import { TaskStatus } from '../../../types/common';
import type { TaskResults } from '../../../types/results';
import type { ExecutionMetricsCheckpoint } from '../../../types/execution';
import {
  TrendingUp as TrendingUpIcon,
  ShowChart as ShowChartIcon,
  SwapHoriz as SwapHorizIcon,
  TrendingDown as TrendingDownIcon,
} from '@mui/icons-material';
import { durationMsBetween, formatDurationMs } from '../../../utils/duration';

interface EquityPoint {
  timestamp: string;
  balance: number;
}

interface TaskOverviewTabProps {
  task: BacktestTask;
  results?: TaskResults | null;
}

type DateRange = 'all' | '1m' | '3m' | '6m' | '1y';

export function TaskOverviewTab({ task, results }: TaskOverviewTabProps) {
  const [dateRange, setDateRange] = useState<DateRange>('all');
  const [equityCurve, setEquityCurve] = useState<EquityPoint[]>([]);
  const [equityCurveLoading, setEquityCurveLoading] = useState(false);
  const [equityCurveError, setEquityCurveError] = useState<string | null>(null);

  const [metricsCheckpoint, setMetricsCheckpoint] =
    useState<ExecutionMetricsCheckpoint | null>(null);
  const [metricsCheckpointLoading, setMetricsCheckpointLoading] =
    useState(false);
  const [metricsCheckpointError, setMetricsCheckpointError] = useState<
    string | null
  >(null);

  const metrics = results?.metrics ?? null;

  const handleDateRangeChange = (event: SelectChangeEvent<DateRange>) => {
    setDateRange(event.target.value as DateRange);
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString();
  };

  const startedAt =
    results?.execution?.started_at ?? task.latest_execution?.started_at ?? null;
  const completedAt =
    results?.execution?.completed_at ??
    task.latest_execution?.completed_at ??
    null;

  const durationMs =
    task.status === TaskStatus.RUNNING
      ? durationMsBetween(startedAt, new Date().toISOString())
      : durationMsBetween(startedAt, completedAt);

  // Check if task has completed execution with metrics
  const hasMetrics = task.status === TaskStatus.COMPLETED && !!metrics;

  const shouldFetchEquityCurve =
    task.status !== TaskStatus.CREATED && !!task.id && !!results?.execution?.id;
  const shouldPollEquityCurve = task.status === TaskStatus.RUNNING;

  useEffect(() => {
    if (!shouldFetchEquityCurve) {
      setMetricsCheckpoint(null);
      setMetricsCheckpointLoading(false);
      setMetricsCheckpointError(null);
      return;
    }

    let cancelled = false;

    const fetchCheckpoint = (opts?: { showLoading?: boolean }) => {
      const showLoading = opts?.showLoading ?? false;
      if (showLoading) setMetricsCheckpointLoading(true);
      setMetricsCheckpointError(null);

      backtestTasksApi
        .getMetricsCheckpoint(task.id)
        .then((resp) => {
          if (cancelled) return;
          setMetricsCheckpoint(resp?.checkpoint ?? null);
        })
        .catch((err) => {
          if (cancelled) return;
          setMetricsCheckpointError(
            err instanceof Error ? err.message : 'Failed to load live metrics'
          );
          setMetricsCheckpoint(null);
        })
        .finally(() => {
          if (cancelled) return;
          if (showLoading) setMetricsCheckpointLoading(false);
        });
    };

    fetchCheckpoint({ showLoading: true });

    let intervalId: number | null = null;
    if (shouldPollEquityCurve) {
      intervalId = window.setInterval(() => {
        fetchCheckpoint({ showLoading: false });
      }, 5000);
    }

    return () => {
      cancelled = true;
      if (intervalId !== null) window.clearInterval(intervalId);
    };
  }, [shouldFetchEquityCurve, shouldPollEquityCurve, task.id]);

  useEffect(() => {
    if (!shouldFetchEquityCurve) {
      setEquityCurve([]);
      setEquityCurveLoading(false);
      setEquityCurveError(null);
      return;
    }

    let cancelled = false;

    const fetchEquityCurve = (opts?: { showLoading?: boolean }) => {
      const showLoading = opts?.showLoading ?? false;
      if (showLoading) {
        setEquityCurveLoading(true);
      }

      setEquityCurveError(null);

      backtestTasksApi
        .getEquityCurve(task.id)
        .then((resp) => {
          if (cancelled) return;
          setEquityCurve(
            Array.isArray(resp.equity_curve) ? resp.equity_curve : []
          );
        })
        .catch((err) => {
          if (cancelled) return;
          setEquityCurveError(
            err instanceof Error ? err.message : 'Failed to load equity curve'
          );
          setEquityCurve([]);
        })
        .finally(() => {
          if (cancelled) return;
          if (showLoading) setEquityCurveLoading(false);
        });
    };

    // Initial fetch
    fetchEquityCurve({ showLoading: true });

    let intervalId: number | null = null;
    if (shouldPollEquityCurve) {
      intervalId = window.setInterval(() => {
        fetchEquityCurve({ showLoading: false });
      }, 5000);
    }

    return () => {
      cancelled = true;
      if (intervalId !== null) {
        window.clearInterval(intervalId);
      }
    };
  }, [
    shouldFetchEquityCurve,
    shouldPollEquityCurve,
    task.id,
    results?.execution?.id,
  ]);

  // Filter equity curve data based on selected date range
  const getFilteredEquityCurve = () => {
    if (!equityCurve || equityCurve.length === 0) return [];

    if (dateRange === 'all') {
      return equityCurve;
    }

    const now = new Date();
    const cutoffDate = new Date(now);

    switch (dateRange) {
      case '1m':
        cutoffDate.setMonth(now.getMonth() - 1);
        break;
      case '3m':
        cutoffDate.setMonth(now.getMonth() - 3);
        break;
      case '6m':
        cutoffDate.setMonth(now.getMonth() - 6);
        break;
      case '1y':
        cutoffDate.setFullYear(now.getFullYear() - 1);
        break;
    }

    return equityCurve.filter(
      (point) => new Date(point.timestamp) >= cutoffDate
    );
  };

  if (task.status === TaskStatus.CREATED) {
    return (
      <Box sx={{ px: 3 }}>
        <Alert severity="info">
          This task has not been started yet. Start the task to see results.
        </Alert>
      </Box>
    );
  }

  if (task.status === TaskStatus.RUNNING) {
    const live = (results?.live ?? null) as Record<string, unknown> | null;
    const toNumber = (value: unknown): number | null => {
      if (value === null || value === undefined) return null;
      const n = typeof value === 'number' ? value : Number(value);
      return Number.isFinite(n) ? n : null;
    };

    const progress = toNumber(live?.progress);

    return (
      <Box sx={{ px: 3 }}>
        <Alert severity="info">
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <CircularProgress size={16} />
            <Typography variant="body2">
              Backtest is running.
              {progress !== null && progress > 0
                ? ` Progress: ${progress}%.`
                : ''}
            </Typography>
          </Box>
        </Alert>

        <Paper sx={{ p: 2, mt: 3, mb: 3, bgcolor: 'grey.50' }}>
          <Typography variant="subtitle2" color="text.secondary" gutterBottom>
            Backtest Period
          </Typography>
          <Typography variant="body1">
            {formatDate(task.start_time)} → {formatDate(task.end_time)}
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
            {task.status === TaskStatus.RUNNING ? 'Elapsed' : 'Duration'}:{' '}
            {durationMs !== null ? formatDurationMs(durationMs) : '—'}
          </Typography>
        </Paper>

        {metricsCheckpointError && (
          <Alert severity="warning" sx={{ mb: 3 }}>
            Failed to load live metrics. {metricsCheckpointError}
          </Alert>
        )}

        {!metricsCheckpoint && (
          <Alert severity="info" sx={{ mb: 3 }}>
            Waiting for performance metrics… Live details (equity curve, trades,
            events) update while the task runs.
          </Alert>
        )}

        <Grid container spacing={3} sx={{ mb: 4 }}>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <MetricCard
              title="Total Return"
              value={
                metricsCheckpoint
                  ? `${parseFloat(metricsCheckpoint.total_return).toFixed(2)}%`
                  : '—'
              }
              icon={<TrendingUpIcon />}
              color={
                metricsCheckpoint
                  ? parseFloat(metricsCheckpoint.total_return) >= 0
                    ? 'success'
                    : 'error'
                  : 'info'
              }
            />
          </Grid>

          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <MetricCard
              title="Win Rate"
              value={
                metricsCheckpoint
                  ? `${parseFloat(metricsCheckpoint.win_rate).toFixed(2)}%`
                  : '—'
              }
              icon={<ShowChartIcon />}
              color={metricsCheckpoint ? 'primary' : 'info'}
            />
          </Grid>

          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <MetricCard
              title="Total Trades"
              value={
                metricsCheckpoint
                  ? metricsCheckpoint.total_trades.toString()
                  : '—'
              }
              icon={<SwapHorizIcon />}
              color={metricsCheckpoint ? 'info' : 'info'}
            />
          </Grid>

          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <MetricCard
              title="Max Drawdown"
              value={
                metricsCheckpoint
                  ? `${parseFloat(metricsCheckpoint.max_drawdown).toFixed(2)}%`
                  : '—'
              }
              icon={<TrendingDownIcon />}
              color={metricsCheckpoint ? 'warning' : 'info'}
            />
          </Grid>
        </Grid>

        <Paper sx={{ p: 3, mt: 3 }}>
          <Box
            sx={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              mb: 3,
            }}
          >
            <Typography variant="h6">Equity Curve</Typography>

            <FormControl size="small" sx={{ minWidth: 120 }}>
              <InputLabel id="date-range-label">Date Range</InputLabel>
              <Select
                labelId="date-range-label"
                id="date-range-select"
                value={dateRange}
                label="Date Range"
                onChange={handleDateRangeChange}
              >
                <MenuItem value="all">All Time</MenuItem>
                <MenuItem value="1m">Last Month</MenuItem>
                <MenuItem value="3m">Last 3 Months</MenuItem>
                <MenuItem value="6m">Last 6 Months</MenuItem>
                <MenuItem value="1y">Last Year</MenuItem>
              </Select>
            </FormControl>
          </Box>

          {equityCurveLoading && (
            <Alert severity="info" sx={{ mb: 2 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <CircularProgress size={16} />
                <Typography variant="body2">Loading equity curve…</Typography>
              </Box>
            </Alert>
          )}

          {equityCurveError && (
            <Alert severity="warning" sx={{ mb: 2 }}>
              Failed to load equity curve. {equityCurveError}
            </Alert>
          )}

          <EquityCurveChart data={getFilteredEquityCurve()} height={400} />
        </Paper>
      </Box>
    );
  }

  if (task.status === TaskStatus.FAILED) {
    const errorMessage = results?.execution?.error_message;
    return (
      <Box sx={{ px: 3 }}>
        <Alert severity="error">
          This task execution failed.{' '}
          {errorMessage && (
            <>
              <br />
              Error: {errorMessage}
            </>
          )}
        </Alert>
      </Box>
    );
  }

  if (!hasMetrics) {
    return (
      <Box sx={{ px: 3 }}>
        <Alert severity="warning">
          No metrics available for this task. The execution may have completed
          without generating results.
        </Alert>
      </Box>
    );
  }

  return (
    <Box sx={{ px: 3 }}>
      {/* Backtest Period */}
      <Paper sx={{ p: 2, mb: 3, bgcolor: 'grey.50' }}>
        <Typography variant="subtitle2" color="text.secondary" gutterBottom>
          Backtest Period
        </Typography>
        <Typography variant="body1">
          {formatDate(task.start_time)} → {formatDate(task.end_time)}
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
          Duration: {durationMs !== null ? formatDurationMs(durationMs) : '—'}
        </Typography>
      </Paper>

      {/* Key Metrics Grid */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <MetricCard
            title="Total Return"
            value={`${parseFloat(metrics.total_return).toFixed(2)}%`}
            icon={<TrendingUpIcon />}
            color={parseFloat(metrics.total_return) >= 0 ? 'success' : 'error'}
          />
        </Grid>

        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <MetricCard
            title="Win Rate"
            value={`${parseFloat(metrics.win_rate).toFixed(2)}%`}
            icon={<ShowChartIcon />}
            color="primary"
          />
        </Grid>

        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <MetricCard
            title="Total Trades"
            value={metrics.total_trades.toString()}
            icon={<SwapHorizIcon />}
            color="info"
          />
        </Grid>

        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <MetricCard
            title="Max Drawdown"
            value={`${parseFloat(metrics.max_drawdown).toFixed(2)}%`}
            icon={<TrendingDownIcon />}
            color="warning"
          />
        </Grid>
      </Grid>

      {/* Equity Curve Chart */}
      <Paper sx={{ p: 3 }}>
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            mb: 3,
          }}
        >
          <Typography variant="h6">Equity Curve</Typography>

          <FormControl size="small" sx={{ minWidth: 120 }}>
            <InputLabel id="date-range-label">Date Range</InputLabel>
            <Select
              labelId="date-range-label"
              id="date-range-select"
              value={dateRange}
              label="Date Range"
              onChange={handleDateRangeChange}
            >
              <MenuItem value="all">All Time</MenuItem>
              <MenuItem value="1m">Last Month</MenuItem>
              <MenuItem value="3m">Last 3 Months</MenuItem>
              <MenuItem value="6m">Last 6 Months</MenuItem>
              <MenuItem value="1y">Last Year</MenuItem>
            </Select>
          </FormControl>
        </Box>

        {equityCurveLoading && (
          <Alert severity="info" sx={{ mb: 2 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <CircularProgress size={16} />
              <Typography variant="body2">Loading equity curve…</Typography>
            </Box>
          </Alert>
        )}

        {equityCurveError && (
          <Alert severity="warning" sx={{ mb: 2 }}>
            Failed to load equity curve. {equityCurveError}
          </Alert>
        )}

        <EquityCurveChart data={getFilteredEquityCurve()} height={400} />
      </Paper>

      {/* Additional Metrics */}
      {(metrics.sharpe_ratio || metrics.profit_factor) && (
        <Paper sx={{ p: 3, mt: 3 }}>
          <Typography variant="h6" sx={{ mb: 2 }}>
            Additional Metrics
          </Typography>

          <Grid container spacing={3}>
            {metrics.sharpe_ratio && (
              <Grid size={{ xs: 12, sm: 6, md: 4 }}>
                <Box>
                  <Typography variant="body2" color="text.secondary">
                    Sharpe Ratio
                  </Typography>
                  <Typography variant="h5">
                    {parseFloat(metrics.sharpe_ratio).toFixed(2)}
                  </Typography>
                </Box>
              </Grid>
            )}

            {metrics.profit_factor && (
              <Grid size={{ xs: 12, sm: 6, md: 4 }}>
                <Box>
                  <Typography variant="body2" color="text.secondary">
                    Profit Factor
                  </Typography>
                  <Typography variant="h5">
                    {parseFloat(metrics.profit_factor).toFixed(2)}
                  </Typography>
                </Box>
              </Grid>
            )}

            {metrics.average_win && (
              <Grid size={{ xs: 12, sm: 6, md: 4 }}>
                <Box>
                  <Typography variant="body2" color="text.secondary">
                    Average Win
                  </Typography>
                  <Typography variant="h5">
                    ${parseFloat(metrics.average_win).toFixed(2)}
                  </Typography>
                </Box>
              </Grid>
            )}

            {metrics.average_loss && (
              <Grid size={{ xs: 12, sm: 6, md: 4 }}>
                <Box>
                  <Typography variant="body2" color="text.secondary">
                    Average Loss
                  </Typography>
                  <Typography variant="h5" color="error.main">
                    ${parseFloat(metrics.average_loss).toFixed(2)}
                  </Typography>
                </Box>
              </Grid>
            )}

            <Grid size={{ xs: 12, sm: 6, md: 4 }}>
              <Box>
                <Typography variant="body2" color="text.secondary">
                  Winning Trades
                </Typography>
                <Typography variant="h5" color="success.main">
                  {metrics.winning_trades}
                </Typography>
              </Box>
            </Grid>

            <Grid size={{ xs: 12, sm: 6, md: 4 }}>
              <Box>
                <Typography variant="body2" color="text.secondary">
                  Losing Trades
                </Typography>
                <Typography variant="h5" color="error.main">
                  {metrics.losing_trades}
                </Typography>
              </Box>
            </Grid>
          </Grid>
        </Paper>
      )}
    </Box>
  );
}
