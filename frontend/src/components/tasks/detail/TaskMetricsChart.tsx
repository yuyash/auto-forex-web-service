/**
 * TaskMetricsChart Component
 *
 * Displays task metrics using task-based API endpoints.
 * Replaces execution-based MetricsChart.
 */

import React from 'react';
import { Box, Typography, Alert, CircularProgress } from '@mui/material';
import {
  MetricsLineChart,
  type MetricSeries,
} from '../../charts/MetricsLineChart';
import { useTaskMetrics } from '../../../hooks/useTaskMetrics';
import { TaskType } from '../../../types/common';

interface TaskMetricsChartProps {
  taskId: number;
  taskType: TaskType;
  enableRealTimeUpdates?: boolean;
}

export const TaskMetricsChart: React.FC<TaskMetricsChartProps> = ({
  taskId,
  taskType,
  enableRealTimeUpdates = false,
}) => {
  const { metrics, isLoading, error } = useTaskMetrics({
    taskId,
    taskType,
    enableRealTimeUpdates,
  });

  if (isLoading) {
    return (
      <Box
        sx={{
          p: 3,
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          minHeight: 400,
        }}
      >
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="error">{error.message}</Alert>
      </Box>
    );
  }

  if (metrics.length === 0) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="info">No metrics data available yet.</Alert>
      </Box>
    );
  }

  // Group metrics by metric_name to create series
  const metricsByName = metrics.reduce(
    (acc, metric) => {
      if (!acc[metric.metric_name]) {
        acc[metric.metric_name] = [];
      }
      acc[metric.metric_name].push({
        timestamp: metric.timestamp,
        value: metric.value,
      });
      return acc;
    },
    {} as Record<string, Array<{ timestamp: string; value: number }>>
  );

  // Convert to MetricSeries format
  const series: MetricSeries[] = Object.entries(metricsByName).map(
    ([name, data]) => ({
      id: name,
      label: name,
      data: data,
    })
  );

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h6" gutterBottom>
        Task Metrics
      </Typography>

      <MetricsLineChart series={series} height={400} />

      <Box sx={{ mt: 2 }}>
        <Typography variant="body2" color="text.secondary">
          Total data points: {metrics.length}
        </Typography>
      </Box>
    </Box>
  );
};

export default TaskMetricsChart;
