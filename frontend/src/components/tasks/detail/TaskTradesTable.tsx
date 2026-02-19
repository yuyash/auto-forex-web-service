/**
 * TaskTradesTable Component
 *
 * Displays closed positions and open positions in separate tables
 * with total Realized PnL and Unrealized PnL summaries.
 */

import React, { useState, useMemo } from 'react';
import { Box, Chip, Typography, Alert, TablePagination } from '@mui/material';
import DataTable, { type Column } from '../../common/DataTable';
import { useTaskTrades, type TaskTrade } from '../../../hooks/useTaskTrades';
import { TaskType } from '../../../types/common';

interface TaskTradesTableProps {
  taskId: string | number;
  taskType: TaskType;
  enableRealTimeUpdates?: boolean;
  currentPrice?: number | null;
  pipSize?: number | null;
}

export const TaskTradesTable: React.FC<TaskTradesTableProps> = ({
  taskId,
  taskType,
  enableRealTimeUpdates = false,
  currentPrice,
  pipSize,
}) => {
  const [page, setPage] = useState(0);
  const [openPage, setOpenPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(10);
  const [openRowsPerPage, setOpenRowsPerPage] = useState(10);

  const {
    trades: closedTrades,
    totalCount: closedTotalCount,
    isLoading: closedLoading,
    error: closedError,
  } = useTaskTrades({
    taskId,
    taskType,
    status: 'closed',
    page: page + 1,
    pageSize: rowsPerPage,
    enableRealTimeUpdates,
  });

  const {
    trades: openTrades,
    totalCount: openTotalCount,
    isLoading: openLoading,
    error: openError,
  } = useTaskTrades({
    taskId,
    taskType,
    status: 'open',
    page: openPage + 1,
    pageSize: openRowsPerPage,
    enableRealTimeUpdates,
  });

  const isLoading = closedLoading || openLoading;
  const error = closedError || openError;

  const totalRealizedPnl = useMemo(
    () =>
      closedTrades.reduce((sum, t) => sum + (t.pnl ? parseFloat(t.pnl) : 0), 0),
    [closedTrades]
  );

  const totalUnrealizedPnl = useMemo(
    () =>
      openTrades.reduce((sum, t) => {
        if (currentPrice == null || !t.open_price) return sum;
        const openP = parseFloat(t.open_price);
        const units =
          typeof t.units === 'string' ? parseFloat(t.units) : (t.units ?? 0);
        const dir = String(t.direction).toLowerCase();
        const pnl =
          dir === 'long' || dir === 'buy'
            ? (currentPrice - openP) * units
            : (openP - currentPrice) * units;
        return sum + pnl;
      }, 0),
    [openTrades, currentPrice]
  );

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

  const closedColumns: Column<TaskTrade>[] = [
    {
      id: 'open_timestamp',
      label: 'Open Timestamp',
      width: 180,
      minWidth: 140,
      render: (row) =>
        row.open_timestamp ? formatTimestamp(row.open_timestamp) : '-',
    },
    {
      id: 'close_timestamp',
      label: 'Close Timestamp',
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
      label: 'Realized PnL',
      width: 120,
      minWidth: 90,
      align: 'right',
      render: (row: TaskTrade) => {
        if (!row.pnl) return '-';
        const val = parseFloat(row.pnl);
        return (
          <Typography
            variant="body2"
            color={val >= 0 ? 'success.main' : 'error.main'}
            fontWeight="bold"
          >
            {val >= 0 ? '+' : ''}¥{val.toFixed(2)}
          </Typography>
        );
      },
    },
  ];

  const openColumns: Column<TaskTrade>[] = [
    {
      id: 'open_timestamp',
      label: 'Open Timestamp',
      width: 180,
      minWidth: 140,
      render: (row) =>
        row.open_timestamp ? formatTimestamp(row.open_timestamp) : '-',
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
      id: 'pips',
      label: 'Pips',
      width: 90,
      minWidth: 70,
      align: 'right',
      render: (row: TaskTrade) => {
        if (currentPrice == null || !row.open_price || !pipSize) return '-';
        const openP = parseFloat(row.open_price);
        const dir = String(row.direction).toLowerCase();
        const diff =
          dir === 'long' || dir === 'buy'
            ? currentPrice - openP
            : openP - currentPrice;
        const pips = diff / pipSize;
        return (
          <Typography
            variant="body2"
            color={pips >= 0 ? 'success.main' : 'error.main'}
            fontWeight="bold"
          >
            {pips >= 0 ? '+' : ''}
            {pips.toFixed(1)}
          </Typography>
        );
      },
    },
    {
      id: 'pnl',
      label: 'Unrealized PnL',
      width: 130,
      minWidth: 100,
      align: 'right',
      render: (row: TaskTrade) => {
        if (currentPrice == null || !row.open_price) return '-';
        const openP = parseFloat(row.open_price);
        const units =
          typeof row.units === 'string'
            ? parseFloat(row.units)
            : (row.units ?? 0);
        const dir = String(row.direction).toLowerCase();
        const val =
          dir === 'long' || dir === 'buy'
            ? (currentPrice - openP) * units
            : (openP - currentPrice) * units;
        return (
          <Typography
            variant="body2"
            color={val >= 0 ? 'success.main' : 'error.main'}
            fontWeight="bold"
          >
            {val >= 0 ? '+' : ''}¥{val.toFixed(2)}
          </Typography>
        );
      },
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
      {/* Closed Positions */}
      <Box
        sx={{
          mb: 2,
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}
      >
        <Typography variant="h6">Closed Positions</Typography>
        <Typography
          variant="subtitle1"
          fontWeight="bold"
          color={totalRealizedPnl >= 0 ? 'success.main' : 'error.main'}
        >
          Total Realized PnL: {totalRealizedPnl >= 0 ? '+' : ''}¥
          {totalRealizedPnl.toFixed(2)}
        </Typography>
      </Box>

      <DataTable
        columns={closedColumns}
        data={closedTrades}
        isLoading={isLoading}
        emptyMessage="No closed positions"
        defaultRowsPerPage={rowsPerPage}
        rowsPerPageOptions={[rowsPerPage]}
        tableMaxHeight="none"
      />

      <TablePagination
        component="div"
        count={closedTotalCount}
        page={page}
        onPageChange={(_e, newPage) => setPage(newPage)}
        rowsPerPage={rowsPerPage}
        onRowsPerPageChange={(e) => {
          setRowsPerPage(parseInt(e.target.value, 10));
          setPage(0);
        }}
        rowsPerPageOptions={[10, 50, 100, 200, 500]}
      />

      {/* Open Positions */}
      <Box
        sx={{
          mt: 4,
          mb: 2,
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}
      >
        <Typography variant="h6">Open Positions</Typography>
        <Typography
          variant="subtitle1"
          fontWeight="bold"
          color={totalUnrealizedPnl >= 0 ? 'success.main' : 'error.main'}
        >
          Total Unrealized PnL: {totalUnrealizedPnl >= 0 ? '+' : ''}¥
          {totalUnrealizedPnl.toFixed(2)}
        </Typography>
      </Box>

      <DataTable
        columns={openColumns}
        data={openTrades}
        isLoading={isLoading}
        emptyMessage="No open positions"
        defaultRowsPerPage={openRowsPerPage}
        rowsPerPageOptions={[openRowsPerPage]}
        tableMaxHeight="none"
      />

      <TablePagination
        component="div"
        count={openTotalCount}
        page={openPage}
        onPageChange={(_e, newPage) => setOpenPage(newPage)}
        rowsPerPage={openRowsPerPage}
        onRowsPerPageChange={(e) => {
          setOpenRowsPerPage(parseInt(e.target.value, 10));
          setOpenPage(0);
        }}
        rowsPerPageOptions={[10, 50, 100, 200]}
      />
    </Box>
  );
};

export default TaskTradesTable;
