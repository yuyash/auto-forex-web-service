/**
 * TaskEventsTable Component
 *
 * Displays task events using task-based API endpoints.
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
import { useTaskEvents, type TaskEvent } from '../../../hooks/useTaskEvents';
import { TaskType } from '../../../types/common';

interface TaskEventsTableProps {
  taskId: number;
  taskType: TaskType;
  enableRealTimeUpdates?: boolean;
}

export const TaskEventsTable: React.FC<TaskEventsTableProps> = ({
  taskId,
  taskType,
  enableRealTimeUpdates = false,
}) => {
  const [severityFilter, setSeverityFilter] = useState<string>('');

  const { events, isLoading, error } = useTaskEvents({
    taskId,
    taskType,
    severity: severityFilter || undefined,
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

  const getSeverityColor = (
    severity: string
  ):
    | 'default'
    | 'primary'
    | 'secondary'
    | 'success'
    | 'error'
    | 'warning'
    | 'info' => {
    const lowerSeverity = severity.toLowerCase();
    switch (lowerSeverity) {
      case 'error':
      case 'critical':
        return 'error';
      case 'warning':
        return 'warning';
      case 'info':
        return 'info';
      default:
        return 'default';
    }
  };

  const columns: Column<TaskEvent>[] = [
    {
      id: 'created_at',
      label: 'Timestamp',
      minWidth: 180,
      format: (value) => formatTimestamp(value as string),
    },
    {
      id: 'event_type',
      label: 'Event Type',
      minWidth: 150,
    },
    {
      id: 'severity',
      label: 'Severity',
      minWidth: 100,
      format: (value) => (
        <Chip
          label={value as string}
          color={getSeverityColor(value as string)}
          size="small"
        />
      ),
    },
    {
      id: 'description',
      label: 'Description',
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
        <Typography variant="h6">Task Events</Typography>
        <FormControl size="small" sx={{ minWidth: 150 }}>
          <InputLabel>Severity Filter</InputLabel>
          <Select
            value={severityFilter}
            label="Severity Filter"
            onChange={(e) => setSeverityFilter(e.target.value)}
          >
            <MenuItem value="">All Severities</MenuItem>
            <MenuItem value="info">Info</MenuItem>
            <MenuItem value="warning">Warning</MenuItem>
            <MenuItem value="error">Error</MenuItem>
            <MenuItem value="critical">Critical</MenuItem>
          </Select>
        </FormControl>
      </Box>

      <DataTable
        columns={columns}
        data={events}
        loading={isLoading}
        emptyMessage="No events available"
      />
    </Box>
  );
};

export default TaskEventsTable;
