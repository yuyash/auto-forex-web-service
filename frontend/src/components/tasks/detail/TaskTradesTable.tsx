/**
 * TaskTradesTable Component
 *
 * Displays all trades for a task in a single table.
 * Trades are append-only event records; position open/close status
 * is tracked in the positions table.
 */

import React, { useState, useCallback } from 'react';
import { Box, Chip, Typography, Alert, TablePagination } from '@mui/material';
import DataTable, { type Column } from '../../common/DataTable';
import { TableSelectionToolbar } from '../../common/TableSelectionToolbar';
import { useTableRowSelection } from '../../../hooks/useTableRowSelection';
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
  const [rowsPerPage, setRowsPerPage] = useState(10);
  const [isReloading, setIsReloading] = useState(false);

  const { trades, totalCount, isLoading, error, refetch } = useTaskTrades({
    taskId,
    taskType,
    page: page + 1,
    pageSize: rowsPerPage,
    enableRealTimeUpdates,
  });

  const selection = useTableRowSelection();

  const getRowId = useCallback((row: TaskTrade) => String(row.id), []);

  const pageRowIds = trades.map((r) => String(r.id));

  const handleToggleAll = useCallback(() => {
    if (selection.isAllPageSelected(pageRowIds)) {
      selection.deselectAllOnPage(pageRowIds);
    } else {
      selection.selectAllOnPage(pageRowIds);
    }
  }, [pageRowIds, selection]);

  const handleReload = useCallback(async () => {
    setIsReloading(true);
    await refetch();
    setIsReloading(false);
  }, [refetch]);

  const handleCopy = useCallback(() => {
    const tradesMap = new Map(trades.map((t) => [String(t.id), t]));
    selection.copySelectedRows(
      [
        'Timestamp',
        'Instrument',
        'Type',
        'Direction',
        'Units',
        'Price',
        'Layer',
        'Retracement',
      ],
      (id) => {
        const r = tradesMap.get(id);
        if (!r) return '';
        return [
          r.timestamp ? new Date(r.timestamp).toLocaleString() : '-',
          r.instrument ?? '-',
          r.execution_method_display || r.execution_method || '-',
          String(r.direction ?? '').toUpperCase(),
          r.units ?? '-',
          r.price ? parseFloat(r.price).toFixed(5) : '-',
          r.layer_index != null ? String(r.layer_index) : '-',
          r.retracement_count != null ? String(r.retracement_count) : '-',
        ].join('\t');
      }
    );
  }, [trades, selection]);

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
        const dir = row.direction ? String(row.direction).toLowerCase() : '';
        if (!dir) return null;
        return (
          <Chip
            label={dir === 'long' ? 'LONG' : dir === 'short' ? 'SHORT' : dir}
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
    {
      id: 'retracement_count',
      label: 'Retracement',
      width: 100,
      minWidth: 70,
      align: 'right',
      render: (row: TaskTrade) =>
        row.retracement_count != null ? String(row.retracement_count) : '-',
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
        <TableSelectionToolbar
          selectedCount={selection.selectedRowIds.size}
          onCopy={handleCopy}
          onSelectAll={() => selection.selectAllOnPage(pageRowIds)}
          onReset={selection.resetSelection}
          onReload={handleReload}
          isReloading={isReloading}
        />
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
        selectable
        getRowId={getRowId}
        selectedRowIds={selection.selectedRowIds}
        onToggleRow={selection.toggleRowSelection}
        allPageSelected={selection.isAllPageSelected(pageRowIds)}
        indeterminate={selection.isIndeterminate(pageRowIds)}
        onToggleAll={handleToggleAll}
        defaultOrderBy="timestamp"
        defaultOrder="desc"
        fillEmptyRows
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
