// ExecutionStatusCard component - displays current execution status and key metrics
import React from 'react';
import {
  Card,
  CardContent,
  Typography,
  Box,
  LinearProgress,
  Chip,
  Skeleton,
  Grid,
} from '@mui/material';
import {
  PlayArrow as RunningIcon,
  CheckCircle as CompletedIcon,
  Error as ErrorIcon,
  Pause as PausedIcon,
  Stop as StoppedIcon,
} from '@mui/icons-material';
import { useExecutionStatus } from '../../../hooks/useExecutionStatus';
import { formatCurrency, formatPercentage } from '../../../utils/formatters';

interface ExecutionStatusCardProps {
  executionId: number;
}

const statusConfig = {
  running: {
    label: 'Running',
    color: 'primary' as const,
    icon: <RunningIcon />,
  },
  completed: {
    label: 'Completed',
    color: 'success' as const,
    icon: <CompletedIcon />,
  },
  failed: {
    label: 'Failed',
    color: 'error' as const,
    icon: <ErrorIcon />,
  },
  paused: {
    label: 'Paused',
    color: 'warning' as const,
    icon: <PausedIcon />,
  },
  stopped: {
    label: 'Stopped',
    color: 'default' as const,
    icon: <StoppedIcon />,
  },
  pending: {
    label: 'Pending',
    color: 'info' as const,
    icon: <PausedIcon />,
  },
};

export const ExecutionStatusCard: React.FC<ExecutionStatusCardProps> = ({
  executionId,
}) => {
  const { data: status, isLoading, error } = useExecutionStatus(executionId);

  if (error) {
    return (
      <Card>
        <CardContent>
          <Typography color="error">
            Failed to load execution status: {error.message}
          </Typography>
        </CardContent>
      </Card>
    );
  }

  if (isLoading || !status) {
    return (
      <Card>
        <CardContent>
          <Skeleton variant="text" width="40%" height={32} />
          <Skeleton variant="rectangular" height={8} sx={{ my: 2 }} />
          <Grid container spacing={2}>
            <Grid size={{ xs: 6, sm: 3 }}>
              <Skeleton variant="text" />
              <Skeleton variant="text" />
            </Grid>
            <Grid size={{ xs: 6, sm: 3 }}>
              <Skeleton variant="text" />
              <Skeleton variant="text" />
            </Grid>
            <Grid size={{ xs: 6, sm: 3 }}>
              <Skeleton variant="text" />
              <Skeleton variant="text" />
            </Grid>
            <Grid size={{ xs: 6, sm: 3 }}>
              <Skeleton variant="text" />
              <Skeleton variant="text" />
            </Grid>
          </Grid>
        </CardContent>
      </Card>
    );
  }

  const statusInfo = statusConfig[
    status.status as keyof typeof statusConfig
  ] || {
    label: status.status,
    color: 'default' as const,
    icon: null,
  };

  const showProgress =
    status.status === 'running' || status.status === 'pending';
  const progress = Math.min(Math.max(status.progress || 0, 0), 100);

  return (
    <Card>
      <CardContent>
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
          <Typography variant="h6" component="h2" sx={{ flexGrow: 1 }}>
            Execution Status
          </Typography>
          <Chip
            label={statusInfo.label}
            color={statusInfo.color}
            icon={statusInfo.icon}
            size="small"
          />
        </Box>

        {showProgress && (
          <Box sx={{ mb: 3 }}>
            <Box
              sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}
            >
              <Typography variant="body2" color="text.secondary">
                Progress
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {formatPercentage(progress)}
              </Typography>
            </Box>
            <LinearProgress
              variant="determinate"
              value={progress}
              sx={{ height: 8, borderRadius: 4 }}
            />
          </Box>
        )}

        <Grid container spacing={2}>
          <Grid size={{ xs: 6, sm: 3 }}>
            <Typography variant="body2" color="text.secondary">
              Ticks Processed
            </Typography>
            <Typography variant="h6">
              {status.ticks_processed.toLocaleString()}
            </Typography>
          </Grid>

          <Grid size={{ xs: 6, sm: 3 }}>
            <Typography variant="body2" color="text.secondary">
              Trades Executed
            </Typography>
            <Typography variant="h6">
              {status.trades_executed.toLocaleString()}
            </Typography>
          </Grid>

          <Grid size={{ xs: 6, sm: 3 }}>
            <Typography variant="body2" color="text.secondary">
              Current Balance
            </Typography>
            <Typography variant="h6">
              {formatCurrency(parseFloat(status.current_balance))}
            </Typography>
          </Grid>

          <Grid size={{ xs: 6, sm: 3 }}>
            <Typography variant="body2" color="text.secondary">
              Current P&L
            </Typography>
            <Typography
              variant="h6"
              color={
                parseFloat(status.current_pnl) >= 0
                  ? 'success.main'
                  : 'error.main'
              }
            >
              {formatCurrency(parseFloat(status.current_pnl))}
            </Typography>
          </Grid>

          {status.realized_pnl != null && (
            <Grid size={{ xs: 6, sm: 3 }}>
              <Typography variant="body2" color="text.secondary">
                Realized P&L
              </Typography>
              <Typography
                variant="body1"
                color={
                  parseFloat(status.realized_pnl) >= 0
                    ? 'success.main'
                    : 'error.main'
                }
              >
                {formatCurrency(parseFloat(status.realized_pnl))}
              </Typography>
            </Grid>
          )}

          {status.unrealized_pnl != null && (
            <Grid size={{ xs: 6, sm: 3 }}>
              <Typography variant="body2" color="text.secondary">
                Unrealized P&L
              </Typography>
              <Typography
                variant="body1"
                color={
                  parseFloat(status.unrealized_pnl) >= 0
                    ? 'success.main'
                    : 'error.main'
                }
              >
                {formatCurrency(parseFloat(status.unrealized_pnl))}
              </Typography>
            </Grid>
          )}

          {status.last_tick_timestamp && (
            <Grid size={{ xs: 12, sm: 6 }}>
              <Typography variant="body2" color="text.secondary">
                Last Tick
              </Typography>
              <Typography variant="body1">
                {new Date(status.last_tick_timestamp).toLocaleString()}
              </Typography>
            </Grid>
          )}
        </Grid>
      </CardContent>
    </Card>
  );
};
