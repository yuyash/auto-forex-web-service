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
import { tradingTasksApi } from '../../../services/api/tradingTasks';
import type { TradingTask } from '../../../types/tradingTask';
import { TaskStatus } from '../../../types/common';
import { useTradingResults } from '../../../hooks/useTaskResults';
import type {
  BacktestStrategyEvent,
  EquityPoint,
  ExecutionMetricsCheckpoint,
  Trade,
} from '../../../types/execution';
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

  const {
    results,
    isLoading: resultsLoading,
    error: resultsError,
  } = useTradingResults(task.id, task.status, { interval: 10000 });

  const execution = results?.execution;
  const metrics = results?.metrics;

  const [equityCurve, setEquityCurve] = useState<EquityPoint[]>([]);
  const [equityCurveLoading, setEquityCurveLoading] = useState(false);
  const [equityCurveError, setEquityCurveError] = useState<string | null>(null);

  const [tradeLogs, setTradeLogs] = useState<Trade[]>([]);
  const [tradeLogsLoading, setTradeLogsLoading] = useState(false);
  const [tradeLogsError, setTradeLogsError] = useState<string | null>(null);

  const [strategyEvents, setStrategyEvents] = useState<BacktestStrategyEvent[]>(
    []
  );
  const [strategyEventsLoading, setStrategyEventsLoading] = useState(false);
  const [strategyEventsError, setStrategyEventsError] = useState<string | null>(
    null
  );

  const [metricsCheckpoint, setMetricsCheckpoint] =
    useState<ExecutionMetricsCheckpoint | null>(null);
  const [metricsCheckpointLoading, setMetricsCheckpointLoading] =
    useState(false);
  const [metricsCheckpointError, setMetricsCheckpointError] = useState<
    string | null
  >(null);

  useEffect(() => {
    if (results) {
      // Update timestamp when results change - intentional state sync
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setLastUpdate(new Date());
    }
  }, [results]);

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

  const shouldFetchDetails =
    task.status !== TaskStatus.CREATED && !!task.id && !!execution?.id;
  const shouldPollDetails = task.status === TaskStatus.RUNNING;
  const hasMetrics = !!metrics;

  useEffect(() => {
    if (!shouldFetchDetails) {
      // Reset state when we shouldn't fetch - these are intentional resets
      // eslint-disable-next-line react-hooks/set-state-in-effect
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

      tradingTasksApi
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
    if (shouldPollDetails) {
      intervalId = window.setInterval(() => {
        fetchCheckpoint({ showLoading: false });
      }, 5000);
    }

    return () => {
      cancelled = true;
      if (intervalId !== null) window.clearInterval(intervalId);
    };
  }, [shouldFetchDetails, shouldPollDetails, task.id, execution?.id]);

  useEffect(() => {
    if (!shouldFetchDetails) {
      // Reset state when we shouldn't fetch - these are intentional resets
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setEquityCurve([]);

      setEquityCurveLoading(false);

      setEquityCurveError(null);

      setTradeLogs([]);

      setTradeLogsLoading(false);

      setTradeLogsError(null);

      setStrategyEvents([]);

      setStrategyEventsLoading(false);

      setStrategyEventsError(null);
      return;
    }

    let cancelled = false;

    const fetchDetails = (opts?: { showLoading?: boolean }) => {
      const showLoading = opts?.showLoading ?? false;

      if (showLoading) {
        setEquityCurveLoading(true);
        setTradeLogsLoading(true);
        setStrategyEventsLoading(true);
      }

      setEquityCurveError(null);
      setTradeLogsError(null);
      setStrategyEventsError(null);

      tradingTasksApi
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

      tradingTasksApi
        .getTradeLogs(task.id)
        .then((resp) => {
          if (cancelled) return;
          setTradeLogs(Array.isArray(resp.trade_logs) ? resp.trade_logs : []);
        })
        .catch((err) => {
          if (cancelled) return;
          setTradeLogsError(
            err instanceof Error ? err.message : 'Failed to load trade logs'
          );
          setTradeLogs([]);
        })
        .finally(() => {
          if (cancelled) return;
          if (showLoading) setTradeLogsLoading(false);
        });

      tradingTasksApi
        .getStrategyEvents(task.id)
        .then((resp) => {
          if (cancelled) return;
          setStrategyEvents(
            Array.isArray(resp.strategy_events) ? resp.strategy_events : []
          );
        })
        .catch((err) => {
          if (cancelled) return;
          setStrategyEventsError(
            err instanceof Error
              ? err.message
              : 'Failed to load strategy events'
          );
          setStrategyEvents([]);
        })
        .finally(() => {
          if (cancelled) return;
          if (showLoading) setStrategyEventsLoading(false);
        });
    };

    // Initial fetch
    fetchDetails({ showLoading: true });

    let intervalId: number | null = null;
    if (shouldPollDetails) {
      intervalId = window.setInterval(() => {
        fetchDetails({ showLoading: false });
      }, 5000);
    }

    return () => {
      cancelled = true;
      if (intervalId !== null) {
        window.clearInterval(intervalId);
      }
    };
  }, [shouldFetchDetails, shouldPollDetails, task.id, execution?.id]);

  // Filter equity curve data based on selected date range
  const getFilteredEquityCurve = () => {
    if (!equityCurve || equityCurve.length === 0) return [];

    if (dateRange === 'all') {
      return equityCurve;
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

    return equityCurve.filter(
      (point) => new Date(point.timestamp) >= cutoffDate
    );
  };

  if (resultsLoading) {
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

  if (resultsError) {
    return (
      <Box sx={{ px: 3 }}>
        <Alert severity="error">Failed to load performance data.</Alert>
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
    const errorMessage = execution?.error_message;
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

  if (!execution?.id) {
    return (
      <Box sx={{ px: 3 }}>
        <Alert severity="warning">
          No execution available yet. Start the task to see performance data.
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
      {metricsCheckpointError && (
        <Alert severity="warning" sx={{ mb: 3 }}>
          Failed to load live metrics. {metricsCheckpointError}
        </Alert>
      )}

      {!hasMetrics && !metricsCheckpoint && (
        <Alert severity="info" sx={{ mb: 3 }}>
          Waiting for metrics… Equity curve and trade logs update live.
        </Alert>
      )}

      {(hasMetrics || !!metricsCheckpoint) && (
        <Grid container spacing={3} sx={{ mb: 4 }}>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <MetricCard
              title="Total Return"
              value={`${parseFloat(
                (metrics ?? metricsCheckpoint)?.total_return ?? '0'
              ).toFixed(2)}%`}
              icon={<TrendingUpIcon />}
              color={
                parseFloat(
                  (metrics ?? metricsCheckpoint)?.total_return ?? '0'
                ) >= 0
                  ? 'success'
                  : 'error'
              }
              isLoading={metricsCheckpointLoading && !hasMetrics}
            />
          </Grid>

          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <MetricCard
              title="Win Rate"
              value={`${parseFloat(
                (metrics ?? metricsCheckpoint)?.win_rate ?? '0'
              ).toFixed(2)}%`}
              icon={<ShowChartIcon />}
              color="primary"
              isLoading={metricsCheckpointLoading && !hasMetrics}
            />
          </Grid>

          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <MetricCard
              title="Total Trades"
              value={
                (metrics ?? metricsCheckpoint)?.total_trades?.toString() ?? '0'
              }
              icon={<SwapHorizIcon />}
              color="info"
              isLoading={metricsCheckpointLoading && !hasMetrics}
            />
          </Grid>

          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <MetricCard
              title="Max Drawdown"
              value={`${parseFloat(
                (metrics ?? metricsCheckpoint)?.max_drawdown ?? '0'
              ).toFixed(2)}%`}
              icon={<TrendingDownIcon />}
              color="warning"
              isLoading={metricsCheckpointLoading && !hasMetrics}
            />
          </Grid>
        </Grid>
      )}

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

        {equityCurveLoading && (
          <Alert severity="info" sx={{ mb: 2 }}>
            Loading equity curve…
          </Alert>
        )}
        {equityCurveError && (
          <Alert severity="warning" sx={{ mb: 2 }}>
            Failed to load equity curve. {equityCurveError}
          </Alert>
        )}

        <EquityCurveChart data={getFilteredEquityCurve()} height={400} />
      </Paper>

      {/* OHLC Chart with Trade Markers */}
      <Paper sx={{ p: 3, mt: 3 }}>
        <Typography variant="h6" sx={{ mb: 2 }}>
          Price Chart with Trade Markers
        </Typography>

        <TradingTaskChart
          instrument={task.instrument || 'EUR_USD'}
          startDate={execution?.started_at || task.created_at}
          stopDate={
            task.status === TaskStatus.STOPPED ||
            task.status === TaskStatus.COMPLETED
              ? (execution?.completed_at ?? undefined)
              : undefined
          }
          trades={tradeLogs}
          strategyLayers={[]} // TODO: Add strategy layers if available
          height={500}
          timezone="UTC"
          autoRefresh={task.status === TaskStatus.RUNNING}
          refreshInterval={60000} // 60 seconds
          onTradeClick={handleTradeClick}
        />
      </Paper>

      {/* Floor Strategy Layer Log (for floor strategy only) */}
      {task.strategy_type === 'floor' && tradeLogs.length > 0 && (
        <Paper sx={{ p: 3, mt: 3 }}>
          <FloorLayerLog
            trades={tradeLogs}
            strategyEvents={strategyEvents}
            selectedTradeIndex={selectedTradeIndex}
          />
        </Paper>
      )}

      {/* Trade Log Table */}
      <Box ref={tradeLogTableRef} sx={{ mt: 3 }}>
        {(tradeLogsLoading || strategyEventsLoading) && (
          <Alert severity="info" sx={{ mb: 2 }}>
            Loading trade details…
          </Alert>
        )}
        {(tradeLogsError || strategyEventsError) && (
          <Alert severity="warning" sx={{ mb: 2 }}>
            Failed to load some trade details.
            {tradeLogsError ? ` Trade logs: ${tradeLogsError}.` : ''}
            {strategyEventsError
              ? ` Strategy events: ${strategyEventsError}.`
              : ''}
          </Alert>
        )}
        <TradeLogTable
          trades={tradeLogs}
          title="Trade Log"
          selectedTradeIndex={selectedTradeIndex}
        />
      </Box>

      {/* Trade Statistics */}
      {hasMetrics && (
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
                    ? (metrics.winning_trades / metrics.losing_trades).toFixed(
                        2
                      )
                    : 'N/A'}
                </Typography>
              </Box>
            </Grid>
          </Grid>
        </Paper>
      )}
    </Box>
  );
}
