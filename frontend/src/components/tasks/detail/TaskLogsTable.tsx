/**
 * TaskLogsTable Component
 *
 * Displays task logs using task-based API endpoints.
 * Replaces execution-based LogsTable.
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
import { useTaskLogs, type TaskLog } from '../../../hooks/useTaskLogs';
import { TaskType } from '../../../types/common';

interface TaskLogsTableProps {
  taskId: number;
  taskType: TaskType;
  enableRealTimeUpdates?: boolean;
}

export const TaskLogsTable: React.FC<TaskLogsTableProps> = ({
  taskId,
  taskType,
  enableRealTimeUpdates = false,
}) => {
  const [levelFilter, setLevelFilter] = useState<string>('');

  const { logs, isLoading, error } = useTaskLogs({
    taskId,
    taskType,
    level: levelFilter || undefined,
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
      fractionalSecondDigits: 3,
    });
  };

  const getLevelColor = (
    level: string
  ):
    | 'default'
    | 'primary'
    | 'secondary'
    | 'success'
    | 'error'
    | 'warning'
    | 'info' => {
    const upperLevel = level.toUpperCase();
    switch (upperLevel) {
      case 'ERROR':
      case 'CRITICAL':
        return 'error';
      case 'WARNING':
        return 'warning';
      case 'INFO':
        return 'info';
      case 'DEBUG':
        return 'default';
      default:
        return 'default';
    }
  };

  const columns: Column<TaskLog>[] = [
    {
      id: 'timestamp',
      label: 'Timestamp',
      minWidth: 200,
      format: (value) => formatTimestamp(value as string),
    },
    {
      id: 'level',
      label: 'Level',
      minWidth: 100,
      format: (value) => (
        <Chip
          label={value as string}
          color={getLevelColor(value as string)}
          size="small"
        />
      ),
    },
    {
      id: 'message',
      label: 'Message',
      minWidth: 400,
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
        <Typography variant="h6">Task Logs</Typography>
        <FormControl size="small" sx={{ minWidth: 150 }}>
          <InputLabel>Level Filter</InputLabel>
          <Select
            value={levelFilter}
            label="Level Filter"
            onChange={(e) => setLevelFilter(e.target.value)}
          >
            <MenuItem value="">All Levels</MenuItem>
            <MenuItem value="DEBUG">Debug</MenuItem>
            <MenuItem value="INFO">Info</MenuItem>
            <MenuItem value="WARNING">Warning</MenuItem>
            <MenuItem value="ERROR">Error</MenuItem>
            <MenuItem value="CRITICAL">Critical</MenuItem>
          </Select>
        </FormControl>
      </Box>

      <DataTable
        columns={columns}
        data={logs}
        loading={isLoading}
        emptyMessage="No logs available"
      />
    </Box>
  );
};

export default TaskLogsTable;
