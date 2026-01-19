// EquityChart component - displays equity curve with real-time updates
import React, { useMemo } from 'react';
import {
  Card,
  CardContent,
  Typography,
  Box,
  Skeleton,
  useTheme,
} from '@mui/material';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';
import { useExecutionEquity } from '../../../hooks/useExecutionEquity';
import { formatCurrency, formatDateTime } from '../../../utils/formatters';
import type { EquityPoint } from '../../../types';

interface EquityChartProps {
  executionId: number;
  title?: string;
  height?: number;
}

interface ChartDataPoint {
  timestamp: string;
  balance: number;
  realized_pnl?: number;
  unrealized_pnl?: number;
  displayTime: string;
}

interface TooltipProps {
  active?: boolean;
  payload?: Array<{ payload: ChartDataPoint }>;
}

const CustomTooltip: React.FC<TooltipProps> = ({ active, payload }) => {
  if (active && payload && payload.length) {
    const data = payload[0].payload;
    return (
      <Box
        sx={{
          bgcolor: 'background.paper',
          p: 1.5,
          border: 1,
          borderColor: 'divider',
          borderRadius: 1,
        }}
      >
        <Typography variant="body2" sx={{ mb: 0.5 }}>
          {formatDateTime(data.timestamp)}
        </Typography>
        <Typography variant="body2" color="primary">
          Balance: {formatCurrency(data.balance)}
        </Typography>
        {data.realized_pnl != null && (
          <Typography
            variant="body2"
            color={data.realized_pnl >= 0 ? 'success.main' : 'error.main'}
          >
            Realized P&L: {formatCurrency(data.realized_pnl)}
          </Typography>
        )}
        {data.unrealized_pnl != null && (
          <Typography
            variant="body2"
            color={data.unrealized_pnl >= 0 ? 'success.main' : 'error.main'}
          >
            Unrealized P&L: {formatCurrency(data.unrealized_pnl)}
          </Typography>
        )}
      </Box>
    );
  }
  return null;
};

export const EquityChart: React.FC<EquityChartProps> = ({
  executionId,
  title = 'Equity Curve',
  height = 400,
}) => {
  const theme = useTheme();
  const { equityPoints, isLoading, error } = useExecutionEquity(executionId);

  const chartData: ChartDataPoint[] = useMemo(() => {
    return equityPoints.map((point: EquityPoint) => ({
      timestamp: point.timestamp,
      balance: point.balance,
      realized_pnl: point.realized_pnl,
      unrealized_pnl: point.unrealized_pnl,
      displayTime: new Date(point.timestamp).toLocaleTimeString(),
    }));
  }, [equityPoints]);

  if (error) {
    return (
      <Card>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            {title}
          </Typography>
          <Typography color="error">
            Failed to load equity data: {error.message}
          </Typography>
        </CardContent>
      </Card>
    );
  }

  if (isLoading) {
    return (
      <Card>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            {title}
          </Typography>
          <Skeleton variant="rectangular" height={height} />
        </CardContent>
      </Card>
    );
  }

  if (chartData.length === 0) {
    return (
      <Card>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            {title}
          </Typography>
          <Box
            sx={{
              height,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'text.secondary',
            }}
          >
            <Typography>No equity data available yet</Typography>
          </Box>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          {title}
        </Typography>
        <ResponsiveContainer width="100%" height={height}>
          <LineChart
            data={chartData}
            margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
          >
            <CartesianGrid
              strokeDasharray="3 3"
              stroke={theme.palette.divider}
            />
            <XAxis
              dataKey="displayTime"
              stroke={theme.palette.text.secondary}
              tick={{ fontSize: 12 }}
            />
            <YAxis
              stroke={theme.palette.text.secondary}
              tick={{ fontSize: 12 }}
              tickFormatter={(value) => formatCurrency(value)}
            />
            <Tooltip content={<CustomTooltip />} />
            <Legend />
            <Line
              type="monotone"
              dataKey="balance"
              stroke={theme.palette.primary.main}
              strokeWidth={2}
              dot={false}
              name="Balance"
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
};
