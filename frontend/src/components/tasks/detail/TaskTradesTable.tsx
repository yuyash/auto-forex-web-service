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
  InputAdornment,
  TextField,
  Tooltip,
} from '@mui/material';
import {
  Settings as SettingsIcon,
  Search as SearchIcon,
  Clear as ClearIcon,
} from '@mui/icons-material';
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
import { buildCopyHandler } from '../../../utils/tableCopyUtils';

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
  const [cycleIdFilter, setCycleIdFilter] = useState('');

  const { trades, totalCount, isLoading, error, refresh } = useTaskTrades({
    taskId,
    taskType,
    executionRunId,
    page: page + 1,
    pageSize: rowsPerPage,
    cycleId: cycleIdFilter || undefined,
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
    await refresh();
    setIsReloading(false);
  }, [refresh]);

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
        // Use i18n key if available, fall back to backend display name.
        // When the trade is a stop-loss rebuild, show the rebuild label
        // instead of the generic open_position label.
        const methodKey =
          row.is_rebuild && row.execution_method === 'open_position'
            ? 'rebuild_position'
            : row.execution_method || '';
        const i18nLabel = t(`tables.trades.executionMethod.${methodKey}`, {
          defaultValue: '',
        });
        const method =
          i18nLabel ||
          row.execution_method_display ||
          row.execution_method ||
          '-';
        const isProtection =
          row.execution_method === 'shrink' ||
          row.execution_method === 'margin_protection' ||
          row.execution_method === 'stop_loss' ||
          row.execution_method === 'volatility_lock' ||
          (row.description?.startsWith('[PROTECTION]') ?? false);
        return (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
            <Typography variant="body2">{method}</Typography>
            {isProtection && (
              <Chip
                label="⚠"
                size="small"
                color="warning"
                variant="filled"
                sx={{
                  minWidth: 0,
                  height: 20,
                  '& .MuiChip-label': { px: 0.5, fontSize: '0.7rem' },
                }}
              />
            )}
          </Box>
        );
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
        row.layer_index != null ? `L${row.layer_index}` : '-',
    },
    {
      id: 'retracement_count',
      label: t('tables.trades.retracement'),
      width: 80,
      minWidth: 80,
      align: 'right',
      render: (row: TaskTrade) =>
        row.retracement_count != null ? `R${row.retracement_count}` : '-',
    },
    {
      id: 'description',
      label: t('tables.trades.description'),
      minWidth: 200,
      render: (row: TaskTrade) => row.description || '-',
    },
    {
      id: 'stop_loss_price',
      label: t('tables.trades.stopLossPrice'),
      width: 130,
      minWidth: 90,
      align: 'right',
      render: (row: TaskTrade) =>
        row.stop_loss_price
          ? `¥${parseFloat(row.stop_loss_price).toFixed(3)}`
          : '-',
    },
    {
      id: 'is_rebuild',
      label: t('tables.trades.isRebuild'),
      width: 80,
      minWidth: 60,
      render: (row: TaskTrade) =>
        row.is_rebuild ? (
          <Chip
            label={t('tables.trades.rebuild')}
            size="small"
            color="info"
            variant="outlined"
            sx={{
              height: 22,
              '& .MuiChip-label': { px: 0.75, fontSize: '0.75rem' },
            }}
          />
        ) : (
          '-'
        ),
    },
  ];

  // Column config
  const [colConfigOpen, setColConfigOpen] = useState(false);
  const defaultColItems = columnsToDefaults(columns).map((c) =>
    ['stop_loss_price', 'is_rebuild'].includes(c.id)
      ? { ...c, visible: false }
      : c
  );
  const {
    columns: colConfig,
    updateColumns,
    resetToDefaults,
  } = useColumnConfig('task_trades', defaultColItems);
  const visibleColumns = applyColumnConfig(columns, colConfig);

  const handleCopy = useCallback(() => {
    const tradesMap = new Map(trades.map((tr) => [String(tr.id), tr]));
    const extractors: Record<string, (r: TaskTrade) => string> = {
      id: (r) => (r.id ? String(r.id).slice(0, 8) : '-'),
      timestamp: (r) =>
        r.timestamp ? new Date(r.timestamp).toLocaleString() : '-',
      instrument: (r) => r.instrument ?? '-',
      execution_method: (r) => {
        const methodKey =
          r.is_rebuild && r.execution_method === 'open_position'
            ? 'rebuild_position'
            : r.execution_method || '';
        const i18nLabel = t(`tables.trades.executionMethod.${methodKey}`, {
          defaultValue: '',
        });
        return (
          i18nLabel || r.execution_method_display || r.execution_method || '-'
        );
      },
      direction: (r) => String(r.direction ?? '').toUpperCase(),
      units: (r) => String(r.units ?? '-'),
      price: (r) => (r.price ? parseFloat(r.price).toFixed(5) : '-'),
      layer_index: (r) => (r.layer_index != null ? String(r.layer_index) : '-'),
      retracement_count: (r) =>
        r.retracement_count != null ? String(r.retracement_count) : '-',
      description: (r) => r.description || '-',
      stop_loss_price: (r) =>
        r.stop_loss_price
          ? `¥${parseFloat(r.stop_loss_price).toFixed(3)}`
          : '-',
      is_rebuild: (r) => (r.is_rebuild ? 'Yes' : '-'),
    };
    const { headers, formatRow } = buildCopyHandler(
      visibleColumns,
      extractors,
      tradesMap
    );
    selection.copySelectedRows(headers, formatRow, pageRowIds);
  }, [t, trades, selection, visibleColumns, pageRowIds]);

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
          gap: 1,
          flexWrap: 'wrap',
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Typography variant="h6">
            {t('tables.trades.title')} ({totalCount})
          </Typography>
          <TextField
            size="small"
            placeholder={t('tables.trades.cycleIdFilter')}
            value={cycleIdFilter}
            onChange={(e) => setCycleIdFilter(e.target.value)}
            sx={{ width: 280 }}
            slotProps={{
              input: {
                startAdornment: (
                  <InputAdornment position="start">
                    <SearchIcon fontSize="small" />
                  </InputAdornment>
                ),
                endAdornment: cycleIdFilter ? (
                  <InputAdornment position="end">
                    <IconButton
                      size="small"
                      onClick={() => setCycleIdFilter('')}
                      edge="end"
                    >
                      <ClearIcon fontSize="small" />
                    </IconButton>
                  </InputAdornment>
                ) : null,
              },
            }}
          />
        </Box>
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
        rowsPerPageOptions={[10, 25, 50, 100, 200, 500, 1000]}
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
