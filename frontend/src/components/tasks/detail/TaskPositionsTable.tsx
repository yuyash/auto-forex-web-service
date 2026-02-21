/**
 * TaskPositionsTable Component
 *
 * Displays closed positions and open positions in separate tables
 * with total Realized PnL and Unrealized PnL summaries.
 * Reads from the `positions` table (Position model).
 */

import React, { useState, useMemo } from 'react';
import { Box, Chip, Typography, Alert, TablePagination } from '@mui/material';
import DataTable, { type Column } from '../../common/DataTable';
import {
  useTaskPositions,
  type TaskPosition,
} from '../../../hooks/useTaskPositions';
import { TaskType } from '../../../types/common';

interface TaskPositionsTableProps {
  taskId: string | number;
  taskType: TaskType;
  enableRealTimeUpdates?: boolean;
  currentPrice?: number | null;
  pipSize?: number | null;
}

export const TaskPositionsTable: React.FC<TaskPositionsTableProps> = ({
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

  // Paginated positions for table display
  const {
    positions: closedPositions,
    totalCount: closedTotalCount,
    isLoading: closedLoading,
    error: closedError,
  } = useTaskPositions({
    taskId,
    taskType,
    status: 'closed',
    page: page + 1,
    pageSize: rowsPerPage,
    enableRealTimeUpdates,
  });

  const {
    positions: openPositions,
    totalCount: openTotalCount,
    isLoading: openLoading,
    error: openError,
  } = useTaskPositions({
    taskId,
    taskType,
    status: 'open',
    page: openPage + 1,
    pageSize: openRowsPerPage,
    enableRealTimeUpdates,
  });

  // All positions (up to 1000) for PnL summary — matches Replay panel
  const { positions: allClosedPositions } = useTaskPositions({
    taskId,
    taskType,
    status: 'closed',
    pageSize: 1000,
    enableRealTimeUpdates,
  });

  const { positions: allOpenPositions } = useTaskPositions({
    taskId,
    taskType,
    status: 'open',
    pageSize: 1000,
    enableRealTimeUpdates,
  });

  const isLoading = closedLoading || openLoading;
  const error = closedError || openError;

  const totalRealizedPnl = useMemo(
    () =>
      allClosedPositions.reduce(
        (sum, p) => sum + (p.realized_pnl ? parseFloat(p.realized_pnl) : 0),
        0
      ),
    [allClosedPositions]
  );

  const totalUnrealizedPnl = useMemo(
    () =>
      allOpenPositions.reduce((sum, p) => {
        // Always compute from currentPrice for open positions
        // (matches TaskReplayPanel calculation exactly)
        if (currentPrice == null || !p.entry_price) return sum;
        const entryP = parseFloat(p.entry_price);
        const units = Math.abs(p.units ?? 0);
        const dir = String(p.direction).toLowerCase();
        const pnl =
          dir === 'long'
            ? (currentPrice - entryP) * units
            : (entryP - currentPrice) * units;
        return sum + pnl;
      }, 0),
    [allOpenPositions, currentPrice]
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

  const closedColumns: Column<TaskPosition>[] = [
    {
      id: 'entry_time',
      label: 'Open Timestamp',
      width: 180,
      minWidth: 140,
      render: (row) => (row.entry_time ? formatTimestamp(row.entry_time) : '-'),
    },
    {
      id: 'exit_time',
      label: 'Close Timestamp',
      width: 180,
      minWidth: 140,
      render: (row) => (row.exit_time ? formatTimestamp(row.exit_time) : '-'),
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
          label={row.direction}
          color={row.direction === 'long' ? 'success' : 'error'}
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
      render: (row) => String(Math.abs(row.units)),
    },
    {
      id: 'entry_price',
      label: 'Open Price',
      width: 110,
      minWidth: 80,
      align: 'right',
      render: (row) =>
        row.entry_price ? `¥${parseFloat(row.entry_price).toFixed(3)}` : '-',
    },
    {
      id: 'exit_price',
      label: 'Close Price',
      width: 110,
      minWidth: 80,
      align: 'right',
      render: (row) =>
        row.exit_price ? `¥${parseFloat(row.exit_price).toFixed(3)}` : '-',
    },
    {
      id: 'pips',
      label: 'Pips',
      width: 90,
      minWidth: 70,
      align: 'right',
      render: (row) => {
        if (!row.entry_price || !row.exit_price || !pipSize) return '-';
        const entryP = parseFloat(row.entry_price);
        const exitP = parseFloat(row.exit_price);
        if (!Number.isFinite(entryP) || !Number.isFinite(exitP)) return '-';
        const dir = String(row.direction).toLowerCase();
        const diff = dir === 'long' ? exitP - entryP : entryP - exitP;
        const pips = diff / pipSize;
        if (!Number.isFinite(pips)) return '-';
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
      id: 'realized_pnl',
      label: 'Realized PnL',
      width: 120,
      minWidth: 90,
      align: 'right',
      render: (row) => {
        if (!row.realized_pnl) return '-';
        const val = parseFloat(row.realized_pnl);
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

  const openColumns: Column<TaskPosition>[] = [
    {
      id: 'entry_time',
      label: 'Open Timestamp',
      width: 180,
      minWidth: 140,
      render: (row) => (row.entry_time ? formatTimestamp(row.entry_time) : '-'),
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
          label={row.direction}
          color={row.direction === 'long' ? 'success' : 'error'}
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
      render: (row) => String(Math.abs(row.units)),
    },
    {
      id: 'entry_price',
      label: 'Open Price',
      width: 110,
      minWidth: 80,
      align: 'right',
      render: (row) =>
        row.entry_price ? `¥${parseFloat(row.entry_price).toFixed(3)}` : '-',
    },
    {
      id: 'pips',
      label: 'Pips',
      width: 90,
      minWidth: 70,
      align: 'right',
      render: (row) => {
        if (currentPrice == null || !row.entry_price || !pipSize) return '-';
        const entryP = parseFloat(row.entry_price);
        const dir = String(row.direction).toLowerCase();
        const diff =
          dir === 'long' ? currentPrice - entryP : entryP - currentPrice;
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
      id: 'unrealized_pnl',
      label: 'Unrealized PnL',
      width: 130,
      minWidth: 100,
      align: 'right',
      render: (row) => {
        // Always compute from currentPrice for open positions so the
        // value updates in real-time (the DB column is not kept in sync).
        if (currentPrice == null || !row.entry_price) return '-';
        const entryP = parseFloat(row.entry_price);
        const units = Math.abs(row.units ?? 0);
        const dir = String(row.direction).toLowerCase();
        const val =
          dir === 'long'
            ? (currentPrice - entryP) * units
            : (entryP - currentPrice) * units;
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
        data={closedPositions}
        isLoading={isLoading}
        emptyMessage="No closed positions"
        defaultRowsPerPage={rowsPerPage}
        rowsPerPageOptions={[rowsPerPage]}
        tableMaxHeight="none"
        hidePagination
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
        data={openPositions}
        isLoading={isLoading}
        emptyMessage="No open positions"
        defaultRowsPerPage={openRowsPerPage}
        rowsPerPageOptions={[openRowsPerPage]}
        tableMaxHeight="none"
        hidePagination
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

export default TaskPositionsTable;
