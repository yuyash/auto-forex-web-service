/**
 * TaskTradesTable Component
 *
 * Displays task trades using task-based API endpoints.
 */

import React, { useState } from 'react';
import {
  Box,
  Chip,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  Typography,
  Alert,
} from '@mui/material';
import DataTable, { type Column } from '../../common/DataTable';
import { useTaskTrades, type TaskTrade } from '../../../hooks/useTaskTrades';
import { TaskType } from '../../../types/common';

interface TaskTradesTableProps {
  taskId: number;
  taskType: TaskType;
  enableRealTimeUpdates?: boolean;
}

export const TaskTradesTable: React.FC<TaskTradesTableProps> = ({
  taskId,
  taskType,
  enableRealTimeUpdates = false,
}) => {
  const [directionFilter, setDirectionFilter] = useState<'buy' | 'sell' | ''>(
    ''
  );

  const { trades, isLoading, error } = useTaskTrades({
    taskId,
    taskType,
    direction: directionFilter || undefined,
    enableRealTimeUpdates,
  });

  const formatTimestamp = (timestamp: string): string => {
    return new Date(timestamp).toLocaleString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  };

  const columns: Column<TaskTrade>[] = [
    {
      id: 'sequence',
      label: 'Seq',
      minWidth: 60,
    },
    {
      id: 'timestamp',
      label: 'Timestamp',
      minWidth: 180,
      format: (value) => formatTimestamp(value as string),
    },
    {
      id: 'instrument',
      label: 'Instrument',
      minWidth: 100,
    },
    {
      id: 'direction',
      label: 'Direction',
      minWidth: 80,
      format: (value) => (
        <Chip
          label={value as string}
          color={(value as string) === 'buy' ? 'success' : 'error'}
          size="small"
        />
      ),
    },
    {
      id: 'units',
      label: 'Units',
      minWidth: 100,
      align: 'right',
    },
    {
      id: 'price',
      label: 'Price',
      minWidth: 100,
      align: 'right',
    },
    {
      id: 'pnl',
      label: 'PnL',
      minWidth: 100,
      align: 'right',
      format: (value) =>
        value ? `$${parseFloat(value as string).toFixed(2)}` : '-',
    },
  ];

  if (error) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="error">{error.message}</Alert>
      </Box>
    );
  }

  return (
    <Box sx={{ p: 3 }}>
      <Box sx={{ mb: 2, display: 'flex', gap: 2, alignItems: 'center' }}>
        <Typography variant="h6">Task Trades</Typography>
        <FormControl size="small" sx={{ minWidth: 150 }}>
          <InputLabel>Direction Filter</InputLabel>
          <Select
            value={directionFilter}
            label="Direction Filter"
            onChange={(e) =>
              setDirectionFilter(e.target.value as 'buy' | 'sell' | '')
            }
          >
            <MenuItem value="">All Directions</MenuItem>
            <MenuItem value="buy">Buy</MenuItem>
            <MenuItem value="sell">Sell</MenuItem>
          </Select>
        </FormControl>
      </Box>

      <DataTable
        columns={columns}
        data={trades}
        loading={isLoading}
        emptyMessage="No trades available"
      />
    </Box>
  );
};

export default TaskTradesTable;
