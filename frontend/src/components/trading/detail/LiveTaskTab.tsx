import { useState, useEffect } from 'react';

import {
  Box,
  Paper,
  Typography,
  Button,
  CircularProgress,
} from '@mui/material';
import Grid from '@mui/material/Grid';
import { Refresh as RefreshIcon } from '@mui/icons-material';
import { StatCard } from '../../tasks/display/StatCard';
import { OpenPositionsTable } from './OpenPositionsTable';
import { RecentTradesLog } from './RecentTradesLog';
import { type TradingTask } from '../../../types/tradingTask';
import { TaskStatus } from '../../../types/common';

interface LiveTaskTabProps {
  task: TradingTask;
}

export function LiveTaskTab({ task }: LiveTaskTabProps) {
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [lastUpdate, setLastUpdate] = useState<Date>(new Date());

  // Auto-refresh every 5 seconds for running tasks
  useEffect(() => {
    if (task.status !== TaskStatus.RUNNING) {
      return;
    }

    const interval = setInterval(() => {
      setLastUpdate(new Date());
    }, 5000);

    return () => clearInterval(interval);
  }, [task.status]);

  const handleManualRefresh = () => {
    setIsRefreshing(true);
    setLastUpdate(new Date());
    // Simulate refresh delay
    setTimeout(() => setIsRefreshing(false), 500);
  };

  // Calculate uptime
  const calculateUptime = () => {
    if (!task.latest_execution?.started_at) {
      return 'N/A';
    }

    const start = new Date(task.latest_execution.started_at);
    const now = new Date();
    const diff = now.getTime() - start.getTime();

    const days = Math.floor(diff / (1000 * 60 * 60 * 24));
    const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
    const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));

    if (days > 0) {
      return `${days}d ${hours}h`;
    } else if (hours > 0) {
      return `${hours}h ${minutes}m`;
    } else {
      return `${minutes}m`;
    }
  };

  const liveMetrics = {
    currentPnL: task.latest_execution?.total_pnl ?? '0.00',
    openPositions: 0,
    totalTrades: task.latest_execution?.total_trades ?? 0,
    uptime: calculateUptime(),
  };

  if (task.status !== TaskStatus.RUNNING && task.status !== TaskStatus.PAUSED) {
    return (
      <Box sx={{ textAlign: 'center', py: 8 }}>
        <Typography variant="h6" color="text.secondary" gutterBottom>
          Task is not running
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Start the task to view live stats and positions
        </Typography>
      </Box>
    );
  }

  return (
    <Box>
      {/* Header with refresh button */}
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          mb: 3,
          px: 3,
        }}
      >
        <Typography variant="body2" color="text.secondary">
          Last updated: {lastUpdate.toLocaleTimeString()}
          {task.status === TaskStatus.RUNNING && ' • Auto-refreshing every 5s'}
        </Typography>
        <Button
          startIcon={
            isRefreshing ? <CircularProgress size={16} /> : <RefreshIcon />
          }
          onClick={handleManualRefresh}
          disabled={isRefreshing}
          size="small"
        >
          Refresh
        </Button>
      </Box>

      {/* Live Stats Dashboard */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <StatCard
            title="Current P&L"
            value={`$${parseFloat(liveMetrics.currentPnL).toFixed(2)}`}
            trend={parseFloat(liveMetrics.currentPnL) >= 0 ? 'up' : 'down'}
            color={
              parseFloat(liveMetrics.currentPnL) >= 0 ? 'success' : 'error'
            }
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <StatCard
            title="Open Positions"
            value={liveMetrics.openPositions.toString()}
            color="info"
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <StatCard
            title="Total Trades"
            value={liveMetrics.totalTrades.toString()}
            color="primary"
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <StatCard title="Uptime" value={liveMetrics.uptime} color="default" />
        </Grid>
      </Grid>

      {/* Open Positions */}
      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography variant="h6" gutterBottom>
          Open Positions
        </Typography>
        <OpenPositionsTable
          taskId={task.id}
          executionStartedAt={task.latest_execution?.started_at}
        />
      </Paper>

      {/* Recent Trades */}
      <Paper sx={{ p: 3 }}>
        <Typography variant="h6" gutterBottom>
          Recent Trades
        </Typography>
        <RecentTradesLog
          taskId={task.id}
          executionStartedAt={task.latest_execution?.started_at}
        />
      </Paper>
    </Box>
  );
}
