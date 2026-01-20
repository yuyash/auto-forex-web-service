/**
 * LogsTable Component
 *
 * Displays execution logs in table format with filtering by log level.
 * Fetches from GET /executions/<execution_id>/logs/ using generated client.
 *
 * Requirements: 11.7
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Chip,
  Typography,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  type SelectChangeEvent,
} from '@mui/material';
import DataTable, { type Column } from '../../common/DataTable';
import { ExecutionsService } from '../../../api/generated/services/ExecutionsService';
import { useToast } from '../../common';

type LogLevel = 'debug' | 'info' | 'warning' | 'error';

interface ExecutionLog {
  timestamp: string;
  level: LogLevel;
  message: string;
  context?: Record<string, unknown>;
}

interface LogsTableProps {
  executionId: number;
  enableRealTimeUpdates?: boolean;
}

/**
 * LogsTable Component
 *
 * Displays execution logs with filtering by log level.
 *
 * @param executionId - The execution ID to fetch logs for
 * @param enableRealTimeUpdates - Enable automatic refresh every 5 seconds
 */
export const LogsTable: React.FC<LogsTableProps> = ({
  executionId,
  enableRealTimeUpdates = false,
}) => {
  const [logs, setLogs] = useState<ExecutionLog[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [levelFilter, setLevelFilter] = useState<LogLevel | ''>('');
  const { showError } = useToast();

  const fetchLogs = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);
      const response = await ExecutionsService.getExecutionLogs(
        executionId,
        undefined, // endTime
        levelFilter || undefined, // level
        1000 // limit - get last 1000 logs
      );
      setLogs(response.logs || []);
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : 'Failed to load logs';
      setError(new Error(errorMessage));
      showError(errorMessage);
    } finally {
      setIsLoading(false);
    }
  }, [executionId, levelFilter, showError]);

  useEffect(() => {
    fetchLogs();
  }, [executionId, levelFilter, fetchLogs]);

  const handleLevelFilterChange = (event: SelectChangeEvent<string>) => {
    setLevelFilter(event.target.value as LogLevel | '');
  };

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

  const getLogLevelColor = (
    level: LogLevel
  ):
    | 'default'
    | 'primary'
    | 'secondary'
    | 'success'
    | 'error'
    | 'warning'
    | 'info' => {
    switch (level) {
      case 'error':
        return 'error';
      case 'warning':
        return 'warning';
      case 'info':
        return 'info';
      case 'debug':
        return 'default';
      default:
        return 'default';
    }
  };

  const columns: Column<ExecutionLog>[] = [
    {
      id: 'timestamp',
      label: 'Timestamp',
      sortable: true,
      minWidth: 220,
      render: (row) => (
        <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
          {formatTimestamp(row.timestamp)}
        </Typography>
      ),
    },
    {
      id: 'level',
      label: 'Level',
      sortable: true,
      minWidth: 100,
      render: (row) => (
        <Chip
          label={row.level.toUpperCase()}
          size="small"
          color={getLogLevelColor(row.level)}
        />
      ),
    },
    {
      id: 'message',
      label: 'Message',
      filterable: true,
      minWidth: 400,
      render: (row) => (
        <Typography
          variant="body2"
          sx={{
            fontFamily: 'monospace',
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
          }}
        >
          {row.message}
        </Typography>
      ),
    },
    {
      id: 'context',
      label: 'Context',
      minWidth: 200,
      render: (row) =>
        row.context && Object.keys(row.context).length > 0 ? (
          <Box>
            {Object.entries(row.context).map(([key, value]) => (
              <Typography
                key={key}
                variant="caption"
                component="div"
                sx={{ color: 'text.secondary', fontFamily: 'monospace' }}
              >
                <strong>{key}:</strong> {String(value)}
              </Typography>
            ))}
          </Box>
        ) : (
          <Typography variant="caption" color="text.secondary">
            -
          </Typography>
        ),
    },
  ];

  return (
    <Box>
      {/* Filter Controls */}
      <Box sx={{ mb: 2, display: 'flex', gap: 2 }}>
        <FormControl size="small" sx={{ minWidth: 150 }}>
          <InputLabel>Log Level</InputLabel>
          <Select
            value={levelFilter}
            onChange={handleLevelFilterChange}
            label="Log Level"
          >
            <MenuItem value="">All Levels</MenuItem>
            <MenuItem value="debug">Debug</MenuItem>
            <MenuItem value="info">Info</MenuItem>
            <MenuItem value="warning">Warning</MenuItem>
            <MenuItem value="error">Error</MenuItem>
          </Select>
        </FormControl>
      </Box>

      {/* Logs Table */}
      <DataTable
        columns={columns}
        data={logs}
        isLoading={isLoading}
        error={error}
        emptyMessage="No logs found"
        enableRealTimeUpdates={enableRealTimeUpdates}
        onRefresh={fetchLogs}
        ariaLabel="Execution logs table"
        defaultRowsPerPage={50}
        rowsPerPageOptions={[25, 50, 100, 200]}
      />
    </Box>
  );
};

export default LogsTable;
