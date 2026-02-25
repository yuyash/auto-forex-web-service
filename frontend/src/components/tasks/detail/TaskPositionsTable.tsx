/**
 * TaskPositionsTable Component
 *
 * Displays closed positions and open positions in separate tables
 * with total Realized PnL and Unrealized PnL summaries.
 * Reads from the `positions` table (Position model).
 */

import React, { useState, useCallback } from 'react';
import { Box, Chip, Typography, Alert, TablePagination } from '@mui/material';
import DataTable, { type Column } from '../../common/DataTable';
import { TableSelectionToolbar } from '../../common/TableSelectionToolbar';
import { useTableRowSelection } from '../../../hooks/useTableRowSelection';
import {
  useTaskPositions,
  type TaskPosition,
} from '../../../hooks/useTaskPositions';
import { useTaskSummary } from '../../../hooks/useTaskSummary';
import { TaskType } from '../../../types/common';

interface TaskPositionsTableProps {
  taskId: string | number;
  taskType: TaskType;
  executionRunId?: number;
  enableRealTimeUpdates?: boolean;
  currentPrice?: number | null;
  pipSize?: number | null;
}

export const TaskPositionsTable: React.FC<TaskPositionsTableProps> = ({
  taskId,
  taskType,
  executionRunId,
  enableRealTimeUpdates = false,
  currentPrice,
  pipSize,
}) => {
  const [page, setPage] = useState(0);
  const [openPage, setOpenPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(10);
  const [openRowsPerPage, setOpenRowsPerPage] = useState(10);
  const [isClosedReloading, setIsClosedReloading] = useState(false);
  const [isOpenReloading, setIsOpenReloading] = useState(false);

  const closedSelection = useTableRowSelection();
  const openSelection = useTableRowSelection();

  // Paginated positions for table display
  const {
    positions: closedPositions,
    totalCount: closedTotalCount,
    isLoading: closedLoading,
    error: closedError,
    refetch: refetchClosed,
  } = useTaskPositions({
    taskId,
    taskType,
    executionRunId,
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
    refetch: refetchOpen,
  } = useTaskPositions({
    taskId,
    taskType,
    executionRunId,
    status: 'open',
    page: openPage + 1,
    pageSize: openRowsPerPage,
    enableRealTimeUpdates,
  });

  // PnL summary from server-side aggregation (no full-fetch needed)
  const {
    summary: {
      pnl: { realized: totalRealizedPnl, unrealized: totalUnrealizedPnl },
    },
    refetch: refetchPnl,
  } = useTaskSummary(String(taskId), taskType, executionRunId);

  // Refetch PnL when real-time updates toggle changes (task finishes)
  const prevRealTimeRef = React.useRef(enableRealTimeUpdates);
  React.useEffect(() => {
    if (prevRealTimeRef.current && !enableRealTimeUpdates) {
      refetchPnl();
    }
    prevRealTimeRef.current = enableRealTimeUpdates;
  }, [enableRealTimeUpdates, refetchPnl]);

  // Periodic PnL refresh while task is running
  React.useEffect(() => {
    if (!enableRealTimeUpdates) return;
    const interval = setInterval(refetchPnl, 10000);
    return () => clearInterval(interval);
  }, [enableRealTimeUpdates, refetchPnl]);

  const isLoading = closedLoading || openLoading;
  const error = closedError || openError;

  const getRowId = useCallback((row: TaskPosition) => String(row.id), []);

  const closedPageRowIds = closedPositions.map((r) => String(r.id));
  const openPageRowIds = openPositions.map((r) => String(r.id));

  const handleClosedToggleAll = useCallback(() => {
    if (closedSelection.isAllPageSelected(closedPageRowIds)) {
      for (const id of closedPageRowIds) {
        if (closedSelection.selectedRowIds.has(id)) {
          closedSelection.toggleRowSelection(id);
        }
      }
    } else {
      closedSelection.selectAllOnPage(closedPageRowIds);
    }
  }, [closedPageRowIds, closedSelection]);

  const handleOpenToggleAll = useCallback(() => {
    if (openSelection.isAllPageSelected(openPageRowIds)) {
      for (const id of openPageRowIds) {
        if (openSelection.selectedRowIds.has(id)) {
          openSelection.toggleRowSelection(id);
        }
      }
    } else {
      openSelection.selectAllOnPage(openPageRowIds);
    }
  }, [openPageRowIds, openSelection]);

  const handleClosedReload = useCallback(async () => {
    setIsClosedReloading(true);
    await refetchClosed();
    setIsClosedReloading(false);
  }, [refetchClosed]);

  const handleOpenReload = useCallback(async () => {
    setIsOpenReloading(true);
    await refetchOpen();
    setIsOpenReloading(false);
  }, [refetchOpen]);

  const handleClosedCopy = useCallback(() => {
    const posMap = new Map(closedPositions.map((p) => [String(p.id), p]));
    closedSelection.copySelectedRows(
      [
        'Open Time',
        'Close Time',
        'Instrument',
        'Direction',
        'Units',
        'Open Price',
        'Close Price',
        'Realized PnL',
      ],
      (id) => {
        const r = posMap.get(id);
        if (!r) return '';
        return [
          r.entry_time ? new Date(r.entry_time).toLocaleString() : '-',
          r.exit_time ? new Date(r.exit_time).toLocaleString() : '-',
          r.instrument ?? '-',
          r.direction ?? '-',
          String(Math.abs(r.units)),
          r.entry_price ? parseFloat(r.entry_price).toFixed(3) : '-',
          r.exit_price ? parseFloat(r.exit_price).toFixed(3) : '-',
          r.exit_price && r.entry_price
            ? (() => {
                const exit = parseFloat(r.exit_price);
                const entry = parseFloat(r.entry_price);
                const units = Math.abs(r.units ?? 0);
                const dir = String(r.direction).toLowerCase();
                const pnl =
                  dir === 'long'
                    ? (exit - entry) * units
                    : (entry - exit) * units;
                return pnl.toFixed(2);
              })()
            : '-',
        ].join('\t');
      }
    );
  }, [closedPositions, closedSelection]);

  const handleOpenCopy = useCallback(() => {
    const posMap = new Map(openPositions.map((p) => [String(p.id), p]));
    openSelection.copySelectedRows(
      [
        'Open Time',
        'Instrument',
        'Direction',
        'Units',
        'Open Price',
        'Unrealized PnL',
      ],
      (id) => {
        const r = posMap.get(id);
        if (!r) return '';
        let unrealizedPnl = '-';
        if (currentPrice != null && r.entry_price) {
          const entryP = parseFloat(r.entry_price);
          const units = Math.abs(r.units ?? 0);
          const dir = String(r.direction).toLowerCase();
          const val =
            dir === 'long'
              ? (currentPrice - entryP) * units
              : (entryP - currentPrice) * units;
          unrealizedPnl = val.toFixed(2);
        }
        return [
          r.entry_time ? new Date(r.entry_time).toLocaleString() : '-',
          r.instrument ?? '-',
          r.direction ?? '-',
          String(Math.abs(r.units)),
          r.entry_price ? parseFloat(r.entry_price).toFixed(3) : '-',
          unrealizedPnl,
        ].join('\t');
      }
    );
  }, [openPositions, openSelection, currentPrice]);

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
          label={row.direction.toUpperCase()}
          color={row.direction === 'long' ? 'success' : 'error'}
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
      id: 'layer_index',
      label: 'Layer',
      width: 70,
      minWidth: 50,
      align: 'right',
      render: (row) =>
        row.layer_index != null ? String(row.layer_index) : '-',
    },
    {
      id: 'retracement_count',
      label: 'Retracement',
      width: 100,
      minWidth: 70,
      align: 'right',
      render: (row) =>
        row.retracement_count != null ? String(row.retracement_count) : '-',
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
        if (!row.exit_price || !row.entry_price) return '-';
        const exit = parseFloat(row.exit_price);
        const entry = parseFloat(row.entry_price);
        const units = Math.abs(row.units ?? 0);
        const dir = String(row.direction).toLowerCase();
        const val =
          dir === 'long' ? (exit - entry) * units : (entry - exit) * units;
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
          label={row.direction.toUpperCase()}
          color={row.direction === 'long' ? 'success' : 'error'}
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
      id: 'layer_index',
      label: 'Layer',
      width: 70,
      minWidth: 50,
      align: 'right',
      render: (row) =>
        row.layer_index != null ? String(row.layer_index) : '-',
    },
    {
      id: 'retracement_count',
      label: 'Retracement',
      width: 100,
      minWidth: 70,
      align: 'right',
      render: (row) =>
        row.retracement_count != null ? String(row.retracement_count) : '-',
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
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <Typography
            variant="subtitle1"
            fontWeight="bold"
            color={totalRealizedPnl >= 0 ? 'success.main' : 'error.main'}
          >
            Total Realized PnL: {totalRealizedPnl >= 0 ? '+' : ''}¥
            {totalRealizedPnl.toFixed(2)}
          </Typography>
          <TableSelectionToolbar
            selectedCount={closedSelection.selectedRowIds.size}
            onCopy={handleClosedCopy}
            onSelectAll={() =>
              closedSelection.selectAllOnPage(closedPageRowIds)
            }
            onReset={closedSelection.resetSelection}
            onReload={handleClosedReload}
            isReloading={isClosedReloading}
          />
        </Box>
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
        selectable
        getRowId={getRowId}
        selectedRowIds={closedSelection.selectedRowIds}
        onToggleRow={closedSelection.toggleRowSelection}
        allPageSelected={closedSelection.isAllPageSelected(closedPageRowIds)}
        indeterminate={closedSelection.isIndeterminate(closedPageRowIds)}
        onToggleAll={handleClosedToggleAll}
        defaultOrderBy="entry_time"
        defaultOrder="desc"
        fillEmptyRows
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
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <Typography
            variant="subtitle1"
            fontWeight="bold"
            color={totalUnrealizedPnl >= 0 ? 'success.main' : 'error.main'}
          >
            Total Unrealized PnL: {totalUnrealizedPnl >= 0 ? '+' : ''}¥
            {totalUnrealizedPnl.toFixed(2)}
          </Typography>
          <TableSelectionToolbar
            selectedCount={openSelection.selectedRowIds.size}
            onCopy={handleOpenCopy}
            onSelectAll={() => openSelection.selectAllOnPage(openPageRowIds)}
            onReset={openSelection.resetSelection}
            onReload={handleOpenReload}
            isReloading={isOpenReloading}
          />
        </Box>
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
        selectable
        getRowId={getRowId}
        selectedRowIds={openSelection.selectedRowIds}
        onToggleRow={openSelection.toggleRowSelection}
        allPageSelected={openSelection.isAllPageSelected(openPageRowIds)}
        indeterminate={openSelection.isIndeterminate(openPageRowIds)}
        onToggleAll={handleOpenToggleAll}
        defaultOrderBy="entry_time"
        defaultOrder="desc"
        fillEmptyRows
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
