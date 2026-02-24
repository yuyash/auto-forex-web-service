/**
 * TaskOrdersTable Component
 *
 * Displays orders for a task with pagination and filtering.
 */

import React, { useState, useCallback } from 'react';
import { Box, Chip, Typography, Alert, TablePagination } from '@mui/material';
import DataTable, { type Column } from '../../common/DataTable';
import { TableSelectionToolbar } from '../../common/TableSelectionToolbar';
import { useTableRowSelection } from '../../../hooks/useTableRowSelection';
import { useTaskOrders, type TaskOrder } from '../../../hooks/useTaskOrders';
import { TaskType } from '../../../types/common';

interface TaskOrdersTableProps {
  taskId: string | number;
  taskType: TaskType;
  celeryTaskId?: string;
  enableRealTimeUpdates?: boolean;
}

export const TaskOrdersTable: React.FC<TaskOrdersTableProps> = ({
  taskId,
  taskType,
  celeryTaskId,
  enableRealTimeUpdates = false,
}) => {
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(50);
  const [isReloading, setIsReloading] = useState(false);
  const selection = useTableRowSelection();

  const { orders, totalCount, isLoading, error, refetch } = useTaskOrders({
    taskId,
    taskType,
    celeryTaskId,
    page: page + 1,
    pageSize: rowsPerPage,
    enableRealTimeUpdates,
  });

  const getRowId = useCallback((row: TaskOrder) => String(row.id), []);
  const pageRowIds = orders.map((r) => String(r.id));

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
    const orderMap = new Map(orders.map((o) => [String(o.id), o]));
    selection.copySelectedRows(
      [
        'Submitted',
        'Instrument',
        'Type',
        'Direction',
        'Units',
        'Status',
        'Requested Price',
        'Fill Price',
      ],
      (id) => {
        const r = orderMap.get(id);
        if (!r) return '';
        return [
          r.submitted_at ? new Date(r.submitted_at).toLocaleString() : '-',
          r.instrument ?? '-',
          r.order_type ?? '-',
          r.direction ?? '-',
          String(Math.abs(r.units)),
          r.status ?? '-',
          r.requested_price ? parseFloat(r.requested_price).toFixed(5) : '-',
          r.fill_price ? parseFloat(r.fill_price).toFixed(5) : '-',
        ].join('\t');
      }
    );
  }, [orders, selection]);

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

  const statusColor = (
    status: string
  ): 'success' | 'error' | 'warning' | 'default' | 'info' => {
    switch (status.toLowerCase()) {
      case 'filled':
        return 'success';
      case 'cancelled':
        return 'warning';
      case 'rejected':
        return 'error';
      case 'pending':
        return 'info';
      case 'triggered':
        return 'default';
      default:
        return 'default';
    }
  };

  const columns: Column<TaskOrder>[] = [
    {
      id: 'submitted_at',
      label: 'Timestamp',
      width: 180,
      minWidth: 140,
      render: (row) =>
        row.submitted_at ? formatTimestamp(row.submitted_at) : '-',
    },
    {
      id: 'instrument',
      label: 'Instrument',
      width: 110,
      minWidth: 80,
    },
    {
      id: 'order_type',
      label: 'Type',
      width: 90,
      minWidth: 70,
      render: (row) => (
        <Chip label={row.order_type.toUpperCase()} variant="outlined" />
      ),
    },
    {
      id: 'direction',
      label: 'Direction',
      width: 90,
      minWidth: 70,
      render: (row) => {
        if (!row.direction)
          return (
            <Typography variant="body2" color="text.secondary">
              CLOSE
            </Typography>
          );
        const dir = row.direction.toLowerCase();
        return (
          <Chip
            label={
              dir === 'long'
                ? 'LONG'
                : dir === 'short'
                  ? 'SHORT'
                  : row.direction.toUpperCase()
            }
            color={dir === 'long' ? 'success' : 'error'}
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
      render: (row) => String(Math.abs(row.units)),
    },
    {
      id: 'status',
      label: 'Status',
      width: 100,
      minWidth: 80,
      render: (row) => (
        <Chip
          label={row.status.toUpperCase()}
          color={statusColor(row.status)}
        />
      ),
    },
    {
      id: 'requested_price',
      label: 'Requested Price',
      width: 130,
      minWidth: 100,
      align: 'right',
      render: (row) =>
        row.requested_price ? parseFloat(row.requested_price).toFixed(5) : '-',
    },
    {
      id: 'fill_price',
      label: 'Fill Price',
      width: 110,
      minWidth: 90,
      align: 'right',
      render: (row) =>
        row.fill_price ? parseFloat(row.fill_price).toFixed(5) : '-',
    },
    {
      id: 'filled_at',
      label: 'Filled At',
      width: 180,
      minWidth: 140,
      render: (row) => (row.filled_at ? formatTimestamp(row.filled_at) : '-'),
    },
    {
      id: 'stop_loss',
      label: 'Stop Loss',
      width: 110,
      minWidth: 90,
      align: 'right',
      render: (row) =>
        row.stop_loss ? parseFloat(row.stop_loss).toFixed(5) : '-',
    },
    {
      id: 'error_message',
      label: 'Error',
      width: 200,
      minWidth: 120,
      render: (row) =>
        row.error_message ? (
          <Typography
            variant="body2"
            color="error.main"
            noWrap
            title={row.error_message}
          >
            {row.error_message}
          </Typography>
        ) : (
          '-'
        ),
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
        <Typography variant="h6">Orders ({totalCount})</Typography>
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
        data={orders}
        isLoading={isLoading}
        emptyMessage="No orders"
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
        defaultOrderBy="submitted_at"
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

export default TaskOrdersTable;
