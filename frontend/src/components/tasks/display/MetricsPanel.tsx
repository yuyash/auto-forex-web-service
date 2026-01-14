// MetricsPanel component - displays current metrics from latest checkpoint
import React from 'react';
import {
  Card,
  CardContent,
  Typography,
  Box,
  Grid,
  Skeleton,
  Divider,
} from '@mui/material';
import {
  TrendingUp as UpIcon,
  TrendingDown as DownIcon,
} from '@mui/icons-material';
import { useExecutionMetrics } from '../../../hooks/useExecutionMetrics';
import { formatCurrency, formatPercentage } from '../../../utils/formatters';

interface MetricsPanelProps {
  executionId: number;
  title?: string;
}

interface MetricItemProps {
  label: string;
  value: string | number;
  color?: string;
  showTrend?: boolean;
  isPositive?: boolean;
}

const MetricItem: React.FC<MetricItemProps> = ({
  label,
  value,
  color,
  showTrend = false,
  isPositive,
}) => {
  return (
    <Box>
      <Typography variant="body2" color="text.secondary" gutterBottom>
        {label}
      </Typography>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
        <Typography variant="h6" color={color}>
          {value}
        </Typography>
        {showTrend && isPositive != null && (
          <>
            {isPositive ? (
              <UpIcon fontSize="small" color="success" />
            ) : (
              <DownIcon fontSize="small" color="error" />
            )}
          </>
        )}
      </Box>
    </Box>
  );
};

export const MetricsPanel: React.FC<MetricsPanelProps> = ({
  executionId,
  title = 'Performance Metrics',
}) => {
  const { metrics, isLoading, error } = useExecutionMetrics(executionId);

  if (error) {
    return (
      <Card>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            {title}
          </Typography>
          <Typography color="error">
            Failed to load metrics: {error.message}
          </Typography>
        </CardContent>
      </Card>
    );
  }

  if (isLoading || !metrics) {
    return (
      <Card>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            {title}
          </Typography>
          <Grid container spacing={3}>
            {[1, 2, 3, 4, 5, 6].map((i) => (
              <Grid size={{ xs: 6, sm: 4, md: 2 }} key={i}>
                <Skeleton variant="text" />
                <Skeleton variant="text" width="60%" />
              </Grid>
            ))}
          </Grid>
        </CardContent>
      </Card>
    );
  }

  const totalReturn = parseFloat(metrics.total_return);
  const totalPnl = parseFloat(metrics.total_pnl);
  const winRate = parseFloat(metrics.win_rate);
  const maxDrawdown = parseFloat(metrics.max_drawdown);
  const profitFactor = metrics.profit_factor
    ? parseFloat(metrics.profit_factor)
    : null;
  const sharpeRatio = metrics.sharpe_ratio
    ? parseFloat(metrics.sharpe_ratio)
    : null;
  const averageWin = metrics.average_win
    ? parseFloat(metrics.average_win)
    : null;
  const averageLoss = metrics.average_loss
    ? parseFloat(metrics.average_loss)
    : null;

  return (
    <Card>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          {title}
        </Typography>

        <Grid container spacing={3}>
          {/* Primary Metrics */}
          <Grid size={{ xs: 6, sm: 4, md: 2 }}>
            <MetricItem
              label="Total Return"
              value={formatPercentage(totalReturn)}
              color={totalReturn >= 0 ? 'success.main' : 'error.main'}
              showTrend
              isPositive={totalReturn >= 0}
            />
          </Grid>

          <Grid size={{ xs: 6, sm: 4, md: 2 }}>
            <MetricItem
              label="Total P&L"
              value={formatCurrency(totalPnl)}
              color={totalPnl >= 0 ? 'success.main' : 'error.main'}
              showTrend
              isPositive={totalPnl >= 0}
            />
          </Grid>

          {metrics.realized_pnl != null && (
            <Grid size={{ xs: 6, sm: 4, md: 2 }}>
              <MetricItem
                label="Realized P&L"
                value={formatCurrency(parseFloat(metrics.realized_pnl))}
                color={
                  parseFloat(metrics.realized_pnl) >= 0
                    ? 'success.main'
                    : 'error.main'
                }
              />
            </Grid>
          )}

          {metrics.unrealized_pnl != null && (
            <Grid size={{ xs: 6, sm: 4, md: 2 }}>
              <MetricItem
                label="Unrealized P&L"
                value={formatCurrency(parseFloat(metrics.unrealized_pnl))}
                color={
                  parseFloat(metrics.unrealized_pnl) >= 0
                    ? 'success.main'
                    : 'error.main'
                }
              />
            </Grid>
          )}

          <Grid size={{ xs: 6, sm: 4, md: 2 }}>
            <MetricItem
              label="Win Rate"
              value={formatPercentage(winRate)}
              color={winRate >= 50 ? 'success.main' : 'warning.main'}
            />
          </Grid>

          <Grid size={{ xs: 6, sm: 4, md: 2 }}>
            <MetricItem
              label="Max Drawdown"
              value={formatPercentage(maxDrawdown)}
              color="error.main"
            />
          </Grid>
        </Grid>

        <Divider sx={{ my: 2 }} />

        <Grid container spacing={3}>
          {/* Trade Statistics */}
          <Grid size={{ xs: 6, sm: 4, md: 2 }}>
            <MetricItem
              label="Total Trades"
              value={metrics.total_trades.toLocaleString()}
            />
          </Grid>

          <Grid size={{ xs: 6, sm: 4, md: 2 }}>
            <MetricItem
              label="Winning Trades"
              value={metrics.winning_trades.toLocaleString()}
              color="success.main"
            />
          </Grid>

          <Grid size={{ xs: 6, sm: 4, md: 2 }}>
            <MetricItem
              label="Losing Trades"
              value={metrics.losing_trades.toLocaleString()}
              color="error.main"
            />
          </Grid>

          {profitFactor != null && (
            <Grid size={{ xs: 6, sm: 4, md: 2 }}>
              <MetricItem
                label="Profit Factor"
                value={profitFactor.toFixed(2)}
                color={profitFactor >= 1.5 ? 'success.main' : 'warning.main'}
              />
            </Grid>
          )}

          {sharpeRatio != null && (
            <Grid size={{ xs: 6, sm: 4, md: 2 }}>
              <MetricItem
                label="Sharpe Ratio"
                value={sharpeRatio.toFixed(2)}
                color={sharpeRatio >= 1 ? 'success.main' : 'warning.main'}
              />
            </Grid>
          )}

          {averageWin != null && (
            <Grid size={{ xs: 6, sm: 4, md: 2 }}>
              <MetricItem
                label="Avg Win"
                value={formatCurrency(averageWin)}
                color="success.main"
              />
            </Grid>
          )}

          {averageLoss != null && (
            <Grid size={{ xs: 6, sm: 4, md: 2 }}>
              <MetricItem
                label="Avg Loss"
                value={formatCurrency(Math.abs(averageLoss))}
                color="error.main"
              />
            </Grid>
          )}
        </Grid>
      </CardContent>
    </Card>
  );
};
