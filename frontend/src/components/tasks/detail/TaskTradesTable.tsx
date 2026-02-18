/**
 * TaskTradesTable Component
 *
 * Displays task trades with server-side pagination.
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
  TablePagination,
} from '@mui/material';
import DataTable, { type Column } from '../../common/DataTable';
import { useTaskTrades, type TaskTrade } from '../../../hooks/useTaskTrades';
import { TaskType } from '../../../types/common';

interface TaskTradesTableProps {
  taskId: string | number;
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
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(100);

  const { trades, totalCount, isLoading, error } = useTaskTrades({
    taskId,
    taskType,
    direction: directionFilter || undefined,
    page: page + 1,
    pageSize: rowsPerPage,
    enableRealTimeUpdates,
  });

  const handleDirectionChange = (value: string) => {
    setDirectionFilter(value as 'buy' | 'sell' | '');
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

  const columns: Column<TaskTrade>[] = [
    {
      id: 'open_timestamp',
      label: 'Opened',
      width: 180,
      minWidth: 140,
      render: (row) =>
        row.open_timestamp ? formatTimestamp(row.open_timestamp) : '-',
    },
    {
      id: 'close_timestamp',
      label: 'Closed',
      width: 180,
      minWidth: 140,
      render: (row) =>
        row.close_timestamp ? formatTimestamp(row.close_timestamp) : '-',
    },
    {
      id: 'instrument',
      label: 'Instrument',
      width: 110,
      minWidth: 80,
    },
    {
      id: 'direction',
      label: 'Direction',
      width: 90,
      minWidth: 70,
      render: (row) => (
        <Chip
          label={row.direction as string}
          color={(row.direction as string) === 'buy' ? 'success' : 'error'}
          size="small"
        />
      ),
    },
    {
      id: 'units',
      label: 'Units',
      width: 90,
      minWidth: 70,
      align: 'right',
    },
    {
      id: 'open_price',
      label: 'Open Price',
      width: 110,
      minWidth: 80,
      align: 'right',
      render: (row: TaskTrade) =>
        row.open_price ? `¥${parseFloat(row.open_price).toFixed(3)}` : '-',
    },
    {
      id: 'close_price',
      label: 'Close Price',
      width: 110,
      minWidth: 80,
      align: 'right',
      render: (row: TaskTrade) =>
        row.close_price ? `¥${parseFloat(row.close_price).toFixed(3)}` : '-',
    },
    {
      id: 'pnl',
      label: 'PnL',
      width: 110,
      minWidth: 80,
      align: 'right',
      render: (row: TaskTrade) =>
        row.pnl ? `¥${parseFloat(row.pnl).toFixed(2)}` : '-',
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
            onChange={(e) => handleDirectionChange(e.target.value)}
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
        isLoading={isLoading}
        emptyMessage="No trades available"
        defaultRowsPerPage={rowsPerPage}
        rowsPerPageOptions={[rowsPerPage]}
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
      />
    </Box>
  );
};

export default TaskTradesTable;
