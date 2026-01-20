import React from 'react';
import { Box } from '@mui/material';

import { MetricCard } from '../display/MetricCard';
import {
  TrendingUp,
  ShowChart,
  Assessment,
  AccountBalance,
  Timeline,
  Speed,
} from '@mui/icons-material';
import type { ExecutionMetrics } from '../../../types/execution';

interface MetricsGridProps {
  metrics: ExecutionMetrics;
  isLoading?: boolean;
  columns?: 2 | 3 | 4;
}

export const MetricsGrid: React.FC<MetricsGridProps> = ({
  metrics,
  isLoading = false,
  columns = 3,
}) => {
  const safeNumber = (
    value: string | number | null | undefined,
    fallback = 0
  ): number => {
    if (value === null || value === undefined) return fallback;
    const num = typeof value === 'string' ? Number(value) : value;
    return Number.isFinite(num) ? num : fallback;
  };

  const formatPercentage = (value: string | number): string => {
    const num = safeNumber(value, 0);
    return `${num >= 0 ? '+' : ''}${num.toFixed(2)}%`;
  };

  const formatCurrency = (value: string | number): string => {
    const num = safeNumber(value, 0);
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(num);
  };

  const formatNumber = (value: number, decimals: number = 2): string => {
    return value.toFixed(decimals);
  };

  const getTrend = (value: string | number): 'up' | 'down' | 'neutral' => {
    const num = safeNumber(value, 0);
    if (num > 0) return 'up';
    if (num < 0) return 'down';
    return 'neutral';
  };

  const realizedPnl = safeNumber(
    metrics.realized_pnl,
    safeNumber(metrics.total_pnl, 0)
  );
  const unrealizedPnl = safeNumber(metrics.unrealized_pnl, 0);

  const metricsData = [
    {
      title: 'Total Return',
      value: formatPercentage(metrics.total_return),
      icon: <TrendingUp />,
      color:
        safeNumber(metrics.total_return.toString(), 0) >= 0
          ? 'success'
          : 'error',
      trend: getTrend(metrics.total_return),
    },
    {
      title: 'Total P&L',
      value: formatCurrency(metrics.total_pnl),
      icon: <AccountBalance />,
      color:
        safeNumber(metrics.total_pnl.toString(), 0) >= 0 ? 'success' : 'error',
      trend: getTrend(metrics.total_pnl),
    },
    {
      title: 'Realized P&L',
      value: formatCurrency(realizedPnl),
      icon: <AccountBalance />,
      color: realizedPnl >= 0 ? 'success' : 'error',
      trend: getTrend(realizedPnl),
    },
    {
      title: 'Unrealized P&L',
      value: formatCurrency(unrealizedPnl),
      icon: <AccountBalance />,
      color: unrealizedPnl >= 0 ? 'success' : 'error',
      trend: getTrend(unrealizedPnl),
    },
    {
      title: 'Total Trades',
      value: metrics.total_trades,
      subtitle: `${metrics.winning_trades}W / ${metrics.losing_trades}L`,
      icon: <Assessment />,
      color: 'primary',
    },
    {
      title: 'Win Rate',
      value: formatPercentage(metrics.win_rate),
      icon: <ShowChart />,
      color:
        safeNumber(metrics.win_rate.toString(), 0) >= 50
          ? 'success'
          : 'warning',
    },
    {
      title: 'Max Drawdown',
      value: formatPercentage(metrics.max_drawdown),
      icon: <Timeline />,
      color: 'error',
    },
  ];

  // Add optional metrics if available
  if (metrics.sharpe_ratio) {
    metricsData.push({
      title: 'Sharpe Ratio',
      value: formatNumber(parseFloat(metrics.sharpe_ratio), 2),
      icon: <Speed />,
      color: parseFloat(metrics.sharpe_ratio) >= 1 ? 'success' : 'warning',
    });
  }

  if (metrics.profit_factor) {
    metricsData.push({
      title: 'Profit Factor',
      value: formatNumber(parseFloat(metrics.profit_factor), 2),
      icon: <TrendingUp />,
      color: parseFloat(metrics.profit_factor) >= 1.5 ? 'success' : 'warning',
    });
  }

  return (
    <Box
      sx={{
        display: 'grid',
        gridTemplateColumns: {
          xs: '1fr',
          sm: 'repeat(2, 1fr)',
          md: `repeat(${columns}, 1fr)`,
        },
        gap: 2,
      }}
    >
      {metricsData.map((metric, index) => (
        <MetricCard
          key={index}
          title={metric.title}
          value={metric.value}
          subtitle={metric.subtitle}
          icon={metric.icon}
          color={
            metric.color as
              | 'primary'
              | 'default'
              | 'error'
              | 'warning'
              | 'info'
              | 'success'
          }
          trend={metric.trend}
          isLoading={isLoading}
        />
      ))}
    </Box>
  );
};
