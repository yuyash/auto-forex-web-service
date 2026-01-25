/**
 * TaskEquityChart Component
 *
 * Displays task equity chart using task-based API endpoints.
 */

import React from 'react';
import { Box, Alert, CircularProgress, Typography } from '@mui/material';
import { LineChart } from '@mui/x-charts/LineChart';
import { useTaskEquity } from '../../../hooks/useTaskEquity';
import { TaskType } from '../../../types/common';

interface TaskEquityChartProps {
  taskId: number;
  taskType: TaskType;
  enableRealTimeUpdates?: boolean;
}

export const TaskEquityChart: React.FC<TaskEquityChartProps> = ({
  taskId,
  taskType,
  enableRealTimeUpdates = false,
}) => {
  const { equityPoints, isLoading, error } = useTaskEquity({
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

  if (equityPoints.length === 0) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="info">No equity data available yet.</Alert>
      </Box>
    );
  }

  // Transform data for chart
  const timestamps = equityPoints.map((point) =>
    new Date(point.timestamp).getTime()
  );
  const balanceData = equityPoints.map((point) => parseFloat(point.balance));
  const equityData = equityPoints.map((point) => parseFloat(point.equity));

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h6" gutterBottom>
        Task Equity Curve
      </Typography>

      <LineChart
        xAxis={[
          {
            data: timestamps,
            scaleType: 'time',
            valueFormatter: (value) =>
              new Date(value).toLocaleTimeString('en-US', {
                hour: '2-digit',
                minute: '2-digit',
              }),
          },
        ]}
        series={[
          {
            data: balanceData,
            label: 'Balance',
            color: '#8884d8',
          },
          {
            data: equityData,
            label: 'Equity',
            color: '#82ca9d',
          },
        ]}
        height={400}
      />

      <Box sx={{ mt: 2 }}>
        <Typography variant="body2" color="text.secondary">
          Total data points: {equityPoints.length}
        </Typography>
      </Box>
    </Box>
  );
};

export default TaskEquityChart;
