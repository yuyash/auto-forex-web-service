// ExecutionSummaryCard component - displays final metrics and status for completed executions
import React from 'react';
import {
  Card,
  CardContent,
  Typography,
  Box,
  Chip,
  Skeleton,
  Divider,
} from '@mui/material';
import Grid from '@mui/material/Grid';
import {
  CheckCircle as CompletedIcon,
  Error as ErrorIcon,
  Stop as StoppedIcon,
  TrendingUp as TrendingUpIcon,
  TrendingDown as TrendingDownIcon,
} from '@mui/icons-material';
import { formatCurrency, formatPercentage } from '../../../utils/formatters';
import type { TaskExecution } from '../../../types';

interface ExecutionSummaryCardProps {
  execution: TaskExecution;
}

const statusConfig = {
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
  stopped: {
    label: 'Stopped',
    color: 'default' as const,
    icon: <StoppedIcon />,
  },
};

export const ExecutionSummaryCard: React.FC<ExecutionSummaryCardProps> = ({
  execution,
}) => {
  const metrics = execution.metrics;
  
  if (!execution) {
    return (
      <Card>
        <CardContent>
          <Skeleton variant="text" width="40%" height={32} />
          <Skeleton variant="rectangular" height={100} sx={{ my: 2 }} />
        </CardContent>
      </Card>
    );
  }

  const statusInfo = statusConfig[execution.status as keyof typeof statusConfig] || {
    label: execution.status,
    color: 'default' as const,
    icon: null,
  };

  const totalReturn = metrics?.total_return ? parseFloat(metrics.total_return) : 0;
  const totalPnl = metrics?.total_pnl ? parseFloat(metrics.total_pnl) : 0;
  const winRate = metrics?.win_rate ? parseFloat(metrics.win_rate) : 0;
  const maxDrawdown = metrics?.max_drawdown ? parseFloat(metrics.max_drawdown) : 0;

  const formatDuration = (started: string, completed?: string) => {
    if (!completed) return 'N/A';
    const start = new Date(started);
    const end = new Date(completed);
    const durationMs = end.getTime() - start.getTime();
    const hours = Math.floor(durationMs / (1000 * 60 * 60));
    const minutes = Math.floor((durationMs % (1000 * 60 * 60)) / (1000 * 60));
    const seconds = Math.floor((durationMs % (1000 * 60)) / 1000);
    
    if (hours > 0) {
      return `${hours}h ${minutes}m ${seconds}s`;
    } else if (minutes > 0) {
      return `${minutes}m ${seconds}s`;
    } else {
      return `${seconds}s`;
    }
  };

  return (
    <Card>
      <CardContent>
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
          <Box sx={{ flexGrow: 1 }}>
            <Typography variant="h5" component="h2">
              Execution #{execution.execution_number}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {execution.task_type === 'backtest' ? 'Backtest' : 'Trading'} Execution Summary
            </Typography>
          </Box>
          <Chip
            label={statusInfo.label}
            color={statusInfo.color}
            icon={statusInfo.icon}
            size="medium"
          />
        </Box>

        <Divider sx={{ my: 2 }} />

        {/* Execution Details */}
        <Grid container spacing={2} sx={{ mb: 3 }}>
          <Grid size={{ xs: 6, sm: 4 }}>
            <Typography variant="body2" color="text.secondary">
              Started
            </Typography>
            <Typography variant="body1">
              {new Date(execution.started_at).toLocaleString()}
            </Typography>
          </Grid>

          {execution.completed_at && (
            <Grid size={{ xs: 6, sm: 4 }}>
              <Typography variant="body2" color="text.secondary">
                Completed
              </Typography>
              <Typography variant="body1">
                {new Date(execution.completed_at).toLocaleString()}
              </Typography>
            </Grid>
          )}

          <Grid size={{ xs: 6, sm: 4 }}>
            <Typography variant="body2" color="text.secondary">
              Duration
            </Typography>
            <Typography variant="body1">
              {formatDuration(execution.started_at, execution.completed_at)}
            </Typography>
          </Grid>
        </Grid>

        {execution.error_message && (
          <Box sx={{ mb: 3, p: 2, bgcolor: 'error.light', borderRadius: 1 }}>
            <Typography variant="body2" color="error.dark" fontWeight="bold">
              Error:
            </Typography>
            <Typography variant="body2" color="error.dark">
              {execution.error_message}
            </Typography>
          </Box>
        )}

        {!metrics && (
          <Box sx={{ textAlign: 'center', py: 4 }}>
            <Typography variant="body1" color="text.secondary">
              No metrics available for this execution.
            </Typography>
            <Typography variant="body2" color="text.secondary">
              The execution may have completed without generating results or is still processing.
            </Typography>
          </Box>
        )}

        {metrics && (
          <>
            <Divider sx={{ my: 2 }} />
            
            {/* Performance Metrics */}
            <Typography variant="h6" gutterBottom>
              Performance Metrics
            </Typography>
            
            <Grid container spacing={3}>
              {/* Total Return */}
              <Grid size={{ xs: 6, sm: 3 }}>
                <Box sx={{ textAlign: 'center', p: 2, bgcolor: 'background.default', borderRadius: 1 }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', mb: 1 }}>
                    {totalReturn >= 0 ? (
                      <TrendingUpIcon color="success" />
                    ) : (
                      <TrendingDownIcon color="error" />
                    )}
                  </Box>
                  <Typography variant="body2" color="text.secondary">
                    Total Return
                  </Typography>
                  <Typography
                    variant="h5"
                    color={totalReturn >= 0 ? 'success.main' : 'error.main'}
                    fontWeight="bold"
                  >
                    {formatPercentage(totalReturn)}
                  </Typography>
                </Box>
              </Grid>

              {/* Total P&L */}
              <Grid size={{ xs: 6, sm: 3 }}>
                <Box sx={{ textAlign: 'center', p: 2, bgcolor: 'background.default', borderRadius: 1 }}>
                  <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                    Total P&L
                  </Typography>
                  <Typography
                    variant="h5"
                    color={totalPnl >= 0 ? 'success.main' : 'error.main'}
                    fontWeight="bold"
                  >
                    {formatCurrency(totalPnl)}
                  </Typography>
                  {metrics.realized_pnl && (
                    <Typography variant="caption" color="text.secondary">
                      Realized: {formatCurrency(parseFloat(metrics.realized_pnl))}
                    </Typography>
                  )}
                </Box>
              </Grid>

              {/* Win Rate */}
              <Grid size={{ xs: 6, sm: 3 }}>
                <Box sx={{ textAlign: 'center', p: 2, bgcolor: 'background.default', borderRadius: 1 }}>
                  <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                    Win Rate
                  </Typography>
                  <Typography variant="h5" fontWeight="bold">
                    {formatPercentage(winRate)}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    {metrics.winning_trades}/{metrics.total_trades} trades
                  </Typography>
                </Box>
              </Grid>

              {/* Max Drawdown */}
              <Grid size={{ xs: 6, sm: 3 }}>
                <Box sx={{ textAlign: 'center', p: 2, bgcolor: 'background.default', borderRadius: 1 }}>
                  <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                    Max Drawdown
                  </Typography>
                  <Typography variant="h5" color="error.main" fontWeight="bold">
                    {formatPercentage(Math.abs(maxDrawdown))}
                  </Typography>
                </Box>
              </Grid>

              {/* Additional Metrics */}
              {metrics.sharpe_ratio && (
                <Grid size={{ xs: 6, sm: 3 }}>
                  <Typography variant="body2" color="text.secondary">
                    Sharpe Ratio
                  </Typography>
                  <Typography variant="h6">
                    {parseFloat(metrics.sharpe_ratio).toFixed(2)}
                  </Typography>
                </Grid>
              )}

              {metrics.profit_factor && (
                <Grid size={{ xs: 6, sm: 3 }}>
                  <Typography variant="body2" color="text.secondary">
                    Profit Factor
                  </Typography>
                  <Typography variant="h6">
                    {parseFloat(metrics.profit_factor).toFixed(2)}
                  </Typography>
                </Grid>
              )}

              {metrics.average_win && (
                <Grid size={{ xs: 6, sm: 3 }}>
                  <Typography variant="body2" color="text.secondary">
                    Avg Win
                  </Typography>
                  <Typography variant="h6" color="success.main">
                    {formatCurrency(parseFloat(metrics.average_win))}
                  </Typography>
                </Grid>
              )}

              {metrics.average_loss && (
                <Grid size={{ xs: 6, sm: 3 }}>
                  <Typography variant="body2" color="text.secondary">
                    Avg Loss
                  </Typography>
                  <Typography variant="h6" color="error.main">
                    {formatCurrency(parseFloat(metrics.average_loss))}
                  </Typography>
                </Grid>
              )}
            </Grid>
          </>
        )}
      </CardContent>
    </Card>
  );
};
