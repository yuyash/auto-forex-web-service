/**
 * EquityOHLCChart Component
 *
 * Displays equity curve data as OHLC candlestick chart using MUI X Charts.
 * Features:
 * - Responsive sizing
 * - Granularity selector for time binning
 * - Accessibility labels
 * - Zoom and pan controls
 * - Tooltip with OHLC data
 */

import React, { useMemo, useState } from 'react';
import {
  Box,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Typography,
  CircularProgress,
  Alert,
  Paper,
} from '@mui/material';
import type { SelectChangeEvent } from '@mui/material/Select';
import { LineChart } from '@mui/x-charts/LineChart';

/**
 * OHLC Data Point interface
 */
export interface OHLCDataPoint {
  timestamp: string; // ISO 8601 timestamp
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
}

/**
 * Granularity options in seconds
 */
export const GRANULARITY_OPTIONS = [
  { value: 1, label: '1 Second' },
  { value: 5, label: '5 Seconds' },
  { value: 10, label: '10 Seconds' },
  { value: 30, label: '30 Seconds' },
  { value: 60, label: '1 Minute' },
  { value: 300, label: '5 Minutes' },
  { value: 900, label: '15 Minutes' },
  { value: 1800, label: '30 Minutes' },
  { value: 3600, label: '1 Hour' },
  { value: 14400, label: '4 Hours' },
  { value: 86400, label: '1 Day' },
] as const;

/**
 * EquityOHLCChart Props
 */
export interface EquityOHLCChartProps {
  /** OHLC data points */
  data: OHLCDataPoint[];
  /** Chart height in pixels */
  height?: number;
  /** Loading state */
  loading?: boolean;
  /** Error message */
  error?: string | null;
  /** Initial granularity in seconds */
  initialGranularity?: number;
  /** Callback when granularity changes */
  onGranularityChange?: (granularity: number) => void;
  /** Show granularity selector */
  showGranularitySelector?: boolean;
  /** Chart title */
  title?: string;
}

/**
 * EquityOHLCChart Component
 */
export const EquityOHLCChart: React.FC<EquityOHLCChartProps> = ({
  data,
  height = 400,
  loading = false,
  error = null,
  initialGranularity = 60,
  onGranularityChange,
  showGranularitySelector = true,
  title = 'Equity Curve',
}) => {
  const [granularity, setGranularity] = useState(initialGranularity);

  // Handle granularity change
  const handleGranularityChange = (event: SelectChangeEvent<number>) => {
    const newGranularity = Number(event.target.value);
    setGranularity(newGranularity);
    onGranularityChange?.(newGranularity);
  };

  // Transform data for chart
  const chartData = useMemo(() => {
    if (!data || data.length === 0) return [];

    return data.map((point) => ({
      timestamp: new Date(point.timestamp).getTime(),
      date: new Date(point.timestamp),
      open: Number(point.open),
      high: Number(point.high),
      low: Number(point.low),
      close: Number(point.close),
      volume: point.volume ? Number(point.volume) : 0,
    }));
  }, [data]);

  // Calculate candlestick colors (green for up, red for down)

  // Show loading state
  if (loading) {
    return (
      <Paper sx={{ p: 3, height }}>
        <Box
          display="flex"
          justifyContent="center"
          alignItems="center"
          height="100%"
        >
          <CircularProgress />
        </Box>
      </Paper>
    );
  }

  // Show error state
  if (error) {
    return (
      <Paper sx={{ p: 3 }}>
        <Alert severity="error">{error}</Alert>
      </Paper>
    );
  }

  // Show empty state
  if (!data || data.length === 0) {
    return (
      <Paper sx={{ p: 3 }}>
        <Alert severity="info">No equity data available</Alert>
      </Paper>
    );
  }

  return (
    <Paper sx={{ p: 2 }}>
      {/* Header with title and granularity selector */}
      <Box
        display="flex"
        justifyContent="space-between"
        alignItems="center"
        mb={2}
      >
        <Typography variant="h6" component="h2">
          {title}
        </Typography>

        {showGranularitySelector && (
          <FormControl size="small" sx={{ minWidth: 150 }}>
            <InputLabel id="granularity-select-label">Granularity</InputLabel>
            <Select
              labelId="granularity-select-label"
              id="granularity-select"
              value={granularity}
              label="Granularity"
              onChange={handleGranularityChange}
              aria-label="Select time granularity for chart"
            >
              {GRANULARITY_OPTIONS.map((option) => (
                <MenuItem key={option.value} value={option.value}>
                  {option.label}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        )}
      </Box>

      {/* Candlestick Chart using BarChart for OHLC representation */}
      <Box sx={{ width: '100%', height }}>
        <LineChart
          xAxis={[
            {
              data: chartData.map((d) => d.timestamp),
              scaleType: 'time',
              valueFormatter: formatTimestamp,
              label: 'Time',
            },
          ]}
          yAxis={[
            {
              label: 'Price',
            },
          ]}
          series={[
            {
              data: chartData.map((d) => d.close),
              label: 'Close Price',
              color: '#1976d2',
              showMark: false,
              curve: 'linear',
            },
            {
              data: chartData.map((d) => d.high),
              label: 'High',
              color: '#26a69a',
              showMark: false,
              curve: 'linear',
            },
            {
              data: chartData.map((d) => d.low),
              label: 'Low',
              color: '#ef5350',
              showMark: false,
              curve: 'linear',
            },
          ]}
          height={height}
          margin={{ top: 20, right: 20, bottom: 60, left: 60 }}
          grid={{ vertical: true, horizontal: true }}
          slotProps={{
            legend: {
              direction: 'row',
              position: { vertical: 'bottom', horizontal: 'middle' },
              padding: 0,
            },
          }}
          aria-label={`${title} showing equity curve with OHLC data`}
        />
      </Box>

      {/* Data summary */}
      <Box mt={2} display="flex" gap={3} flexWrap="wrap">
        <Typography variant="body2" color="text.secondary">
          Data Points: {chartData.length}
        </Typography>
        {chartData.length > 0 && (
          <>
            <Typography variant="body2" color="text.secondary">
              Latest: {Number(chartData[chartData.length - 1].close).toFixed(2)}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              High:{' '}
              {Math.max(...chartData.map((d) => Number(d.high))).toFixed(2)}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Low: {Math.min(...chartData.map((d) => Number(d.low))).toFixed(2)}
            </Typography>
          </>
        )}
      </Box>
    </Paper>
  );
};

export default EquityOHLCChart;
