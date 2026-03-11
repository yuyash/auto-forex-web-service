/**
 * TaskTradesTable Component
 *
 * Displays all trades for a task in a single table.
 * Trades are append-only event records; position open/close status
 * is tracked in the positions table.
 */

import React, { useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Box,
  Chip,
  Typography,
  Alert,
  TablePagination,
  IconButton,
  Tooltip,
} from '@mui/material';
import { Settings as SettingsIcon } from '@mui/icons-material';
import DataTable, { type Column } from '../../common/DataTable';
import { TableSelectionToolbar } from '../../common/TableSelectionToolbar';
import { useTableRowSelection } from '../../../hooks/useTableRowSelection';
import { useTaskTrades, type TaskTrade } from '../../../hooks/useTaskTrades';
import { TaskType } from '../../../types/common';
import { ColumnConfigDialog } from '../../common/ColumnConfigDialog';
import {
  useColumnConfig,
  columnsToDefaults,
  applyColumnConfig,
} from '../../../hooks/useColumnConfig';

interface TaskTradesTableProps {
  taskId: string | number;
  taskType: TaskType;
  executionRunId?: string;
  enableRealTimeUpdates?: boolean;
  pipSize?: number | null;
}

export const TaskTradesTable: React.FC<TaskTradesTableProps> = ({
  taskId,
  taskType,
  executionRunId,
  enableRealTimeUpdates = false,
}) => {
  const { t } = useTranslation('common');
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(50);
  const [isReloading, setIsReloading] = useState(false);

  const { trades, totalCount, isLoading, error, refetch } = useTaskTrades({
    taskId,
    taskType,
    executionRunId,
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
        'Description',
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
          r.description || '-',
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
      id: 'id',
      label: t('tables.trades.tradeId'),
      width: 120,
      minWidth: 80,
      render: (row) => (row.id ? String(row.id).slice(0, 8) : '-'),
    },
    {
      id: 'timestamp',
      label: t('tables.trades.timestamp'),
      width: 220,
      minWidth: 220,
      render: (row) => (row.timestamp ? formatTimestamp(row.timestamp) : '-'),
    },
    {
      id: 'instrument',
      label: t('tables.trades.instrument'),
      width: 100,
      minWidth: 100,
    },
    {
      id: 'execution_method',
      label: t('tables.trades.type'),
      width: 150,
      minWidth: 150,
      render: (row) => {
        const method =
          row.execution_method_display || row.execution_method || '-';
        return <Typography variant="body2">{method}</Typography>;
      },
    },
    {
      id: 'direction',
      label: t('tables.trades.direction'),
      width: 120,
      minWidth: 120,
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
      label: t('tables.trades.units'),
      width: 100,
      minWidth: 100,
      align: 'right',
    },
    {
      id: 'price',
      label: t('tables.trades.price'),
      width: 120,
      minWidth: 120,
      align: 'right',
      render: (row: TaskTrade) =>
        row.price ? parseFloat(row.price).toFixed(5) : '-',
    },
    {
      id: 'layer_index',
      label: t('tables.trades.layer'),
      width: 80,
      minWidth: 80,
      align: 'right',
      render: (row: TaskTrade) =>
        row.layer_index != null ? String(row.layer_index) : '-',
    },
    {
      id: 'retracement_count',
      label: t('tables.trades.retracement'),
      width: 80,
      minWidth: 80,
      align: 'right',
      render: (row: TaskTrade) =>
        row.retracement_count != null ? String(row.retracement_count) : '-',
    },
    {
      id: 'description',
      label: t('tables.trades.description'),
      minWidth: 200,
      render: (row: TaskTrade) => row.description || '-',
    },
  ];

  // Column config
  const [colConfigOpen, setColConfigOpen] = useState(false);
  const defaultColItems = columnsToDefaults(columns);
  const {
    columns: colConfig,
    updateColumns,
    resetToDefaults,
  } = useColumnConfig('task_trades', defaultColItems);
  const visibleColumns = applyColumnConfig(columns, colConfig);

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
        <Typography variant="h6">
          {t('tables.trades.title')} ({totalCount})
        </Typography>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Tooltip title={t('common:columnConfig.configureColumns')}>
            <IconButton
              size="small"
              onClick={() => setColConfigOpen(true)}
              aria-label={t('common:columnConfig.configureColumns')}
            >
              <SettingsIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          <TableSelectionToolbar
            selectedCount={selection.selectedRowIds.size}
            onCopy={handleCopy}
            onSelectAll={() => selection.selectAllOnPage(pageRowIds)}
            onReset={selection.resetSelection}
            onReload={handleReload}
            isReloading={isReloading}
          />
        </Box>
      </Box>

      <DataTable
        columns={visibleColumns}
        data={trades}
        isLoading={isLoading}
        emptyMessage={t('tables.trades.noTrades')}
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

      <ColumnConfigDialog
        open={colConfigOpen}
        columns={colConfig}
        onClose={() => setColConfigOpen(false)}
        onSave={updateColumns}
        onReset={resetToDefaults}
      />
    </Box>
  );
};

export default TaskTradesTable;
