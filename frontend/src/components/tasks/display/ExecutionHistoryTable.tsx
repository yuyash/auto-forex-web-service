/**
 * ExecutionHistoryTable Component
 *
 * Displays paginated execution history for a task using the shared DataTable,
 * with column visibility/ordering via ColumnConfigDialog.
 */

import { useState, useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  Box,
  Chip,
  Typography,
  TablePagination,
  IconButton,
  Tooltip,
} from '@mui/material';
import {
  Settings as SettingsIcon,
  Refresh as RefreshIcon,
} from '@mui/icons-material';
import DataTable, { type Column } from '../../common/DataTable';
import { ColumnConfigDialog } from '../../common/ColumnConfigDialog';
import {
  useColumnConfig,
  columnsToDefaults,
  applyColumnConfig,
} from '../../../hooks/useColumnConfig';
import { useTaskExecutions } from '../../../hooks/useTaskExecutions';
import { StatusBadge } from './StatusBadge';
import { TaskStatus, TaskType } from '../../../types/common';
import type { TaskExecution } from '../../../types/execution';

interface ExecutionHistoryTableProps {
  taskId: string;
  taskType: TaskType;
}

export function ExecutionHistoryTable({
  taskId,
  taskType,
}: ExecutionHistoryTableProps) {
  const { t } = useTranslation('common');
  const navigate = useNavigate();
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(10);
  const [colConfigOpen, setColConfigOpen] = useState(false);

  const { data, isLoading, refetch } = useTaskExecutions(
    taskId,
    taskType,
    { page: page + 1, page_size: rowsPerPage, include_metrics: true },
    { enablePolling: true, pollingInterval: 5000 }
  );

  const executions = data?.results ?? [];
  const totalCount = data?.count ?? 0;

  const formatDate = (v: string | undefined | null): string => {
    if (!v) return '-';
    return new Date(v).toLocaleString();
  };

  const formatDuration = (exec: TaskExecution): string => {
    if (exec.duration != null) {
      const d =
        typeof exec.duration === 'string'
          ? parseFloat(exec.duration)
          : exec.duration;
      if (isNaN(d)) return '-';
      if (d >= 3600)
        return `${Math.floor(d / 3600)}h ${Math.floor((d % 3600) / 60)}m`;
      if (d >= 60) return `${Math.floor(d / 60)}m ${Math.floor(d % 60)}s`;
      return `${Math.floor(d)}s`;
    }
    if (!exec.started_at || !exec.completed_at) return '-';
    const ms =
      new Date(exec.completed_at).getTime() -
      new Date(exec.started_at).getTime();
    const s = Math.floor(ms / 1000);
    if (s >= 3600)
      return `${Math.floor(s / 3600)}h ${Math.floor((s % 3600) / 60)}m`;
    if (s >= 60) return `${Math.floor(s / 60)}m ${s % 60}s`;
    return `${s}s`;
  };

  const fmt = (v: string | number | undefined | null): string => {
    if (v == null) return '-';
    const n = typeof v === 'string' ? parseFloat(v) : v;
    return isNaN(n) ? '-' : n.toFixed(2);
  };

  const columns: Column<TaskExecution>[] = useMemo(
    () => [
      {
        id: 'execution_number',
        label: t('tables.executions.executionId'),
        width: 120,
        minWidth: 80,
        render: (row: TaskExecution) => (
          <Typography
            variant="body2"
            fontWeight="medium"
            sx={{ fontFamily: 'monospace' }}
          >
            {row.execution_number}
          </Typography>
        ),
      },
      {
        id: 'status',
        label: t('tables.executions.status'),
        width: 120,
        minWidth: 90,
        render: (row: TaskExecution) => <StatusBadge status={row.status} />,
      },
      {
        id: 'progress',
        label: t('tables.executions.progress'),
        width: 90,
        minWidth: 70,
        align: 'right' as const,
        render: (row: TaskExecution) => `${row.progress}%`,
      },
      {
        id: 'started_at',
        label: t('tables.executions.started'),
        width: 200,
        minWidth: 160,
        render: (row: TaskExecution) => formatDate(row.started_at),
      },
      {
        id: 'completed_at',
        label: t('tables.executions.completed'),
        width: 200,
        minWidth: 160,
        render: (row: TaskExecution) => formatDate(row.completed_at),
      },
      {
        id: 'duration',
        label: t('tables.executions.duration'),
        width: 110,
        minWidth: 80,
        render: (row: TaskExecution) => formatDuration(row),
      },
      {
        id: 'metrics.total_return',
        label: t('tables.executions.returnPct'),
        width: 110,
        minWidth: 80,
        align: 'right' as const,
        render: (row: TaskExecution) => {
          if (!row.metrics?.total_return)
            return (
              <Typography variant="body2" color="text.secondary">
                -
              </Typography>
            );
          const v = parseFloat(String(row.metrics.total_return));
          return (
            <Chip
              label={`${v >= 0 ? '+' : ''}${v.toFixed(2)}%`}
              color={v >= 0 ? 'success' : 'error'}
              size="small"
              sx={{ minWidth: 70 }}
            />
          );
        },
      },
      {
        id: 'metrics.total_pnl',
        label: t('tables.executions.pnl'),
        width: 110,
        minWidth: 80,
        align: 'right' as const,
        render: (row: TaskExecution) => {
          if (!row.metrics?.total_pnl) return '-';
          const v = parseFloat(String(row.metrics.total_pnl));
          return (
            <Typography
              variant="body2"
              color={v >= 0 ? 'success.main' : 'error.main'}
            >
              {fmt(v)}
            </Typography>
          );
        },
      },
      {
        id: 'metrics.total_trades',
        label: t('tables.executions.trades'),
        width: 80,
        minWidth: 60,
        align: 'right' as const,
        render: (row: TaskExecution) => row.metrics?.total_trades ?? '-',
      },
      {
        id: 'metrics.win_rate',
        label: t('tables.executions.winRate'),
        width: 100,
        minWidth: 70,
        align: 'right' as const,
        render: (row: TaskExecution) =>
          row.metrics?.win_rate != null ? `${fmt(row.metrics.win_rate)}%` : '-',
      },
      {
        id: 'error_message',
        label: t('tables.executions.error'),
        width: 200,
        minWidth: 120,
        render: (row: TaskExecution) =>
          row.error_message ? (
            <Typography
              variant="body2"
              color="error"
              noWrap
              title={row.error_message}
            >
              {row.error_message}
            </Typography>
          ) : (
            '-'
          ),
      },
    ],
    [t]
  );

  const defaultColItems = useMemo(() => columnsToDefaults(columns), [columns]);
  const storageKey = `exec_history_${taskType}`;
  const {
    columns: colConfig,
    updateColumns,
    resetToDefaults,
  } = useColumnConfig(storageKey, defaultColItems);
  const visibleColumns = applyColumnConfig(columns, colConfig);

  const handleRowClick = useCallback(
    (exec: TaskExecution) => {
      if (
        exec.status === TaskStatus.RUNNING ||
        exec.status === TaskStatus.PAUSED
      ) {
        const prefix = taskType === TaskType.BACKTEST ? 'backtest' : 'trading';
        navigate(`/${prefix}-tasks/${taskId}/running`);
      }
    },
    [navigate, taskId, taskType]
  );

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
        <Typography variant="subtitle1" sx={{ flex: 1 }}>
          {t('tables.executions.title')}
        </Typography>
        <Tooltip title={t('tables.executions.refresh')}>
          <IconButton
            size="small"
            onClick={() => refetch()}
            aria-label={t('tables.executions.refresh')}
          >
            <RefreshIcon fontSize="small" />
          </IconButton>
        </Tooltip>
        <Tooltip title={t('tables.executions.configureColumns')}>
          <IconButton
            size="small"
            onClick={() => setColConfigOpen(true)}
            aria-label={t('tables.executions.configureColumns')}
          >
            <SettingsIcon fontSize="small" />
          </IconButton>
        </Tooltip>
      </Box>

      <DataTable<TaskExecution>
        columns={visibleColumns}
        data={executions}
        isLoading={isLoading}
        emptyMessage={t('tables.executions.noExecutions')}
        defaultRowsPerPage={rowsPerPage}
        rowsPerPageOptions={[rowsPerPage]}
        storageKey={`exec-history-widths-${taskType}`}
        tableMaxHeight="none"
        hidePagination
        onRowClick={handleRowClick}
        defaultOrderBy="started_at"
        defaultOrder="desc"
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
        rowsPerPageOptions={[5, 10, 25, 50]}
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
}
