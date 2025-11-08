import { useState } from 'react';
import {
  Box,
  Grid,
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

interface TaskOverviewTabProps {
  task: BacktestTask;
}

type DateRange = 'all' | '1m' | '3m' | '6m' | '1y';

export function TaskOverviewTab({ task }: TaskOverviewTabProps) {
  const [dateRange, setDateRange] = useState<DateRange>('all');

  // Fetch latest execution with full metrics
  const { data: executionsData, isLoading: executionsLoading } =
    useTaskExecutions(task.id, TaskType.BACKTEST, { page: 1, page_size: 1 });

  const latestExecution = executionsData?.results?.[0];
  const metrics = latestExecution?.metrics;

  const handleDateRangeChange = (event: SelectChangeEvent<DateRange>) => {
    setDateRange(event.target.value as DateRange);
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
    return (
      <Box sx={{ px: 3 }}>
        <Alert severity="info">
          This task is currently running. Results will be available once the
          execution completes.
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
      {/* Key Metrics Grid */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        <Grid item xs={12} sm={6} md={3}>
          <MetricCard
            title="Total Return"
            value={`${parseFloat(metrics.total_return).toFixed(2)}%`}
            icon={<TrendingUpIcon />}
            color={parseFloat(metrics.total_return) >= 0 ? 'success' : 'error'}
          />
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <MetricCard
            title="Win Rate"
            value={`${parseFloat(metrics.win_rate).toFixed(2)}%`}
            icon={<ShowChartIcon />}
            color="primary"
          />
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <MetricCard
            title="Total Trades"
            value={metrics.total_trades.toString()}
            icon={<SwapHorizIcon />}
            color="info"
          />
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
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
              <Grid item xs={12} sm={6} md={4}>
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
              <Grid item xs={12} sm={6} md={4}>
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
              <Grid item xs={12} sm={6} md={4}>
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
              <Grid item xs={12} sm={6} md={4}>
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

            <Grid item xs={12} sm={6} md={4}>
              <Box>
                <Typography variant="body2" color="text.secondary">
                  Winning Trades
                </Typography>
                <Typography variant="h5" color="success.main">
                  {metrics.winning_trades}
                </Typography>
              </Box>
            </Grid>

            <Grid item xs={12} sm={6} md={4}>
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
