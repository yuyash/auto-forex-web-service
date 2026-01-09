import React from 'react';
import {
  Box,
  Paper,
  Typography,
  Alert,
  Divider,
  Button,
  CircularProgress,
} from '@mui/material';
import Grid from '@mui/material/Grid';
import {
  Download as DownloadIcon,
  FileDownload as FileDownloadIcon,
} from '@mui/icons-material';
import { backtestTasksApi } from '../../../services/api/backtestTasks';
import { MetricsGrid } from '../../tasks/charts/MetricsGrid';
import { TradeLogTable } from '../../tasks/charts/TradeLogTable';
import { BacktestChart } from '../BacktestChart';
import { FloorLayerLog } from '../FloorLayerLog';
import type { BacktestTask } from '../../../types/backtestTask';
import { TaskStatus } from '../../../types/common';
import { durationMsBetween, formatDurationMs } from '../../../utils/duration';
import type {
  BacktestStrategyEvent,
  ExecutionMetricsCheckpoint,
  Trade,
} from '../../../types/execution';
import type { TaskResults } from '../../../types/results';
import type { ChartMarker } from '../../../utils/chartMarkers';

const toNumberOrNull = (value: unknown): number | null => {
  if (value === null || value === undefined) return null;
  const n = typeof value === 'number' ? value : Number(value);
  return Number.isFinite(n) ? n : null;
};

interface TaskResultsTabProps {
  task: BacktestTask;
  results?: TaskResults | null;
}

export function TaskResultsTab({ task, results }: TaskResultsTabProps) {
  const metrics = results?.metrics ?? null;

  const hasMetrics = task.status === TaskStatus.COMPLETED && !!metrics;

  const [tradeLogs, setTradeLogs] = React.useState<Trade[]>([]);
  const [tradeLogsLoading, setTradeLogsLoading] = React.useState(false);
  const [tradeLogsError, setTradeLogsError] = React.useState<string | null>(
    null
  );
  const [strategyEvents, setStrategyEvents] = React.useState<
    BacktestStrategyEvent[]
  >([]);
  const [strategyEventsLoading, setStrategyEventsLoading] =
    React.useState(false);
  const [strategyEventsError, setStrategyEventsError] = React.useState<
    string | null
  >(null);

  const [metricsCheckpoint, setMetricsCheckpoint] =
    React.useState<ExecutionMetricsCheckpoint | null>(null);
  const [metricsCheckpointLoading, setMetricsCheckpointLoading] =
    React.useState(false);
  const [metricsCheckpointError, setMetricsCheckpointError] = React.useState<
    string | null
  >(null);

  const shouldFetchDetails =
    task.status !== TaskStatus.CREATED && !!task.id && !!results?.execution?.id;
  const shouldPollDetails = task.status === TaskStatus.RUNNING;

  React.useEffect(() => {
    if (!shouldFetchDetails) {
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
    if (shouldPollDetails) {
      intervalId = window.setInterval(() => {
        fetchCheckpoint({ showLoading: false });
      }, 5000);
    }

    return () => {
      cancelled = true;
      if (intervalId !== null) window.clearInterval(intervalId);
    };
  }, [shouldFetchDetails, shouldPollDetails, task.id]);

  React.useEffect(() => {
    if (!shouldFetchDetails) {
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
        setTradeLogsLoading(true);
        setStrategyEventsLoading(true);
      }

      setTradeLogsError(null);
      setStrategyEventsError(null);

      backtestTasksApi
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

      backtestTasksApi
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
  }, [shouldFetchDetails, shouldPollDetails, task.id, results?.execution?.id]);

  // Debug logging for strategy events (ALWAYS LOG)
  React.useEffect(() => {}, [metrics]);

  // State for selected trade index (for chart-to-table interaction)
  const [selectedTradeIndex, setSelectedTradeIndex] = React.useState<
    number | null
  >(null);

  // Ref for trade log table to enable scrolling
  const tradeLogRef = React.useRef<HTMLDivElement>(null);

  // Handle marker click from chart
  const handleMarkerClick = React.useCallback((marker: ChartMarker) => {
    if (marker.id && marker.id.startsWith('event-')) {
      // Strategy event marker clicked - scroll to event
      const element = document.getElementById(marker.id);
      if (element) {
        element.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    } else if (marker.id && marker.id.startsWith('trade-')) {
      // Trade marker clicked
      const tradeIndex = parseInt(marker.id.replace('trade-', ''), 10);
      if (!isNaN(tradeIndex)) {
        setSelectedTradeIndex(tradeIndex);

        // Scroll to trade log table
        if (tradeLogRef.current) {
          tradeLogRef.current.scrollIntoView({
            behavior: 'smooth',
            block: 'nearest',
          });
        }

        // Clear selection after 3 seconds
        setTimeout(() => {
          setSelectedTradeIndex(null);
        }, 3000);
      }
    }
  }, []);

  const [isExporting, setIsExporting] = React.useState(false);

  const handleExportCSV = () => {
    if (!tradeLogs || tradeLogs.length === 0) return;

    // Create CSV content
    const headers = [
      'Entry Time',
      'Exit Time',
      'Instrument',
      'Direction',
      'Units',
      'Entry Price',
      'Exit Price',
      'P&L',
      'Realized P&L',
      'Duration',
    ];

    const rows = tradeLogs.map((trade: Trade) => [
      trade.entry_time,
      trade.exit_time,
      trade.instrument,
      trade.direction,
      trade.units.toString(),
      trade.entry_price.toString(),
      trade.exit_price.toString(),
      trade.pnl.toString(),
      (trade.realized_pnl ?? trade.pnl).toString(),
      trade.duration || '',
    ]);

    const csvContent = [
      headers.join(','),
      ...rows.map((row: string[]) => row.join(',')),
    ].join('\n');

    // Create and download file
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);

    link.setAttribute('href', url);
    link.setAttribute('download', `${task.name}_trades.csv`);
    link.style.visibility = 'hidden';

    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const handleExportJSON = async () => {
    setIsExporting(true);
    try {
      await backtestTasksApi.exportResults(task.id, task.name);
    } catch (error) {
      console.error('Failed to export backtest results:', error);
    } finally {
      setIsExporting(false);
    }
  };

  const getTradeStatistics = () => {
    if (!tradeLogs || tradeLogs.length === 0) return null;

    const safeNumber = (value: unknown, fallback = 0): number => {
      if (value === null || value === undefined) return fallback;
      const num = typeof value === 'number' ? value : Number(value);
      return Number.isFinite(num) ? num : fallback;
    };

    const trades = tradeLogs;
    const tradePnl = (trade: Trade) =>
      safeNumber((trade as Trade & { pnl?: unknown }).pnl);
    const tradeRealizedPnl = (trade: Trade) =>
      safeNumber(
        (trade as Trade & { realized_pnl?: unknown }).realized_pnl ??
          (trade as Trade & { pnl?: unknown }).pnl
      );

    const winningTrades = trades.filter((t: Trade) => tradePnl(t) > 0);
    const losingTrades = trades.filter((t: Trade) => tradePnl(t) < 0);

    const tradeLogTotalPnL = trades.reduce(
      (sum: number, t: Trade) => sum + tradePnl(t),
      0
    );
    const tradeLogRealizedPnL = trades.reduce(
      (sum: number, t: Trade) => sum + tradeRealizedPnl(t),
      0
    );

    const metricsSafe: Record<string, unknown> =
      metrics && typeof metrics === 'object'
        ? (metrics as Record<string, unknown>)
        : {};

    const unrealizedPnL = safeNumber(metricsSafe.unrealized_pnl);
    const realizedPnL = safeNumber(
      metricsSafe.realized_pnl,
      tradeLogRealizedPnL
    );
    const totalPnL = safeNumber(metricsSafe.total_pnl, tradeLogTotalPnL);
    const avgPnL = trades.length > 0 ? realizedPnL / trades.length : 0;

    const avgWin =
      winningTrades.length > 0
        ? winningTrades.reduce(
            (sum: number, t: Trade) => sum + tradePnl(t),
            0
          ) / winningTrades.length
        : 0;

    const avgLoss =
      losingTrades.length > 0
        ? losingTrades.reduce((sum: number, t: Trade) => sum + tradePnl(t), 0) /
          losingTrades.length
        : 0;

    const largestWin =
      winningTrades.length > 0
        ? Math.max(...winningTrades.map((t: Trade) => tradePnl(t)))
        : 0;

    const largestLoss =
      losingTrades.length > 0
        ? Math.min(...losingTrades.map((t: Trade) => tradePnl(t)))
        : 0;

    return {
      totalTrades: trades.length,
      winningTrades: winningTrades.length,
      losingTrades: losingTrades.length,
      totalPnL,
      realizedPnL,
      unrealizedPnL,
      avgPnL,
      avgWin,
      avgLoss,
      largestWin,
      largestLoss,
    };
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

  if (!results && task.status !== TaskStatus.CREATED) {
    // While running, show the live layout even if the first poll hasn't returned yet.
    if (task.status === TaskStatus.RUNNING) {
      return (
        <Box sx={{ px: 3 }}>
          <Alert severity="info" sx={{ mb: 3 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <CircularProgress size={16} />
              <Typography variant="body2">Task is running…</Typography>
            </Box>
          </Alert>

          <Paper sx={{ p: 2, mb: 3, bgcolor: 'grey.50' }}>
            <Typography variant="subtitle2" color="text.secondary" gutterBottom>
              Backtest Period
            </Typography>
            <Typography variant="body1">
              {formatDate(task.start_time)} → {formatDate(task.end_time)}
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
              Elapsed:{' '}
              {durationMs !== null ? formatDurationMs(durationMs) : '—'}
            </Typography>
          </Paper>

          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" sx={{ mb: 3 }}>
              Live Results
            </Typography>
            <Alert severity="info">Waiting for live snapshot…</Alert>
          </Paper>
        </Box>
      );
    }

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
    const live = (results?.live ?? null) as Record<string, unknown> | null;
    const progress = toNumberOrNull(live?.progress);
    const liveMetrics = metricsCheckpoint;

    return (
      <Box sx={{ px: 3 }}>
        <Alert severity="info" sx={{ mb: 3 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <CircularProgress size={16} />
            <Typography variant="body2">
              Task is running...
              {progress !== null && progress > 0
                ? ` ${progress}% complete.`
                : ''}
            </Typography>
          </Box>
        </Alert>

        <Paper sx={{ p: 2, mb: 3, bgcolor: 'grey.50' }}>
          <Typography variant="subtitle2" color="text.secondary" gutterBottom>
            Backtest Period
          </Typography>
          <Typography variant="body1">
            {formatDate(task.start_time)} → {formatDate(task.end_time)}
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
            Elapsed: {durationMs !== null ? formatDurationMs(durationMs) : '—'}
          </Typography>
        </Paper>

        <Paper sx={{ p: 3, mb: 3 }}>
          <Typography variant="h6" sx={{ mb: 3 }}>
            Performance Metrics
          </Typography>

          {metricsCheckpointError && (
            <Alert severity="warning" sx={{ mb: 2 }}>
              Failed to load live metrics. {metricsCheckpointError}
            </Alert>
          )}

          {!liveMetrics && (
            <Alert severity="info">
              Waiting for performance metrics… Live results (trades/events)
              update while the task runs.
            </Alert>
          )}

          {liveMetrics && (
            <MetricsGrid
              metrics={liveMetrics}
              isLoading={metricsCheckpointLoading}
            />
          )}
        </Paper>

        {(tradeLogsLoading || strategyEventsLoading) && (
          <Alert severity="info" sx={{ mb: 2 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <CircularProgress size={16} />
              <Typography variant="body2">Loading live details…</Typography>
            </Box>
          </Alert>
        )}

        {(tradeLogsError || strategyEventsError) && (
          <Alert severity="warning" sx={{ mb: 2 }}>
            Failed to load some live details.
            {tradeLogsError ? ` Trade logs: ${tradeLogsError}.` : ''}
            {strategyEventsError
              ? ` Strategy events: ${strategyEventsError}.`
              : ''}
          </Alert>
        )}

        {/* OHLC Chart with Trading Events */}
        {tradeLogs.length > 0 && (
          <Paper sx={{ p: 3, mb: 3 }}>
            <Typography variant="h6" sx={{ mb: 3 }}>
              Price Chart with Trading Events
            </Typography>

            <BacktestChart
              instrument={task.instrument}
              startDate={task.start_time}
              endDate={task.end_time}
              strategyEvents={strategyEvents}
              timezone="UTC"
              height={500}
              onTradeClick={handleMarkerClick}
            />
          </Paper>
        )}

        {/* Trade Statistics (derived from current trades) */}
        {(() => {
          const stats = getTradeStatistics();
          if (!stats) return null;
          return (
            <Paper sx={{ p: 3, mb: 3 }}>
              <Typography variant="h6" sx={{ mb: 3 }}>
                Trade Statistics
              </Typography>

              <Grid container spacing={3}>
                <Grid size={{ xs: 12, sm: 6, md: 4 }}>
                  <Box>
                    <Typography variant="body2" color="text.secondary">
                      Total P&L
                    </Typography>
                    <Typography
                      variant="h5"
                      color={
                        stats.totalPnL >= 0 ? 'success.main' : 'error.main'
                      }
                    >
                      ${stats.totalPnL.toFixed(2)}
                    </Typography>
                  </Box>
                </Grid>

                <Grid size={{ xs: 12, sm: 6, md: 4 }}>
                  <Box>
                    <Typography variant="body2" color="text.secondary">
                      Realized P&L
                    </Typography>
                    <Typography
                      variant="h5"
                      color={
                        stats.realizedPnL >= 0 ? 'success.main' : 'error.main'
                      }
                    >
                      ${stats.realizedPnL.toFixed(2)}
                    </Typography>
                  </Box>
                </Grid>

                <Grid size={{ xs: 12, sm: 6, md: 4 }}>
                  <Box>
                    <Typography variant="body2" color="text.secondary">
                      Unrealized P&L
                    </Typography>
                    <Typography
                      variant="h5"
                      color={
                        stats.unrealizedPnL >= 0 ? 'success.main' : 'error.main'
                      }
                    >
                      ${stats.unrealizedPnL.toFixed(2)}
                    </Typography>
                  </Box>
                </Grid>
              </Grid>
            </Paper>
          );
        })()}

        {task.strategy_type === 'floor' && tradeLogs.length > 0 && (
          <FloorLayerLog
            trades={tradeLogs}
            strategyEvents={strategyEvents}
            selectedTradeIndex={selectedTradeIndex}
          />
        )}

        <Divider sx={{ my: 3 }} />

        <Box ref={tradeLogRef}>
          <Typography variant="h6" sx={{ mb: 2 }}>
            Trade Log
          </Typography>

          <TradeLogTable
            trades={tradeLogs}
            showExport={false}
            selectedTradeIndex={selectedTradeIndex}
          />
        </Box>
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

  const stats = getTradeStatistics();

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

      {/* Performance Metrics */}
      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography variant="h6" sx={{ mb: 3 }}>
          Performance Metrics
        </Typography>

        <MetricsGrid metrics={metrics} />
      </Paper>

      {(tradeLogsLoading || strategyEventsLoading) && (
        <Alert severity="info" sx={{ mb: 2 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <CircularProgress size={16} />
            <Typography variant="body2">Loading results details…</Typography>
          </Box>
        </Alert>
      )}

      {(tradeLogsError || strategyEventsError) && (
        <Alert severity="warning" sx={{ mb: 2 }}>
          Failed to load some result details.
          {tradeLogsError ? ` Trade logs: ${tradeLogsError}.` : ''}
          {strategyEventsError
            ? ` Strategy events: ${strategyEventsError}.`
            : ''}
        </Alert>
      )}

      {/* OHLC Chart with Trading Events */}
      {tradeLogs.length > 0 && (
        <Paper sx={{ p: 3, mb: 3 }}>
          <Typography variant="h6" sx={{ mb: 3 }}>
            Price Chart with Trading Events
          </Typography>

          <BacktestChart
            instrument={task.instrument}
            startDate={task.start_time}
            endDate={task.end_time}
            strategyEvents={strategyEvents}
            timezone="UTC"
            height={500}
            onTradeClick={handleMarkerClick}
          />
        </Paper>
      )}

      {/* Trade Statistics */}
      {stats && (
        <Paper sx={{ p: 3, mb: 3 }}>
          <Box
            sx={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              mb: 3,
            }}
          >
            <Typography variant="h6">Trade Statistics</Typography>
            <Button
              variant="contained"
              startIcon={
                isExporting ? (
                  <CircularProgress size={16} color="inherit" />
                ) : (
                  <FileDownloadIcon />
                )
              }
              onClick={handleExportJSON}
              disabled={isExporting}
              size="small"
            >
              Export Results
            </Button>
          </Box>

          <Grid container spacing={3}>
            <Grid size={{ xs: 12, sm: 6, md: 4 }}>
              <Box>
                <Typography variant="body2" color="text.secondary">
                  Total P&L
                </Typography>
                <Typography
                  variant="h5"
                  color={stats.totalPnL >= 0 ? 'success.main' : 'error.main'}
                >
                  ${stats.totalPnL.toFixed(2)}
                </Typography>
              </Box>
            </Grid>

            <Grid size={{ xs: 12, sm: 6, md: 4 }}>
              <Box>
                <Typography variant="body2" color="text.secondary">
                  Realized P&L
                </Typography>
                <Typography
                  variant="h5"
                  color={stats.realizedPnL >= 0 ? 'success.main' : 'error.main'}
                >
                  ${stats.realizedPnL.toFixed(2)}
                </Typography>
              </Box>
            </Grid>

            <Grid size={{ xs: 12, sm: 6, md: 4 }}>
              <Box>
                <Typography variant="body2" color="text.secondary">
                  Unrealized P&L
                </Typography>
                <Typography
                  variant="h5"
                  color={
                    stats.unrealizedPnL >= 0 ? 'success.main' : 'error.main'
                  }
                >
                  ${stats.unrealizedPnL.toFixed(2)}
                </Typography>
              </Box>
            </Grid>

            <Grid size={{ xs: 12, sm: 6, md: 4 }}>
              <Box>
                <Typography variant="body2" color="text.secondary">
                  Average P&L per Trade
                </Typography>
                <Typography
                  variant="h5"
                  color={stats.avgPnL >= 0 ? 'success.main' : 'error.main'}
                >
                  ${stats.avgPnL.toFixed(2)}
                </Typography>
              </Box>
            </Grid>

            <Grid size={{ xs: 12, sm: 6, md: 4 }}>
              <Box>
                <Typography variant="body2" color="text.secondary">
                  Average Win
                </Typography>
                <Typography variant="h5" color="success.main">
                  ${stats.avgWin.toFixed(2)}
                </Typography>
              </Box>
            </Grid>

            <Grid size={{ xs: 12, sm: 6, md: 4 }}>
              <Box>
                <Typography variant="body2" color="text.secondary">
                  Average Loss
                </Typography>
                <Typography variant="h5" color="error.main">
                  ${stats.avgLoss.toFixed(2)}
                </Typography>
              </Box>
            </Grid>

            <Grid size={{ xs: 12, sm: 6, md: 4 }}>
              <Box>
                <Typography variant="body2" color="text.secondary">
                  Largest Win
                </Typography>
                <Typography variant="h5" color="success.main">
                  ${stats.largestWin.toFixed(2)}
                </Typography>
              </Box>
            </Grid>

            <Grid size={{ xs: 12, sm: 6, md: 4 }}>
              <Box>
                <Typography variant="body2" color="text.secondary">
                  Largest Loss
                </Typography>
                <Typography variant="h5" color="error.main">
                  ${stats.largestLoss.toFixed(2)}
                </Typography>
              </Box>
            </Grid>
          </Grid>
        </Paper>
      )}

      {/* Floor Strategy Layer Log */}
      {task.strategy_type === 'floor' && tradeLogs.length > 0 && (
        <>
          {import.meta.env.DEV &&
            console.log('[TaskResultsTab] Rendering FloorLayerLog', {
              strategy_type: task.strategy_type,
              trade_count: tradeLogs.length,
              first_trade: tradeLogs[0],
              strategy_events_count: strategyEvents.length,
            })}
          <FloorLayerLog
            trades={tradeLogs}
            strategyEvents={strategyEvents}
            selectedTradeIndex={selectedTradeIndex}
          />
        </>
      )}

      <Divider sx={{ my: 3 }} />

      {/* Trade Log */}
      <Box ref={tradeLogRef}>
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            mb: 2,
          }}
        >
          <Typography variant="h6">Trade Log</Typography>

          <Button
            variant="outlined"
            startIcon={<DownloadIcon />}
            onClick={handleExportCSV}
            size="small"
          >
            Export CSV
          </Button>
        </Box>

        <TradeLogTable
          trades={tradeLogs}
          showExport={false}
          selectedTradeIndex={selectedTradeIndex}
        />
      </Box>
    </Box>
  );
}
