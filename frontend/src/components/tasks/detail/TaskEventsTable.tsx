/**
 * TaskEventsTable Component
 *
 * Displays task events with server-side pagination.
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
import { useTaskEvents, type TaskEvent } from '../../../hooks/useTaskEvents';
import { TaskType } from '../../../types/common';

interface TaskEventsTableProps {
  taskId: string | number;
  taskType: TaskType;
  enableRealTimeUpdates?: boolean;
}

export const TaskEventsTable: React.FC<TaskEventsTableProps> = ({
  taskId,
  taskType,
  enableRealTimeUpdates = false,
}) => {
  const [severityFilter, setSeverityFilter] = useState<string>('');
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(100);

  const { events, totalCount, isLoading, error } = useTaskEvents({
    taskId,
    taskType,
    severity: severityFilter || undefined,
    page: page + 1,
    pageSize: rowsPerPage,
    enableRealTimeUpdates,
  });

  const handleSeverityChange = (value: string) => {
    setSeverityFilter(value);
    setPage(0);
  };

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
      width: 240,
      minWidth: 200,
      render: (row) => formatTimestamp(row.created_at as string),
    },
    {
      id: 'event_type',
      label: 'Event Type',
      width: 140,
      minWidth: 100,
      render: (row) => row.event_type_display ?? row.event_type,
    },
    {
      id: 'severity',
      label: 'Severity',
      width: 100,
      minWidth: 80,
      render: (row) => (
        <Chip
          label={row.severity as string}
          color={getSeverityColor(row.severity as string)}
          size="small"
        />
      ),
    },
    {
      id: 'description',
      label: 'Description',
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
    // Double rAF to wait for layout to settle
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
        <Typography variant="h6">Task Events</Typography>
        <FormControl size="small" sx={{ minWidth: 150 }}>
          <InputLabel>Severity Filter</InputLabel>
          <Select
            value={severityFilter}
            label="Severity Filter"
            onChange={(e) => handleSeverityChange(e.target.value)}
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
        isLoading={isLoading}
        emptyMessage="No events available"
        defaultRowsPerPage={rowsPerPage}
        rowsPerPageOptions={[rowsPerPage]}
        storageKey="task-events"
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

export default TaskEventsTable;
