// CompleteEquityChart component - displays complete equity curve with zooming and panning
import React, { useState, useMemo } from 'react';
import {
  Card,
  CardContent,
  Typography,
  Box,
  Skeleton,
  useTheme,
  ButtonGroup,
  Button,
  IconButton,
  Tooltip,
} from '@mui/material';
import {
  ZoomIn as ZoomInIcon,
  ZoomOut as ZoomOutIcon,
  ZoomOutMap as ResetIcon,
} from '@mui/icons-material';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
  Legend,
  Brush,
  ReferenceLine,
} from 'recharts';
import { formatCurrency } from '../../../utils/formatters';
import type { EquityPoint } from '../../../types';

interface CompleteEquityChartProps {
  equityPoints: EquityPoint[];
  title?: string;
  height?: number;
  isLoading?: boolean;
  error?: Error | null;
}

interface ChartDataPoint {
  timestamp: string;
  balance: number;
  realized_pnl?: number;
  unrealized_pnl?: number;
  displayTime: string;
  displayDate: string;
}

type TimeRange = 'all' | '1h' | '6h' | '1d' | '7d' | '30d';

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
          boxShadow: 2,
        }}
      >
        <Typography variant="body2" fontWeight="bold" sx={{ mb: 0.5 }}>
          {data.displayDate} {data.displayTime}
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

export const CompleteEquityChart: React.FC<CompleteEquityChartProps> = ({
  equityPoints,
  title = 'Complete Equity Curve',
  height = 500,
  isLoading = false,
  error = null,
}) => {
  const theme = useTheme();
  const [timeRange, setTimeRange] = useState<TimeRange>('all');
  const [zoomDomain, setZoomDomain] = useState<[number, number] | null>(null);

  const chartData: ChartDataPoint[] = useMemo(() => {
    return equityPoints.map((point: EquityPoint) => {
      const date = new Date(point.timestamp);
      return {
        timestamp: point.timestamp,
        balance: point.balance,
        realized_pnl: point.realized_pnl,
        unrealized_pnl: point.unrealized_pnl,
        displayTime: date.toLocaleTimeString(),
        displayDate: date.toLocaleDateString(),
      };
    });
  }, [equityPoints]);

  const filteredData = useMemo(() => {
    if (timeRange === 'all') return chartData;

    const now = new Date();
    const timeRangeMs: Record<TimeRange, number> = {
      all: 0,
      '1h': 60 * 60 * 1000,
      '6h': 6 * 60 * 60 * 1000,
      '1d': 24 * 60 * 60 * 1000,
      '7d': 7 * 24 * 60 * 60 * 1000,
      '30d': 30 * 24 * 60 * 60 * 1000,
    };

    const cutoffTime = now.getTime() - timeRangeMs[timeRange];
    return chartData.filter(
      (point) => new Date(point.timestamp).getTime() >= cutoffTime
    );
  }, [chartData, timeRange]);

  const displayData = zoomDomain
    ? filteredData.slice(zoomDomain[0], zoomDomain[1])
    : filteredData;

  const { minBalance, maxBalance, initialBalance, finalBalance } =
    useMemo(() => {
      if (displayData.length === 0) {
        return {
          minBalance: 0,
          maxBalance: 0,
          initialBalance: 0,
          finalBalance: 0,
        };
      }

      const balances = displayData.map((d) => d.balance);
      return {
        minBalance: Math.min(...balances),
        maxBalance: Math.max(...balances),
        initialBalance: displayData[0].balance,
        finalBalance: displayData[displayData.length - 1].balance,
      };
    }, [displayData]);

  const handleZoomIn = () => {
    if (displayData.length < 10) return;
    const start = Math.floor(displayData.length * 0.25);
    const end = Math.floor(displayData.length * 0.75);
    setZoomDomain([start, end]);
  };

  const handleZoomOut = () => {
    setZoomDomain(null);
  };

  const handleReset = () => {
    setTimeRange('all');
    setZoomDomain(null);
  };

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
            <Typography>No equity data available</Typography>
          </Box>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardContent>
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            mb: 2,
          }}
        >
          <Typography variant="h6">{title}</Typography>

          <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
            {/* Time Range Selector */}
            <ButtonGroup size="small" variant="outlined">
              <Button
                onClick={() => setTimeRange('1h')}
                variant={timeRange === '1h' ? 'contained' : 'outlined'}
              >
                1H
              </Button>
              <Button
                onClick={() => setTimeRange('6h')}
                variant={timeRange === '6h' ? 'contained' : 'outlined'}
              >
                6H
              </Button>
              <Button
                onClick={() => setTimeRange('1d')}
                variant={timeRange === '1d' ? 'contained' : 'outlined'}
              >
                1D
              </Button>
              <Button
                onClick={() => setTimeRange('7d')}
                variant={timeRange === '7d' ? 'contained' : 'outlined'}
              >
                7D
              </Button>
              <Button
                onClick={() => setTimeRange('30d')}
                variant={timeRange === '30d' ? 'contained' : 'outlined'}
              >
                30D
              </Button>
              <Button
                onClick={() => setTimeRange('all')}
                variant={timeRange === 'all' ? 'contained' : 'outlined'}
              >
                All
              </Button>
            </ButtonGroup>

            {/* Zoom Controls */}
            <Box>
              <Tooltip title="Zoom In">
                <IconButton
                  size="small"
                  onClick={handleZoomIn}
                  disabled={displayData.length < 10}
                >
                  <ZoomInIcon />
                </IconButton>
              </Tooltip>
              <Tooltip title="Zoom Out">
                <IconButton
                  size="small"
                  onClick={handleZoomOut}
                  disabled={!zoomDomain}
                >
                  <ZoomOutIcon />
                </IconButton>
              </Tooltip>
              <Tooltip title="Reset View">
                <IconButton size="small" onClick={handleReset}>
                  <ResetIcon />
                </IconButton>
              </Tooltip>
            </Box>
          </Box>
        </Box>

        {/* Summary Stats */}
        <Box
          sx={{
            display: 'flex',
            gap: 3,
            mb: 2,
            p: 1,
            bgcolor: 'background.default',
            borderRadius: 1,
          }}
        >
          <Box>
            <Typography variant="caption" color="text.secondary">
              Initial Balance
            </Typography>
            <Typography variant="body2" fontWeight="bold">
              {formatCurrency(initialBalance)}
            </Typography>
          </Box>
          <Box>
            <Typography variant="caption" color="text.secondary">
              Final Balance
            </Typography>
            <Typography
              variant="body2"
              fontWeight="bold"
              color={
                finalBalance >= initialBalance ? 'success.main' : 'error.main'
              }
            >
              {formatCurrency(finalBalance)}
            </Typography>
          </Box>
          <Box>
            <Typography variant="caption" color="text.secondary">
              Peak Balance
            </Typography>
            <Typography variant="body2" fontWeight="bold" color="success.main">
              {formatCurrency(maxBalance)}
            </Typography>
          </Box>
          <Box>
            <Typography variant="caption" color="text.secondary">
              Lowest Balance
            </Typography>
            <Typography variant="body2" fontWeight="bold" color="error.main">
              {formatCurrency(minBalance)}
            </Typography>
          </Box>
        </Box>

        <ResponsiveContainer width="100%" height={height}>
          <LineChart
            data={displayData}
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
              angle={-45}
              textAnchor="end"
              height={80}
            />
            <YAxis
              stroke={theme.palette.text.secondary}
              tick={{ fontSize: 12 }}
              tickFormatter={(value) => formatCurrency(value)}
              domain={['auto', 'auto']}
            />
            <RechartsTooltip content={<CustomTooltip />} />
            <Legend />

            {/* Reference line for initial balance */}
            <ReferenceLine
              y={initialBalance}
              stroke={theme.palette.text.disabled}
              strokeDasharray="3 3"
              label={{ value: 'Initial', position: 'right', fontSize: 12 }}
            />

            <Line
              type="monotone"
              dataKey="balance"
              stroke={theme.palette.primary.main}
              strokeWidth={2}
              dot={false}
              name="Balance"
              isAnimationActive={false}
            />

            {/* Brush for panning */}
            {!zoomDomain && filteredData.length > 50 && (
              <Brush
                dataKey="displayTime"
                height={30}
                stroke={theme.palette.primary.main}
                fill={theme.palette.background.default}
              />
            )}
          </LineChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
};
