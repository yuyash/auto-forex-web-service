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
import { TaskStatus, TaskType } from '../../../types/common';
import type { Trade } from '../../../types/execution';
import { useTaskExecutions } from '../../../hooks/useTaskExecutions';
import type { ChartMarker } from '../../../utils/chartMarkers';
import type { BacktestStrategyEvent } from '../../../types/execution';

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

interface LiveTrade {
  timestamp?: string;
  entry_time?: string;
  exit_time?: string;
  instrument?: string;
  direction?: string;
  entry_price?: number;
  exit_price?: number;
  units?: number;
  pnl?: number;
  realized_pnl?: number;
  duration?: number | string;
  layer_number?: number;
  is_first_lot?: boolean;
  retracement_count?: number;
  entry_retracement_count?: number;
  [key: string]: string | number | boolean | undefined;
}

interface LiveResults {
  day_date: string;
  progress: number;
  days_processed: number;
  total_days: number;
  balance: number;
  total_trades: number;
  metrics: LiveMetrics;
  trade_log?: LiveTrade[];
  strategy_events?: BacktestStrategyEvent[];
}

interface TaskResultsTabProps {
  task: BacktestTask;
  liveResults?: LiveResults | null;
}

export function TaskResultsTab({ task, liveResults }: TaskResultsTabProps) {
  // Fetch latest execution with full metrics
  const { data: executionsData, isLoading: executionsLoading } =
    useTaskExecutions(task.id, TaskType.BACKTEST, {
      page: 1,
      page_size: 1,
      include_metrics: true,
    });

  const latestExecution = executionsData?.results?.[0];
  const metrics = latestExecution?.metrics;

  // Check if task has completed execution with metrics
  const hasMetrics = task.status === TaskStatus.COMPLETED && metrics;

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
    if (!metrics?.trade_log) return;

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

    const rows = metrics.trade_log.map((trade: Trade) => [
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
    if (!metrics?.trade_log) return null;

    const safeNumber = (value: unknown, fallback = 0): number => {
      if (value === null || value === undefined) return fallback;
      const num = typeof value === 'number' ? value : Number(value);
      return Number.isFinite(num) ? num : fallback;
    };

    const trades = metrics.trade_log;
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

    const unrealizedPnL = safeNumber(
      (metrics as { unrealized_pnl?: unknown }).unrealized_pnl
    );
    const realizedPnL = safeNumber(
      (metrics as { realized_pnl?: unknown }).realized_pnl,
      tradeLogRealizedPnL
    );
    const totalPnL = safeNumber(
      (metrics as { total_pnl?: unknown }).total_pnl,
      tradeLogTotalPnL
    );
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
    if (liveResults && liveResults.total_trades > 0) {
      const liveMetrics = liveResults.metrics;

      return (
        <Box sx={{ px: 3 }}>
          {/* Running Status Banner */}
          <Alert severity="info" sx={{ mb: 3 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <CircularProgress size={16} />
              <Typography variant="body2">
                Task is running... Day {liveResults.days_processed} of{' '}
                {liveResults.total_days} ({liveResults.progress}% complete)
              </Typography>
            </Box>
          </Alert>

          {/* Live Backtest Period */}
          <Paper sx={{ p: 2, mb: 3, bgcolor: 'grey.50' }}>
            <Typography variant="subtitle2" color="text.secondary" gutterBottom>
              Backtest Period (Live Data up to {liveResults.day_date})
            </Typography>
            <Typography variant="body1">
              {formatDate(task.start_time)} → {formatDate(task.end_time)}
            </Typography>
          </Paper>

          {/* Live Performance Metrics */}
          <Paper sx={{ p: 3, mb: 3 }}>
            <Typography variant="h6" sx={{ mb: 3 }}>
              Live Performance Metrics
            </Typography>

            <Grid container spacing={3}>
              <Grid size={{ xs: 6, sm: 4, md: 3 }}>
                <Paper
                  sx={{
                    p: 2,
                    textAlign: 'center',
                    bgcolor: 'background.default',
                  }}
                >
                  <Typography variant="subtitle2" color="text.secondary">
                    Current Balance
                  </Typography>
                  <Typography variant="h6">
                    $
                    {liveResults.balance.toLocaleString(undefined, {
                      minimumFractionDigits: 2,
                      maximumFractionDigits: 2,
                    })}
                  </Typography>
                </Paper>
              </Grid>
              <Grid size={{ xs: 6, sm: 4, md: 3 }}>
                <Paper
                  sx={{
                    p: 2,
                    textAlign: 'center',
                    bgcolor: 'background.default',
                  }}
                >
                  <Typography variant="subtitle2" color="text.secondary">
                    Total Return
                  </Typography>
                  <Typography
                    variant="h6"
                    sx={{
                      color:
                        (liveMetrics.total_return || 0) >= 0
                          ? 'success.main'
                          : 'error.main',
                    }}
                  >
                    {(liveMetrics.total_return || 0).toFixed(2)}%
                  </Typography>
                </Paper>
              </Grid>
              <Grid size={{ xs: 6, sm: 4, md: 3 }}>
                <Paper
                  sx={{
                    p: 2,
                    textAlign: 'center',
                    bgcolor: 'background.default',
                  }}
                >
                  <Typography variant="subtitle2" color="text.secondary">
                    Total Trades
                  </Typography>
                  <Typography variant="h6">
                    {liveResults.total_trades}
                  </Typography>
                </Paper>
              </Grid>
              <Grid size={{ xs: 6, sm: 4, md: 3 }}>
                <Paper
                  sx={{
                    p: 2,
                    textAlign: 'center',
                    bgcolor: 'background.default',
                  }}
                >
                  <Typography variant="subtitle2" color="text.secondary">
                    Win Rate
                  </Typography>
                  <Typography variant="h6">
                    {(liveMetrics.win_rate || 0).toFixed(1)}%
                  </Typography>
                </Paper>
              </Grid>
              <Grid size={{ xs: 6, sm: 4, md: 3 }}>
                <Paper
                  sx={{
                    p: 2,
                    textAlign: 'center',
                    bgcolor: 'background.default',
                  }}
                >
                  <Typography variant="subtitle2" color="text.secondary">
                    Total P&L
                  </Typography>
                  <Typography
                    variant="h6"
                    sx={{
                      color:
                        (liveMetrics.total_pnl || 0) >= 0
                          ? 'success.main'
                          : 'error.main',
                    }}
                  >
                    $
                    {(liveMetrics.total_pnl || 0).toLocaleString(undefined, {
                      minimumFractionDigits: 2,
                      maximumFractionDigits: 2,
                    })}
                  </Typography>
                </Paper>
              </Grid>
              <Grid size={{ xs: 6, sm: 4, md: 3 }}>
                <Paper
                  sx={{
                    p: 2,
                    textAlign: 'center',
                    bgcolor: 'background.default',
                  }}
                >
                  <Typography variant="subtitle2" color="text.secondary">
                    Max Drawdown
                  </Typography>
                  <Typography variant="h6" sx={{ color: 'error.main' }}>
                    {(liveMetrics.max_drawdown || 0).toFixed(2)}%
                  </Typography>
                </Paper>
              </Grid>
            </Grid>
          </Paper>

          {/* Live OHLC Chart with Trading Events */}
          {liveResults.trade_log && liveResults.trade_log.length > 0 && (
            <Paper sx={{ p: 3, mb: 3 }}>
              <Typography variant="h6" sx={{ mb: 3 }}>
                Price Chart with Trading Events (Live)
              </Typography>

              <BacktestChart
                instrument={task.instrument}
                startDate={task.start_time}
                endDate={liveResults.day_date}
                strategyEvents={liveResults.strategy_events}
                timezone="UTC"
                height={500}
                onTradeClick={handleMarkerClick}
              />
            </Paper>
          )}

          {/* Live Floor Layer Log (for floor strategy) */}
          {task.strategy_type === 'floor' &&
            liveResults.trade_log &&
            liveResults.trade_log.length > 0 && (
              <Paper sx={{ p: 3, mb: 3 }}>
                <FloorLayerLog
                  trades={liveResults.trade_log.map((t) => ({
                    entry_time: t.entry_time || t.timestamp || '',
                    exit_time: t.exit_time || '',
                    instrument: t.instrument || task.instrument,
                    direction: (t.direction?.toLowerCase() === 'short'
                      ? 'short'
                      : 'long') as 'long' | 'short',
                    units: t.units || 0,
                    entry_price: t.entry_price || 0,
                    exit_price: t.exit_price || 0,
                    pnl: t.pnl || 0,
                    realized_pnl: t.realized_pnl || t.pnl || 0,
                    duration: t.duration?.toString() || '',
                    layer_number: t.layer_number,
                    is_first_lot: t.is_first_lot,
                    retracement_count: t.retracement_count,
                    entry_retracement_count: t.entry_retracement_count,
                  }))}
                />
              </Paper>
            )}

          {/* Live Trade Log Table */}
          {liveResults.trade_log && liveResults.trade_log.length > 0 && (
            <Paper sx={{ p: 3 }}>
              <Typography variant="h6" sx={{ mb: 3 }}>
                Trade Log (Live - {liveResults.trade_log.length} trades)
              </Typography>
              <TradeLogTable
                trades={liveResults.trade_log.map((t) => ({
                  entry_time: t.entry_time || t.timestamp || '',
                  exit_time: t.exit_time || '',
                  instrument: t.instrument || task.instrument,
                  direction: (t.direction?.toLowerCase() === 'short'
                    ? 'short'
                    : 'long') as 'long' | 'short',
                  units: t.units || 0,
                  entry_price: t.entry_price || 0,
                  exit_price: t.exit_price || 0,
                  pnl: t.pnl || 0,
                  realized_pnl: t.realized_pnl || t.pnl || 0,
                  duration: t.duration?.toString() || '',
                  layer_number: t.layer_number,
                  is_first_lot: t.is_first_lot,
                  retracement_count: t.retracement_count,
                  entry_retracement_count: t.entry_retracement_count,
                }))}
                selectedTradeIndex={selectedTradeIndex}
              />
            </Paper>
          )}
        </Box>
      );
    }

    // No live results yet - show waiting message
    return (
      <Box sx={{ px: 3 }}>
        <Alert severity="info">
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <CircularProgress size={16} />
            <Typography variant="body2">
              This task is currently running. Live results will appear here
              shortly...
            </Typography>
          </Box>
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
      </Paper>

      {/* Performance Metrics */}
      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography variant="h6" sx={{ mb: 3 }}>
          Performance Metrics
        </Typography>

        <MetricsGrid metrics={metrics} />
      </Paper>

      {/* OHLC Chart with Trading Events */}
      {metrics.trade_log && metrics.trade_log.length > 0 && (
        <Paper sx={{ p: 3, mb: 3 }}>
          <Typography variant="h6" sx={{ mb: 3 }}>
            Price Chart with Trading Events
          </Typography>

          <BacktestChart
            instrument={task.instrument}
            startDate={task.start_time}
            endDate={task.end_time}
            strategyEvents={metrics.strategy_events}
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
      {task.strategy_type === 'floor' &&
        metrics.trade_log &&
        metrics.trade_log.length > 0 && (
          <>
            {import.meta.env.DEV &&
              console.log('[TaskResultsTab] Rendering FloorLayerLog', {
                strategy_type: task.strategy_type,
                trade_count: metrics.trade_log.length,
                first_trade: metrics.trade_log[0],
                strategy_events_count: metrics.strategy_events?.length || 0,
              })}
            <FloorLayerLog
              trades={metrics.trade_log}
              strategyEvents={metrics.strategy_events}
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
          trades={metrics.trade_log}
          showExport={false}
          selectedTradeIndex={selectedTradeIndex}
        />
      </Box>
    </Box>
  );
}
