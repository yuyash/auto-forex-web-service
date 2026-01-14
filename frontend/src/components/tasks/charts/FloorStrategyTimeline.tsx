// FloorStrategyTimeline component - renders Floor strategy events on a timeline chart
import React, { useMemo } from 'react';
import {
  Card,
  CardContent,
  Typography,
  Box,
  Skeleton,
  useTheme,
  Chip,
} from '@mui/material';
import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ZAxis,
} from 'recharts';
import { useExecutionEvents } from '../../../hooks/useExecutionEvents';
import { formatDateTime, formatCurrency } from '../../../utils/formatters';
import type { BacktestStrategyEvent } from '../../../types';

interface FloorStrategyTimelineProps {
  executionId: number;
  title?: string;
  height?: number;
}

interface TimelineDataPoint {
  timestamp: string;
  displayTime: string;
  layer_number: number;
  retracement_count: number;
  event_type: string;
  price?: number;
  pnl?: number;
  direction?: string;
  size: number; // For scatter plot sizing
}

interface TooltipProps {
  active?: boolean;
  payload?: Array<{ payload: TimelineDataPoint }>;
}

const eventTypeColors: Record<string, string> = {
  initial: '#2196f3', // blue
  retracement: '#ff9800', // orange
  layer: '#4caf50', // green
  close: '#9e9e9e', // grey
  take_profit: '#8bc34a', // light green
  volatility_lock: '#ff5722', // deep orange
  margin_protection: '#f44336', // red
};

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
        <Chip
          label={data.event_type.replace('_', ' ').toUpperCase()}
          size="small"
          sx={{ mb: 0.5 }}
        />
        <Typography variant="body2">
          Layer: {data.layer_number}
        </Typography>
        <Typography variant="body2">
          Retracement: {data.retracement_count}
        </Typography>
        {data.direction && (
          <Typography variant="body2">
            Direction: {data.direction.toUpperCase()}
          </Typography>
        )}
        {data.price != null && (
          <Typography variant="body2">
            Price: {data.price.toFixed(5)}
          </Typography>
        )}
        {data.pnl != null && (
          <Typography
            variant="body2"
            color={data.pnl >= 0 ? 'success.main' : 'error.main'}
          >
            P&L: {formatCurrency(data.pnl)}
          </Typography>
        )}
      </Box>
    );
  }
  return null;
};

export const FloorStrategyTimeline: React.FC<FloorStrategyTimelineProps> = ({
  executionId,
  title = 'Floor Strategy Timeline',
  height = 400,
}) => {
  const theme = useTheme();
  const { events, isLoading, error } = useExecutionEvents(executionId);

  const timelineData: TimelineDataPoint[] = useMemo(() => {
    return events
      .filter((event) => event.layer_number != null && event.retracement_count != null)
      .map((event: BacktestStrategyEvent) => ({
        timestamp: event.timestamp || '',
        displayTime: event.timestamp
          ? new Date(event.timestamp).toLocaleTimeString()
          : '',
        layer_number: event.layer_number || 0,
        retracement_count: event.retracement_count || 0,
        event_type: event.event_type,
        price: event.price ? parseFloat(String(event.price)) : undefined,
        pnl: event.pnl ? parseFloat(String(event.pnl)) : undefined,
        direction: event.direction,
        size: event.event_type === 'take_profit' ? 100 : 50, // Larger dots for take profit
      }));
  }, [events]);

  if (error) {
    return (
      <Card>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            {title}
          </Typography>
          <Typography color="error">
            Failed to load timeline data: {error.message}
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

  if (timelineData.length === 0) {
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
            <Typography>No Floor strategy events available yet</Typography>
          </Box>
        </CardContent>
      </Card>
    );
  }

  // Group data by event type for legend
  const eventTypes = Array.from(new Set(timelineData.map((d) => d.event_type)));

  return (
    <Card>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          {title}
        </Typography>
        <Box sx={{ mb: 1, display: 'flex', flexWrap: 'wrap', gap: 1 }}>
          {eventTypes.map((type) => (
            <Chip
              key={type}
              label={type.replace('_', ' ')}
              size="small"
              sx={{
                bgcolor: eventTypeColors[type] || theme.palette.grey[500],
                color: 'white',
              }}
            />
          ))}
        </Box>
        <ResponsiveContainer width="100%" height={height}>
          <ScatterChart
            margin={{ top: 20, right: 30, left: 20, bottom: 20 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke={theme.palette.divider} />
            <XAxis
              dataKey="displayTime"
              name="Time"
              stroke={theme.palette.text.secondary}
              tick={{ fontSize: 12 }}
            />
            <YAxis
              dataKey="layer_number"
              name="Layer"
              stroke={theme.palette.text.secondary}
              tick={{ fontSize: 12 }}
              label={{
                value: 'Layer Number',
                angle: -90,
                position: 'insideLeft',
              }}
            />
            <ZAxis dataKey="size" range={[50, 200]} />
            <Tooltip content={<CustomTooltip />} />
            {eventTypes.map((type) => (
              <Scatter
                key={type}
                name={type.replace('_', ' ')}
                data={timelineData.filter((d) => d.event_type === type)}
                fill={eventTypeColors[type] || theme.palette.grey[500]}
              />
            ))}
          </ScatterChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
};
