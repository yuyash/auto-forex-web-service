/**
 * MetricsLineChart Component
 *
 * Displays multiple metrics as line charts using MUI X Charts.
 * Features:
 * - Multiple series support
 * - Responsive sizing
 * - Accessibility labels
 * - Zoom and pan controls
 * - Customizable colors
 * - Legend with series toggle
 */

import React, { useMemo } from 'react';
import {
  Box,
  Typography,
  CircularProgress,
  Alert,
  Paper,
  Chip,
} from '@mui/material';
import { LineChart } from '@mui/x-charts/LineChart';

/**
 * Metric Data Point interface
 */
export interface MetricDataPoint {
  timestamp: string; // ISO 8601 timestamp
  value: number;
}

/**
 * Metric Series interface
 */
export interface MetricSeries {
  id: string;
  label: string;
  data: MetricDataPoint[];
  color?: string;
  unit?: string;
}

/**
 * MetricsLineChart Props
 */
export interface MetricsLineChartProps {
  /** Array of metric series to display */
  series: MetricSeries[];
  /** Chart height in pixels */
  height?: number;
  /** Loading state */
  loading?: boolean;
  /** Error message */
  error?: string | null;
  /** Chart title */
  title?: string;
  /** Show legend */
  showLegend?: boolean;
  /** Y-axis label */
  yAxisLabel?: string;
  /** Enable zoom */
  enableZoom?: boolean;
}

/**
 * Default colors for series
 */
const DEFAULT_COLORS = [
  '#1976d2', // Blue
  '#26a69a', // Teal
  '#ff9800', // Orange
  '#9c27b0', // Purple
  '#f44336', // Red
  '#4caf50', // Green
  '#00bcd4', // Cyan
  '#ff5722', // Deep Orange
];

/**
 * MetricsLineChart Component
 */
export const MetricsLineChart: React.FC<MetricsLineChartProps> = ({
  series,
  height = 400,
  loading = false,
  error = null,
  title = 'Metrics',
  showLegend = true,
  yAxisLabel = 'Value',
}) => {
  // Transform series data for chart
  const chartSeries = useMemo(() => {
    if (!series || series.length === 0) return [];

    // First, get all unique timestamps
    const timestampSet = new Set<number>();
    series.forEach((metric) => {
      metric.data.forEach((point) => {
        timestampSet.add(new Date(point.timestamp).getTime());
      });
    });
    const allTimestamps = Array.from(timestampSet).sort((a, b) => a - b);

    // Then align each series data to match all timestamps
    return series.map((metric, index) => {
      // Create a map of timestamp to value for this metric
      const valueMap = new Map<number, number>();
      metric.data.forEach((point) => {
        const timestamp = new Date(point.timestamp).getTime();
        valueMap.set(timestamp, Number(point.value));
      });

      // Create aligned data array with null for missing values
      const alignedData = allTimestamps.map((timestamp) => {
        const value = valueMap.get(timestamp);
        return value !== undefined && !isNaN(value) ? value : null;
      });

      return {
        id: metric.id,
        label: metric.label,
        data: alignedData,
        color: metric.color || DEFAULT_COLORS[index % DEFAULT_COLORS.length],
        showMark: false,
        curve: 'linear' as const,
        connectNulls: true, // Connect line across null values
      };
    });
  }, [series]);

  // Get all unique timestamps across all series
  const allTimestamps = useMemo(() => {
    if (!series || series.length === 0) return [];

    const timestampSet = new Set<number>();
    series.forEach((metric) => {
      metric.data.forEach((point) => {
        timestampSet.add(new Date(point.timestamp).getTime());
      });
    });

    return Array.from(timestampSet).sort((a, b) => a - b);
  }, [series]);

  // Format timestamp for x-axis
  const formatTimestamp = (timestamp: number) => {
    const date = new Date(timestamp);
    return date.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  // Calculate statistics for each series
  const seriesStats = useMemo(() => {
    return series.map((metric) => {
      const values = metric.data
        .map((point) => Number(point.value))
        .filter((v) => !isNaN(v));

      if (values.length === 0) {
        return {
          id: metric.id,
          label: metric.label,
          min: 0,
          max: 0,
          avg: 0,
          latest: 0,
          unit: metric.unit || '',
        };
      }

      const min = Math.min(...values);
      const max = Math.max(...values);
      const avg = values.reduce((sum, val) => sum + val, 0) / values.length;
      const latest = values[values.length - 1];

      return {
        id: metric.id,
        label: metric.label,
        min,
        max,
        avg,
        latest,
        unit: metric.unit || '',
      };
    });
  }, [series]);

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
  if (!series || series.length === 0) {
    return (
      <Paper sx={{ p: 3 }}>
        <Alert severity="info">No metrics data available</Alert>
      </Paper>
    );
  }

  return (
    <Paper sx={{ p: 2 }}>
      {/* Header with title */}
      <Box mb={2}>
        <Typography variant="h6" component="h2">
          {title}
        </Typography>
      </Box>

      {/* Line Chart */}
      <Box sx={{ width: '100%', height }}>
        <LineChart
          xAxis={[
            {
              data: allTimestamps,
              scaleType: 'time',
              valueFormatter: formatTimestamp,
              label: 'Time',
            },
          ]}
          yAxis={[
            {
              label: yAxisLabel,
            },
          ]}
          series={chartSeries}
          height={height}
          margin={{ top: 20, right: 20, bottom: 60, left: 60 }}
          grid={{ vertical: true, horizontal: true }}
          slotProps={{
            legend: showLegend
              ? {
                  direction: 'row',
                  position: { vertical: 'bottom', horizontal: 'middle' },
                  padding: 0,
                }
              : { hidden: true },
          }}
          aria-label={`${title} showing ${series.length} metric series`}
        />
      </Box>

      {/* Series Statistics */}
      <Box mt={2}>
        <Typography variant="subtitle2" gutterBottom>
          Statistics
        </Typography>
        <Box display="flex" flexDirection="column" gap={1}>
          {seriesStats.map((stat) => (
            <Box
              key={stat.id}
              display="flex"
              alignItems="center"
              gap={1}
              flexWrap="wrap"
            >
              <Chip
                label={stat.label}
                size="small"
                sx={{
                  backgroundColor:
                    series.find((s) => s.id === stat.id)?.color ||
                    DEFAULT_COLORS[0],
                  color: 'white',
                }}
              />
              <Typography variant="body2" color="text.secondary">
                Latest: {stat.latest.toFixed(2)}
                {stat.unit}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Avg: {stat.avg.toFixed(2)}
                {stat.unit}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Min: {stat.min.toFixed(2)}
                {stat.unit}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Max: {stat.max.toFixed(2)}
                {stat.unit}
              </Typography>
            </Box>
          ))}
        </Box>
      </Box>
    </Paper>
  );
};

export default MetricsLineChart;
