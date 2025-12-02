import { useState, useEffect, useRef } from 'react';

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
import { TradeLogTable } from '../../tasks/charts/TradeLogTable';
import { FloorLayerLog } from '../../backtest/FloorLayerLog';
import { TradingTaskChart } from '../TradingTaskChart';
import type { TradingTask } from '../../../types/tradingTask';
import { TaskStatus, TaskType } from '../../../types/common';
import { useTaskExecutions } from '../../../hooks/useTaskExecutions';
import {
  TrendingUp as TrendingUpIcon,
  ShowChart as ShowChartIcon,
  SwapHoriz as SwapHorizIcon,
  TrendingDown as TrendingDownIcon,
} from '@mui/icons-material';

interface TaskPerformanceTabProps {
  task: TradingTask;
}

type DateRange = 'all' | '1d' | '1w' | '1m' | '3m';

export function TaskPerformanceTab({ task }: TaskPerformanceTabProps) {
  const [dateRange, setDateRange] = useState<DateRange>('all');
  const [lastUpdate, setLastUpdate] = useState<Date>(new Date());
  const [selectedTradeIndex, setSelectedTradeIndex] = useState<number | null>(
    null
  );

  // Ref for trade log table to scroll to selected trade
  const tradeLogTableRef = useRef<HTMLDivElement>(null);

  // Fetch latest execution with full metrics
  const { data: executionsData, isLoading: executionsLoading } =
    useTaskExecutions(task.id, TaskType.TRADING, { page: 1, page_size: 1 });

  const latestExecution = executionsData?.results?.[0];
  const metrics = latestExecution?.metrics;

  // Auto-refresh every 10 seconds for running tasks
  useEffect(() => {
    if (task.status !== TaskStatus.RUNNING) {
      return;
    }

    const interval = setInterval(() => {
      setLastUpdate(new Date());
    }, 10000);

    return () => clearInterval(interval);
  }, [task.status]);

  const handleDateRangeChange = (event: SelectChangeEvent<DateRange>) => {
    setDateRange(event.target.value as DateRange);
  };

  // Handle trade click from chart - scroll to trade in table
  const handleTradeClick = (tradeIndex: number) => {
    setSelectedTradeIndex(tradeIndex);

    // Scroll to trade log table
    if (tradeLogTableRef.current) {
      tradeLogTableRef.current.scrollIntoView({
        behavior: 'smooth',
        block: 'nearest',
      });
    }
  };

  // Check if task has execution with metrics
  const hasMetrics =
    (task.status === TaskStatus.RUNNING ||
      task.status === TaskStatus.PAUSED ||
      task.status === TaskStatus.STOPPED ||
      task.status === TaskStatus.COMPLETED) &&
    metrics;

  // Filter equity curve data based on selected date range
  const getFilteredEquityCurve = () => {
    if (!metrics?.equity_curve) return [];

    if (dateRange === 'all') {
      return metrics.equity_curve;
    }

    const now = new Date();
    const cutoffDate = new Date();

    switch (dateRange) {
      case '1d':
        cutoffDate.setDate(now.getDate() - 1);
        break;
      case '1w':
        cutoffDate.setDate(now.getDate() - 7);
        break;
      case '1m':
        cutoffDate.setMonth(now.getMonth() - 1);
        break;
      case '3m':
        cutoffDate.setMonth(now.getMonth() - 3);
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
          This task has not been started yet. Start the task to see performance
          metrics.
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
          No performance metrics available yet. Metrics will be generated as the
          task executes trades.
        </Alert>
      </Box>
    );
  }

  return (
    <Box sx={{ px: 3 }}>
      {/* Live Update Indicator */}
      {task.status === TaskStatus.RUNNING && (
        <Alert severity="info" sx={{ mb: 3 }}>
          Live trading metrics update automatically every 10 seconds. Last
          updated: {lastUpdate.toLocaleTimeString()}
        </Alert>
      )}

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
          <Typography variant="h6">
            Live Equity Curve
            {task.status === TaskStatus.RUNNING && (
              <Box
                component="span"
                sx={{
                  ml: 1,
                  display: 'inline-block',
                  width: 8,
                  height: 8,
                  borderRadius: '50%',
                  bgcolor: 'success.main',
                  animation: 'pulse 2s infinite',
                  '@keyframes pulse': {
                    '0%, 100%': { opacity: 1 },
                    '50%': { opacity: 0.5 },
                  },
                }}
              />
            )}
          </Typography>

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
              <MenuItem value="1d">Last 24 Hours</MenuItem>
              <MenuItem value="1w">Last Week</MenuItem>
              <MenuItem value="1m">Last Month</MenuItem>
              <MenuItem value="3m">Last 3 Months</MenuItem>
            </Select>
          </FormControl>
        </Box>

        <EquityCurveChart data={getFilteredEquityCurve()} height={400} />
      </Paper>

      {/* OHLC Chart with Trade Markers */}
      <Paper sx={{ p: 3, mt: 3 }}>
        <Typography variant="h6" sx={{ mb: 2 }}>
          Price Chart with Trade Markers
        </Typography>

        <TradingTaskChart
          instrument={task.config_name.split(' - ')[0] || 'EUR_USD'} // Extract instrument from config name
          startDate={latestExecution?.started_at || task.created_at}
          stopDate={
            task.status === TaskStatus.STOPPED ||
            task.status === TaskStatus.COMPLETED
              ? latestExecution?.completed_at
              : undefined
          }
          trades={metrics?.trade_log || []}
          strategyLayers={[]} // TODO: Add strategy layers if available
          height={500}
          timezone="UTC"
          autoRefresh={task.status === TaskStatus.RUNNING}
          refreshInterval={60000} // 60 seconds
          onTradeClick={handleTradeClick}
        />
      </Paper>

      {/* Floor Strategy Layer Log (for floor strategy only) */}
      {task.strategy_type === 'floor' &&
        metrics?.trade_log &&
        metrics.trade_log.length > 0 && (
          <Paper sx={{ p: 3, mt: 3 }}>
            <FloorLayerLog
              trades={metrics.trade_log}
              strategyEvents={metrics.strategy_events}
              selectedTradeIndex={selectedTradeIndex}
            />
          </Paper>
        )}

      {/* Trade Log Table */}
      <Box ref={tradeLogTableRef} sx={{ mt: 3 }}>
        <TradeLogTable
          trades={metrics?.trade_log || []}
          title="Trade Log"
          selectedTradeIndex={selectedTradeIndex}
        />
      </Box>

      {/* Trade Statistics */}
      <Paper sx={{ p: 3, mt: 3 }}>
        <Typography variant="h6" sx={{ mb: 2 }}>
          Trade Statistics
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

          <Grid size={{ xs: 12, sm: 6, md: 4 }}>
            <Box>
              <Typography variant="body2" color="text.secondary">
                Total P&L
              </Typography>
              <Typography
                variant="h5"
                color={
                  parseFloat(metrics.total_pnl) >= 0
                    ? 'success.main'
                    : 'error.main'
                }
              >
                ${parseFloat(metrics.total_pnl).toFixed(2)}
              </Typography>
            </Box>
          </Grid>

          {metrics.average_win && (
            <Grid size={{ xs: 12, sm: 6, md: 4 }}>
              <Box>
                <Typography variant="body2" color="text.secondary">
                  Average Win
                </Typography>
                <Typography variant="h5" color="success.main">
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

          <Grid size={{ xs: 12, sm: 6, md: 4 }}>
            <Box>
              <Typography variant="body2" color="text.secondary">
                Win/Loss Ratio
              </Typography>
              <Typography variant="h5">
                {metrics.losing_trades > 0
                  ? (metrics.winning_trades / metrics.losing_trades).toFixed(2)
                  : 'N/A'}
              </Typography>
            </Box>
          </Grid>
        </Grid>
      </Paper>
    </Box>
  );
}
