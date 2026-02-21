/**
 * TaskTradesTable Component
 *
 * Displays all trades for a task in a single table.
 * Trades are append-only event records; position open/close status
 * is tracked in the positions table.
 */

import React, { useState } from 'react';
import { Box, Chip, Typography, Alert, TablePagination } from '@mui/material';
import DataTable, { type Column } from '../../common/DataTable';
import { useTaskTrades, type TaskTrade } from '../../../hooks/useTaskTrades';
import { TaskType } from '../../../types/common';

interface TaskTradesTableProps {
  taskId: string | number;
  taskType: TaskType;
  enableRealTimeUpdates?: boolean;
  pipSize?: number | null;
}

export const TaskTradesTable: React.FC<TaskTradesTableProps> = ({
  taskId,
  taskType,
  enableRealTimeUpdates = false,
}) => {
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(50);

  const { trades, totalCount, isLoading, error } = useTaskTrades({
    taskId,
    taskType,
    page: page + 1,
    pageSize: rowsPerPage,
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
      id: 'timestamp',
      label: 'Timestamp',
      width: 180,
      minWidth: 140,
      render: (row) => (row.timestamp ? formatTimestamp(row.timestamp) : '-'),
    },
    {
      id: 'instrument',
      label: 'Instrument',
      width: 110,
      minWidth: 80,
    },
    {
      id: 'execution_method',
      label: 'Type',
      width: 140,
      minWidth: 100,
      render: (row) => {
        const method =
          row.execution_method_display || row.execution_method || '-';
        return <Typography variant="body2">{method}</Typography>;
      },
    },
    {
      id: 'direction',
      label: 'Direction',
      width: 90,
      minWidth: 70,
      render: (row) => {
        const dir = String(row.direction).toLowerCase();
        return (
          <Chip
            label={
              dir === 'long'
                ? 'LONG'
                : dir === 'short'
                  ? 'SHORT'
                  : (row.direction as string)
            }
            color={dir === 'long' ? 'success' : 'error'}
            size="small"
          />
        );
      },
    },
    {
      id: 'units',
      label: 'Units',
      width: 90,
      minWidth: 70,
      align: 'right',
    },
    {
      id: 'price',
      label: 'Price',
      width: 110,
      minWidth: 80,
      align: 'right',
      render: (row: TaskTrade) =>
        row.price ? parseFloat(row.price).toFixed(5) : '-',
    },
    {
      id: 'layer_index',
      label: 'Layer',
      width: 70,
      minWidth: 50,
      align: 'right',
      render: (row: TaskTrade) =>
        row.layer_index != null ? String(row.layer_index) : '-',
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
      <Box
        sx={{
          mb: 2,
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}
      >
        <Typography variant="h6">Trades ({totalCount})</Typography>
      </Box>

      <DataTable
        columns={columns}
        data={trades}
        isLoading={isLoading}
        emptyMessage="No trades recorded"
        defaultRowsPerPage={rowsPerPage}
        rowsPerPageOptions={[rowsPerPage]}
        tableMaxHeight="none"
        hidePagination
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
        rowsPerPageOptions={[10, 50, 100, 200, 500]}
      />
    </Box>
  );
};

export default TaskTradesTable;
