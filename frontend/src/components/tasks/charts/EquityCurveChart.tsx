import React from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
  CartesianGrid,
} from 'recharts';
import {
  Box,
  Paper,
  Typography,
  IconButton,
  Tooltip as MuiTooltip,
} from '@mui/material';

import DownloadIcon from '@mui/icons-material/Download';
import { format } from 'date-fns';

// Helper to determine optimal tick configuration based on date range
interface TickConfig {
  tickCount: number;
  dateFormat: string;
  showTime: boolean;
}

function getXAxisTickConfig(startTime: number, endTime: number): TickConfig {
  const rangeMs = endTime - startTime;
  const rangeHours = rangeMs / (1000 * 60 * 60);
  const rangeDays = rangeMs / (1000 * 60 * 60 * 24);

  // Less than 24 hours: show time with hours
  if (rangeHours <= 24) {
    return {
      tickCount: Math.min(12, Math.max(4, Math.ceil(rangeHours / 2))),
      dateFormat: 'HH:mm',
      showTime: true,
    };
  }

  // 1-3 days: show date + time
  if (rangeDays <= 3) {
    return {
      tickCount: Math.min(12, Math.max(6, Math.ceil(rangeHours / 6))),
      dateFormat: 'MMM dd HH:mm',
      showTime: true,
    };
  }

  // 3-14 days: show date only, more ticks
  if (rangeDays <= 14) {
    return {
      tickCount: Math.min(14, Math.max(7, Math.ceil(rangeDays))),
      dateFormat: 'MMM dd',
      showTime: false,
    };
  }

  // 14-60 days: show date, moderate ticks
  if (rangeDays <= 60) {
    return {
      tickCount: Math.min(15, Math.max(8, Math.ceil(rangeDays / 4))),
      dateFormat: 'MMM dd',
      showTime: false,
    };
  }

  // 60-180 days: show date, fewer ticks
  if (rangeDays <= 180) {
    return {
      tickCount: Math.min(12, Math.max(6, Math.ceil(rangeDays / 15))),
      dateFormat: 'MMM dd',
      showTime: false,
    };
  }

  // More than 180 days: show month/year
  return {
    tickCount: Math.min(12, Math.max(6, Math.ceil(rangeDays / 30))),
    dateFormat: "MMM ''yy",
    showTime: false,
  };
}

// Helper to determine optimal Y-axis tick count based on value range
function getYAxisTickCount(minValue: number, maxValue: number): number {
  const range = maxValue - minValue;
  if (range === 0) return 5;

  // Calculate a reasonable number of ticks based on the range magnitude
  const magnitude = Math.floor(Math.log10(range));
  const normalizedRange = range / Math.pow(10, magnitude);

  // Aim for 5-10 ticks depending on the range
  if (normalizedRange <= 2) {
    return 8;
  } else if (normalizedRange <= 5) {
    return 10;
  } else {
    return 6;
  }
}

export interface EquityPoint {
  timestamp: string;
  balance: number;
}

interface EquityCurveChartProps {
  data: EquityPoint[];
  initialBalance?: number;
  title?: string;
  height?: number;
  showExport?: boolean;
  onExport?: () => void;
}

// Custom tooltip component defined outside render
interface CustomTooltipProps {
  active?: boolean;
  payload?: Array<{
    payload: {
      date: string;
      balance: number;
    };
  }>;
  stats: {
    startBalance: number;
  } | null;
  formatCurrency: (value: number) => string;
}

const CustomTooltip: React.FC<CustomTooltipProps> = ({
  active,
  payload,
  stats,
  formatCurrency,
}) => {
  if (active && payload && payload.length) {
    const data = payload[0].payload;
    return (
      <Paper sx={{ p: 1.5, border: 1, borderColor: 'divider' }}>
        <Typography variant="body2" sx={{ fontWeight: 600, mb: 0.5 }}>
          {data.date}
        </Typography>
        <Typography variant="body2" color="primary">
          Balance: {formatCurrency(data.balance)}
        </Typography>
        {stats && (
          <Typography variant="caption" color="text.secondary">
            Return:{' '}
            {(
              ((data.balance - stats.startBalance) / stats.startBalance) *
              100
            ).toFixed(2)}
            %
          </Typography>
        )}
      </Paper>
    );
  }
  return null;
};

export const EquityCurveChart: React.FC<EquityCurveChartProps> = ({
  data,
  initialBalance,
  title = 'Equity Curve',
  height = 400,
  showExport = true,
  onExport,
}) => {
  // Format data for recharts
  const chartData = React.useMemo(() => {
    return data.map((point) => ({
      timestamp: new Date(point.timestamp).getTime(),
      balance: parseFloat(point.balance.toString()),
      date: format(new Date(point.timestamp), 'MMM dd, yyyy HH:mm'),
    }));
  }, [data]);

  // Calculate statistics
  const stats = React.useMemo(() => {
    if (chartData.length === 0) return null;

    const balances = chartData.map((d) => d.balance);
    const maxBalance = Math.max(...balances);
    const minBalance = Math.min(...balances);
    const finalBalance = balances[balances.length - 1];
    const startBalance = initialBalance || balances[0];
    const totalReturn = ((finalBalance - startBalance) / startBalance) * 100;

    // Calculate max drawdown
    let maxDrawdown = 0;
    let peak = balances[0];
    for (const balance of balances) {
      if (balance > peak) {
        peak = balance;
      }
      const drawdown = ((peak - balance) / peak) * 100;
      if (drawdown > maxDrawdown) {
        maxDrawdown = drawdown;
      }
    }

    return {
      maxBalance,
      minBalance,
      finalBalance,
      startBalance,
      totalReturn,
      maxDrawdown,
    };
  }, [chartData, initialBalance]);

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(value);
  };

  const formatYAxis = (value: number) => {
    if (value >= 1000000) {
      return `$${(value / 1000000).toFixed(1)}M`;
    } else if (value >= 1000) {
      return `$${(value / 1000).toFixed(1)}K`;
    }
    return `$${value.toFixed(0)}`;
  };

  // Calculate tick configurations based on data range
  const axisConfig = React.useMemo(() => {
    if (chartData.length === 0) {
      return {
        xAxis: { tickCount: 5, dateFormat: 'MMM dd', showTime: false },
        yAxisTickCount: 5,
      };
    }

    const timestamps = chartData.map((d) => d.timestamp);
    const startTime = Math.min(...timestamps);
    const endTime = Math.max(...timestamps);

    const balances = chartData.map((d) => d.balance);
    const minBalance = Math.min(...balances);
    const maxBalance = Math.max(...balances);

    return {
      xAxis: getXAxisTickConfig(startTime, endTime),
      yAxisTickCount: getYAxisTickCount(minBalance, maxBalance),
    };
  }, [chartData]);

  if (chartData.length === 0) {
    return (
      <Paper sx={{ p: 3, textAlign: 'center' }}>
        <Typography variant="body2" color="text.secondary">
          No equity curve data available
        </Typography>
      </Paper>
    );
  }

  return (
    <Paper sx={{ p: 2 }}>
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          mb: 2,
        }}
      >
        <Typography variant="h6">{title}</Typography>
        {showExport && onExport && (
          <MuiTooltip title="Export chart data">
            <IconButton size="small" onClick={onExport}>
              <DownloadIcon />
            </IconButton>
          </MuiTooltip>
        )}
      </Box>

      {stats && (
        <Box sx={{ display: 'flex', gap: 3, mb: 2, flexWrap: 'wrap' }}>
          <Box>
            <Typography variant="caption" color="text.secondary">
              Total Return
            </Typography>
            <Typography
              variant="body1"
              sx={{
                fontWeight: 600,
                color: stats.totalReturn >= 0 ? 'success.main' : 'error.main',
              }}
            >
              {stats.totalReturn >= 0 ? '+' : ''}
              {stats.totalReturn.toFixed(2)}%
            </Typography>
          </Box>
          <Box>
            <Typography variant="caption" color="text.secondary">
              Max Drawdown
            </Typography>
            <Typography
              variant="body1"
              sx={{ fontWeight: 600, color: 'error.main' }}
            >
              -{stats.maxDrawdown.toFixed(2)}%
            </Typography>
          </Box>
          <Box>
            <Typography variant="caption" color="text.secondary">
              Final Balance
            </Typography>
            <Typography variant="body1" sx={{ fontWeight: 600 }}>
              {formatCurrency(stats.finalBalance)}
            </Typography>
          </Box>
        </Box>
      )}

      <ResponsiveContainer width="100%" height={height}>
        <LineChart
          data={chartData}
          margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#e0e0e0" />
          <XAxis
            dataKey="timestamp"
            type="number"
            domain={['dataMin', 'dataMax']}
            tickCount={axisConfig.xAxis.tickCount}
            tickFormatter={(timestamp) =>
              format(new Date(timestamp), axisConfig.xAxis.dateFormat)
            }
            stroke="#666"
            fontSize={12}
            angle={axisConfig.xAxis.showTime ? -45 : 0}
            textAnchor={axisConfig.xAxis.showTime ? 'end' : 'middle'}
            height={axisConfig.xAxis.showTime ? 60 : 30}
          />
          <YAxis
            tickFormatter={formatYAxis}
            stroke="#666"
            domain={['auto', 'auto']}
            tickCount={axisConfig.yAxisTickCount}
            fontSize={12}
            width={70}
          />
          <Tooltip
            content={
              <CustomTooltip stats={stats} formatCurrency={formatCurrency} />
            }
          />
          <Legend />
          {initialBalance && (
            <ReferenceLine
              y={initialBalance}
              stroke="#999"
              strokeDasharray="3 3"
              label="Initial"
            />
          )}
          <Line
            type="monotone"
            dataKey="balance"
            stroke="#1976d2"
            strokeWidth={2}
            dot={false}
            name="Balance"
            animationDuration={500}
          />
        </LineChart>
      </ResponsiveContainer>
    </Paper>
  );
};
