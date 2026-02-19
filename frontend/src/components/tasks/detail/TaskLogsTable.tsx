/**
 * TaskLogsTable Component
 *
 * Displays task logs with server-side pagination.
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  Box,
  Chip,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  Typography,
  Alert,
  TablePagination,
} from '@mui/material';
import DataTable, { type Column } from '../../common/DataTable';
import { useTaskLogs, type TaskLog } from '../../../hooks/useTaskLogs';
import { TaskType } from '../../../types/common';

interface TaskLogsTableProps {
  taskId: string;
  taskType: TaskType;
  executionId?: string;
  enableRealTimeUpdates?: boolean;
}

export const TaskLogsTable: React.FC<TaskLogsTableProps> = ({
  taskId,
  taskType,
  executionId,
  enableRealTimeUpdates = false,
}) => {
  const [levelFilter, setLevelFilter] = useState<string>('');
  const [page, setPage] = useState(0); // 0-indexed for MUI TablePagination
  const [rowsPerPage, setRowsPerPage] = useState(100);

  const { logs, totalCount, isLoading, error } = useTaskLogs({
    taskId,
    taskType,
    level: levelFilter || undefined,
    page: page + 1, // DRF uses 1-indexed pages
    pageSize: rowsPerPage,
    enableRealTimeUpdates,
  });

  const handleLevelFilterChange = (value: string) => {
    setLevelFilter(value);
    setPage(0);
  };

  // Reset page when executionId changes
  const [prevExecutionId, setPrevExecutionId] = useState(executionId);
  if (prevExecutionId !== executionId) {
    setPrevExecutionId(executionId);
    if (page !== 0) setPage(0);
  }

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
      width: 260,
      minWidth: 200,
      render: (row) => formatTimestamp(row.timestamp as string),
    },
    {
      id: 'level',
      label: 'Level',
      width: 120,
      minWidth: 90,
      render: (row) => (
        <Chip
          label={row.level as string}
          color={getLevelColor(row.level as string)}
          size="small"
        />
      ),
    },
    {
      id: 'component',
      label: 'Component',
      width: 220,
      minWidth: 150,
    },
    {
      id: 'message',
      label: 'Message',
      minWidth: 200,
    },
  ];

  // Measure available height so the table fills the viewport
  const rootRef = useRef<HTMLDivElement | null>(null);
  const [tableMaxHeight, setTableMaxHeight] = useState<string>(
    'calc(100vh - 640px)'
  );

  const measure = useCallback(() => {
    const el = rootRef.current;
    if (!el) return;
    const top = el.getBoundingClientRect().top;
    // title/filter bar (44) + DataTable internal pagination (52)
    // + external TablePagination (52) + padding/margin (24)
    const reserved = 44 + 52 + 52 + 24 + 68;
    const available = window.innerHeight - top - reserved;
    setTableMaxHeight(`${Math.max(200, Math.round(available))}px`);
  }, []);

  useEffect(() => {
    let raf: number;
    raf = requestAnimationFrame(() => {
      raf = requestAnimationFrame(measure);
    });
    window.addEventListener('resize', measure);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener('resize', measure);
    };
  }, [measure]);

  if (error) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="error">{error.message}</Alert>
      </Box>
    );
  }

  return (
    <Box
      ref={rootRef}
      sx={{
        px: 3,
        pt: 1,
        pb: 0,
        display: 'flex',
        flexDirection: 'column',
        flex: 1,
        minHeight: 0,
        overflow: 'hidden',
      }}
    >
      <Box
        sx={{
          mb: 1,
          display: 'flex',
          gap: 2,
          alignItems: 'center',
          flexShrink: 0,
        }}
      >
        <Typography variant="h6">Task Logs</Typography>
        <FormControl size="small" sx={{ minWidth: 150 }}>
          <InputLabel>Level Filter</InputLabel>
          <Select
            value={levelFilter}
            label="Level Filter"
            onChange={(e) => handleLevelFilterChange(e.target.value)}
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
        isLoading={isLoading}
        emptyMessage="No logs available"
        defaultRowsPerPage={rowsPerPage}
        rowsPerPageOptions={[rowsPerPage]}
        storageKey="task-logs"
        tableMaxHeight={tableMaxHeight}
      />

      <TablePagination
        component="div"
        count={totalCount}
        page={page}
        onPageChange={(_e, newPage) => setPage(newPage)}
        rowsPerPage={rowsPerPage}
        onRowsPerPageChange={(e) => {
          setRowsPerPage(parseInt(e.target.value, 10));
          setPage(0);
        }}
        rowsPerPageOptions={[50, 100, 200, 500]}
        sx={{ flexShrink: 0 }}
      />
    </Box>
  );
};

export default TaskLogsTable;
