import { useState } from 'react';

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
import type { BacktestTask } from '../../../types/backtestTask';
import { TaskStatus, TaskType } from '../../../types/common';
import { useTaskExecutions } from '../../../hooks/useTaskExecutions';
import {
  TrendingUp as TrendingUpIcon,
  ShowChart as ShowChartIcon,
  SwapHoriz as SwapHorizIcon,
  TrendingDown as TrendingDownIcon,
} from '@mui/icons-material';

interface EquityPoint {
  timestamp: string;
  balance: number;
}

interface LiveMetrics {
  total_return?: number;
  total_pnl?: number;
  win_rate?: number;
  winning_trades?: number;
  losing_trades?: number;
  max_drawdown?: number;
  sharpe_ratio?: number;
  profit_factor?: number;
  average_win?: number;
  average_loss?: number;
  [key: string]: string | number | undefined;
}

interface LiveResults {
  day_date: string;
  progress: number;
  days_processed: number;
  total_days: number;
  balance: number;
  total_trades: number;
  metrics: LiveMetrics;
  equity_curve: EquityPoint[];
}

interface TaskOverviewTabProps {
  task: BacktestTask;
  liveResults?: LiveResults | null;
}

type DateRange = 'all' | '1m' | '3m' | '6m' | '1y';

export function TaskOverviewTab({ task, liveResults }: TaskOverviewTabProps) {
  const [dateRange, setDateRange] = useState<DateRange>('all');

  // Fetch latest execution with full metrics
  const { data: executionsData, isLoading: executionsLoading } =
    useTaskExecutions(task.id, TaskType.BACKTEST, { page: 1, page_size: 1 });

  const latestExecution = executionsData?.results?.[0];
  const metrics = latestExecution?.metrics;

  const handleDateRangeChange = (event: SelectChangeEvent<DateRange>) => {
    setDateRange(event.target.value as DateRange);
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString();
  };

  // Check if task has completed execution with metrics
  const hasMetrics = task.status === TaskStatus.COMPLETED && metrics;

  // Filter equity curve data based on selected date range
  const getFilteredEquityCurve = () => {
    if (!metrics?.equity_curve) return [];

    if (dateRange === 'all') {
      return metrics.equity_curve;
    }

    const now = new Date();
    const cutoffDate = new Date();

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

    return metrics.equity_curve.filter(
      (point) => new Date(point.timestamp) >= cutoffDate
    );
  };

  if (executionsLoading) {
    return (
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          minHeight: '200px',
        }}
      >
        <CircularProgress />
      </Box>
    );
  }

  if (task.status === TaskStatus.CREATED) {
    return (
      <Box sx={{ px: 3 }}>
        <Alert severity="info">
          This task has not been executed yet. Start the task to see results.
        </Alert>
      </Box>
    );
  }

  if (task.status === TaskStatus.RUNNING) {
    // Show live results if available
    if (liveResults && liveResults.metrics) {
      const liveMetrics = liveResults.metrics;

      return (
        <Box sx={{ px: 3 }}>
          <Alert severity="info" sx={{ mb: 3 }}>
            <Typography variant="body2">
              <strong>Backtest in progress:</strong> Day{' '}
              {liveResults.days_processed} of {liveResults.total_days} (
              {liveResults.progress}%)
            </Typography>
            <Typography variant="body2" sx={{ mt: 1 }}>
              Current date: {liveResults.day_date} • Balance: $
              {liveResults.balance.toFixed(2)} • Trades:{' '}
              {liveResults.total_trades}
            </Typography>
          </Alert>

          {/* Live Key Metrics Grid */}
          <Grid container spacing={3} sx={{ mb: 4 }}>
            <Grid size={{ xs: 12, sm: 6, md: 3 }}>
              <MetricCard
                title="Total Return (Live)"
                value={`${parseFloat(String(liveMetrics.total_return || 0)).toFixed(2)}%`}
                icon={<TrendingUpIcon />}
                color={
                  parseFloat(String(liveMetrics.total_return || 0)) >= 0
                    ? 'success'
                    : 'error'
                }
              />
            </Grid>

            <Grid size={{ xs: 12, sm: 6, md: 3 }}>
              <MetricCard
                title="Win Rate (Live)"
                value={`${parseFloat(String(liveMetrics.win_rate || 0)).toFixed(2)}%`}
                icon={<ShowChartIcon />}
                color="primary"
              />
            </Grid>

            <Grid size={{ xs: 12, sm: 6, md: 3 }}>
              <MetricCard
                title="Total Trades (Live)"
                value={liveResults.total_trades.toString()}
                icon={<SwapHorizIcon />}
                color="info"
              />
            </Grid>

            <Grid size={{ xs: 12, sm: 6, md: 3 }}>
              <MetricCard
                title="Max Drawdown (Live)"
                value={`${parseFloat(String(liveMetrics.max_drawdown || 0)).toFixed(2)}%`}
                icon={<TrendingDownIcon />}
                color="warning"
              />
            </Grid>
          </Grid>

          {/* Live Equity Curve Chart */}
          {liveResults.equity_curve && liveResults.equity_curve.length > 0 && (
            <Paper sx={{ p: 3 }}>
              <Typography variant="h6" sx={{ mb: 3 }}>
                Equity Curve (Live - Last 100 points)
              </Typography>
              <EquityCurveChart data={liveResults.equity_curve} height={400} />
            </Paper>
          )}

          {/* Live Additional Metrics */}
          {(liveMetrics.sharpe_ratio || liveMetrics.profit_factor) && (
            <Paper sx={{ p: 3, mt: 3 }}>
              <Typography variant="h6" sx={{ mb: 2 }}>
                Additional Metrics (Live)
              </Typography>

              <Grid container spacing={3}>
                {liveMetrics.sharpe_ratio && (
                  <Grid size={{ xs: 12, sm: 6, md: 4 }}>
                    <Box>
                      <Typography variant="body2" color="text.secondary">
                        Sharpe Ratio
                      </Typography>
                      <Typography variant="h5">
                        {parseFloat(String(liveMetrics.sharpe_ratio)).toFixed(
                          2
                        )}
                      </Typography>
                    </Box>
                  </Grid>
                )}

                {liveMetrics.profit_factor && (
                  <Grid size={{ xs: 12, sm: 6, md: 4 }}>
                    <Box>
                      <Typography variant="body2" color="text.secondary">
                        Profit Factor
                      </Typography>
                      <Typography variant="h5">
                        {parseFloat(String(liveMetrics.profit_factor)).toFixed(
                          2
                        )}
                      </Typography>
                    </Box>
                  </Grid>
                )}

                {liveMetrics.average_win && (
                  <Grid size={{ xs: 12, sm: 6, md: 4 }}>
                    <Box>
                      <Typography variant="body2" color="text.secondary">
                        Average Win
                      </Typography>
                      <Typography variant="h5">
                        $
                        {parseFloat(String(liveMetrics.average_win)).toFixed(2)}
                      </Typography>
                    </Box>
                  </Grid>
                )}

                {liveMetrics.average_loss && (
                  <Grid size={{ xs: 12, sm: 6, md: 4 }}>
                    <Box>
                      <Typography variant="body2" color="text.secondary">
                        Average Loss
                      </Typography>
                      <Typography variant="h5" color="error.main">
                        $
                        {parseFloat(String(liveMetrics.average_loss)).toFixed(
                          2
                        )}
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
                      {liveMetrics.winning_trades || 0}
                    </Typography>
                  </Box>
                </Grid>

                <Grid size={{ xs: 12, sm: 6, md: 4 }}>
                  <Box>
                    <Typography variant="body2" color="text.secondary">
                      Losing Trades
                    </Typography>
                    <Typography variant="h5" color="error.main">
                      {liveMetrics.losing_trades || 0}
                    </Typography>
                  </Box>
                </Grid>
              </Grid>
            </Paper>
          )}
        </Box>
      );
    }

    // No live results yet
    return (
      <Box sx={{ px: 3 }}>
        <Alert severity="info">
          This task is currently running. Live results will appear here as the
          backtest progresses.
        </Alert>
      </Box>
    );
  }

  if (task.status === TaskStatus.FAILED) {
    return (
      <Box sx={{ px: 3 }}>
        <Alert severity="error">
          This task execution failed.{' '}
          {latestExecution?.error_message && (
            <>
              <br />
              Error: {latestExecution.error_message}
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
