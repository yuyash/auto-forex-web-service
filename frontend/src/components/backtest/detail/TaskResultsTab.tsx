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
import { Download as DownloadIcon } from '@mui/icons-material';
import { MetricsGrid } from '../../tasks/charts/MetricsGrid';
import { TradeLogTable } from '../../tasks/charts/TradeLogTable';
import { BacktestChart } from '../BacktestChart';
import type { BacktestTask } from '../../../types/backtestTask';
import { TaskStatus, TaskType } from '../../../types/common';
import type { Trade } from '../../../types/execution';
import { useTaskExecutions } from '../../../hooks/useTaskExecutions';

interface TaskResultsTabProps {
  task: BacktestTask;
}

export function TaskResultsTab({ task }: TaskResultsTabProps) {
  // Fetch latest execution with full metrics
  const { data: executionsData, isLoading: executionsLoading } =
    useTaskExecutions(task.id, TaskType.BACKTEST, { page: 1, page_size: 1 });

  const latestExecution = executionsData?.results?.[0];
  const metrics = latestExecution?.metrics;

  // Check if task has completed execution with metrics
  const hasMetrics = task.status === TaskStatus.COMPLETED && metrics;

  // State for selected trade index (for chart-to-table interaction)
  const [selectedTradeIndex, setSelectedTradeIndex] = React.useState<
    number | null
  >(null);

  // Ref for trade log table to enable scrolling
  const tradeLogRef = React.useRef<HTMLDivElement>(null);

  // Handle trade click from chart
  const handleTradeClick = React.useCallback((tradeIndex: number) => {
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
  }, []);

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

  const getTradeStatistics = () => {
    if (!metrics?.trade_log) return null;

    const trades = metrics.trade_log;
    const winningTrades = trades.filter((t: Trade) => t.pnl > 0);
    const losingTrades = trades.filter((t: Trade) => t.pnl < 0);

    const totalPnL = trades.reduce((sum: number, t: Trade) => sum + t.pnl, 0);
    const avgPnL = trades.length > 0 ? totalPnL / trades.length : 0;

    const avgWin =
      winningTrades.length > 0
        ? winningTrades.reduce((sum: number, t: Trade) => sum + t.pnl, 0) /
          winningTrades.length
        : 0;

    const avgLoss =
      losingTrades.length > 0
        ? losingTrades.reduce((sum: number, t: Trade) => sum + t.pnl, 0) /
          losingTrades.length
        : 0;

    const largestWin =
      winningTrades.length > 0
        ? Math.max(...winningTrades.map((t: Trade) => t.pnl))
        : 0;

    const largestLoss =
      losingTrades.length > 0
        ? Math.min(...losingTrades.map((t: Trade) => t.pnl))
        : 0;

    return {
      totalTrades: trades.length,
      winningTrades: winningTrades.length,
      losingTrades: losingTrades.length,
      totalPnL,
      avgPnL,
      avgWin,
      avgLoss,
      largestWin,
      largestLoss,
    };
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

  const stats = getTradeStatistics();

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString();
  };

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
            trades={metrics.trade_log}
            timezone="UTC"
            height={500}
            onTradeClick={handleTradeClick}
          />
        </Paper>
      )}

      {/* Trade Statistics */}
      {stats && (
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
                  color={stats.totalPnL >= 0 ? 'success.main' : 'error.main'}
                >
                  ${stats.totalPnL.toFixed(2)}
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
