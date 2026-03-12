/**
 * TaskLogsTable Component
 *
 * Displays task logs with server-side pagination.
 */

import React, { useCallback, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Box,
  Chip,
  FormControl,
  IconButton,
  InputLabel,
  MenuItem,
  Select,
  Tooltip,
  Typography,
  Alert,
  TablePagination,
  TextField,
  type SelectChangeEvent,
} from '@mui/material';
import FilterListOffIcon from '@mui/icons-material/FilterListOff';
import { Settings as SettingsIcon } from '@mui/icons-material';
import DataTable, { type Column } from '../../common/DataTable';
import { TableSelectionToolbar } from '../../common/TableSelectionToolbar';
import { useTableRowSelection } from '../../../hooks/useTableRowSelection';
import { useTaskLogs, type TaskLog } from '../../../hooks/useTaskLogs';
import { useTaskLogComponents } from '../../../hooks/useTaskLogComponents';
import { TaskType } from '../../../types/common';
import { ColumnConfigDialog } from '../../common/ColumnConfigDialog';
import {
  useColumnConfig,
  columnsToDefaults,
  applyColumnConfig,
} from '../../../hooks/useColumnConfig';
import { buildCopyHandler } from '../../../utils/tableCopyUtils';

interface TaskLogsTableProps {
  taskId: string;
  taskType: TaskType;
  executionRunId?: string;
  enableRealTimeUpdates?: boolean;
}

export const TaskLogsTable: React.FC<TaskLogsTableProps> = ({
  taskId,
  taskType,
  executionRunId,
  enableRealTimeUpdates = false,
}) => {
  const { t } = useTranslation('common');
  const [levelFilter, setLevelFilter] = useState<string[]>([]);
  const [componentFilter, setComponentFilter] = useState<string[]>([]);
  const [timestampFrom, setTimestampFrom] = useState<string>('');
  const [timestampTo, setTimestampTo] = useState<string>('');
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(100);
  const [isReloading, setIsReloading] = useState(false);

  const { components: availableComponents } = useTaskLogComponents({
    taskId,
    taskType,
    executionRunId,
  });

  const { logs, totalCount, isLoading, error, refetch } = useTaskLogs({
    taskId,
    taskType,
    executionRunId,
    level: levelFilter.length > 0 ? levelFilter : undefined,
    component: componentFilter.length > 0 ? componentFilter : undefined,
    timestampFrom: timestampFrom
      ? new Date(timestampFrom).toISOString()
      : undefined,
    timestampTo: timestampTo ? new Date(timestampTo).toISOString() : undefined,
    page: page + 1,
    pageSize: rowsPerPage,
    enableRealTimeUpdates,
  });

  const selection = useTableRowSelection();

  const getRowId = useCallback((row: TaskLog) => String(row.id), []);

  const pageRowIds = logs.map((r) => String(r.id));

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

  const handleLevelFilterChange = (event: SelectChangeEvent<string[]>) => {
    const value = event.target.value;
    setLevelFilter(typeof value === 'string' ? value.split(',') : value);
    setPage(0);
  };

  const handleComponentFilterChange = (
    _event: React.SyntheticEvent,
    value: string[]
  ) => {
    setComponentFilter(value);
    setPage(0);
  };

  // Reset page when executionRunId changes
  const [prevExecutionRunId, setPrevExecutionRunId] = useState(executionRunId);
  if (prevExecutionRunId !== executionRunId) {
    setPrevExecutionRunId(executionRunId);
    if (page !== 0) setPage(0);
  }

  const formatTimestamp = (timestamp: string): string => {
    return new Date(timestamp).toLocaleString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      fractionalSecondDigits: 3,
    });
  };

  const getLevelColor = (
    level: string
  ):
    | 'default'
    | 'primary'
    | 'secondary'
    | 'success'
    | 'error'
    | 'warning'
    | 'info' => {
    const upperLevel = level.toUpperCase();
    switch (upperLevel) {
      case 'ERROR':
      case 'CRITICAL':
        return 'error';
      case 'WARNING':
        return 'warning';
      case 'INFO':
        return 'info';
      case 'DEBUG':
        return 'default';
      default:
        return 'default';
    }
  };

  const columns: Column<TaskLog>[] = [
    {
      id: 'timestamp',
      label: t('tables.logs.timestamp'),
      width: 260,
      minWidth: 200,
      render: (row) => formatTimestamp(row.timestamp as string),
    },
    {
      id: 'level',
      label: t('tables.logs.level'),
      width: 120,
      minWidth: 90,
      render: (row) => (
        <Chip
          label={row.level as string}
          color={getLevelColor(row.level as string)}
        />
      ),
    },
    {
      id: 'component',
      label: t('tables.logs.component'),
      width: 220,
      minWidth: 150,
    },
    {
      id: 'message',
      label: t('tables.logs.message'),
      minWidth: 200,
    },
  ];

  // Column config
  const [colConfigOpen, setColConfigOpen] = useState(false);
  const defaultColItems = columnsToDefaults(columns);
  const {
    columns: colConfig,
    updateColumns,
    resetToDefaults: resetColDefaults,
  } = useColumnConfig('task_logs', defaultColItems);
  const visibleColumns = applyColumnConfig(columns, colConfig);

  const handleCopy = useCallback(() => {
    const logsMap = new Map(logs.map((l) => [String(l.id), l]));
    const extractors: Record<string, (r: TaskLog) => string> = {
      timestamp: (r) =>
        r.timestamp ? new Date(r.timestamp as string).toLocaleString() : '-',
      level: (r) => (r.level as string) ?? '-',
      component: (r) => (r.component as string) ?? '-',
      message: (r) => (r.message as string) ?? '-',
    };
    const { headers, formatRow } = buildCopyHandler(
      visibleColumns,
      extractors,
      logsMap
    );
    selection.copySelectedRows(headers, formatRow, pageRowIds);
  }, [logs, selection, visibleColumns, pageRowIds]);

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
          gap: 2,
          alignItems: 'center',
          flexWrap: 'wrap',
        }}
      >
        <Typography variant="h6">{t('tables.logs.title')}</Typography>
        <FormControl sx={{ minWidth: 200 }} size="small">
          <InputLabel>{t('tables.logs.levelFilter')}</InputLabel>
          <Select
            multiple
            value={levelFilter}
            label={t('tables.logs.levelFilter')}
            onChange={handleLevelFilterChange}
            renderValue={(selected) => (
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                {selected.map((v) => (
                  <Chip
                    key={v}
                    label={v}
                    size="small"
                    color={getLevelColor(v)}
                  />
                ))}
              </Box>
            )}
          >
            <MenuItem value="DEBUG">Debug</MenuItem>
            <MenuItem value="INFO">Info</MenuItem>
            <MenuItem value="WARNING">Warning</MenuItem>
            <MenuItem value="ERROR">Error</MenuItem>
            <MenuItem value="CRITICAL">Critical</MenuItem>
          </Select>
        </FormControl>
        <FormControl sx={{ minWidth: 350 }} size="small">
          <InputLabel>{t('tables.logs.componentFilter')}</InputLabel>
          <Select<string[]>
            multiple
            value={componentFilter}
            label={t('tables.logs.componentFilter')}
            onChange={(e: SelectChangeEvent<string[]>) => {
              const value = e.target.value;
              handleComponentFilterChange(
                e as unknown as React.SyntheticEvent,
                typeof value === 'string' ? value.split(',') : value
              );
            }}
            renderValue={(selected: string[]) => (
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                {selected.map((v: string) => (
                  <Chip key={v} label={v} size="small" />
                ))}
              </Box>
            )}
          >
            {availableComponents.map((comp) => (
              <MenuItem key={comp} value={comp}>
                {comp}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
        <TextField
          label={t('tables.logs.timestampFrom')}
          type="datetime-local"
          size="small"
          value={timestampFrom}
          onChange={(e) => {
            setTimestampFrom(e.target.value);
            setPage(0);
          }}
          slotProps={{ inputLabel: { shrink: true } }}
          sx={{ minWidth: 200 }}
        />
        <TextField
          label={t('tables.logs.timestampTo')}
          type="datetime-local"
          size="small"
          value={timestampTo}
          onChange={(e) => {
            setTimestampTo(e.target.value);
            setPage(0);
          }}
          slotProps={{ inputLabel: { shrink: true } }}
          sx={{ minWidth: 200 }}
        />
        <Tooltip title={t('tables.logs.resetFilters')}>
          <IconButton
            size="small"
            onClick={() => {
              setLevelFilter([]);
              setComponentFilter([]);
              setTimestampFrom('');
              setTimestampTo('');
              setPage(0);
            }}
          >
            <FilterListOffIcon fontSize="small" />
          </IconButton>
        </Tooltip>
        <Box sx={{ flex: 1 }} />
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

      <DataTable
        columns={visibleColumns}
        data={logs}
        isLoading={isLoading}
        emptyMessage={t('tables.logs.noLogs')}
        defaultRowsPerPage={rowsPerPage}
        rowsPerPageOptions={[rowsPerPage]}
        storageKey="task-logs"
        tableMaxHeight="none"
        hidePagination
        selectable
        getRowId={getRowId}
        selectedRowIds={selection.selectedRowIds}
        onToggleRow={selection.toggleRowSelection}
        allPageSelected={selection.isAllPageSelected(pageRowIds)}
        indeterminate={selection.isIndeterminate(pageRowIds)}
        onToggleAll={handleToggleAll}
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
        rowsPerPageOptions={[50, 100, 200, 500]}
      />

      <ColumnConfigDialog
        open={colConfigOpen}
        columns={colConfig}
        onClose={() => setColConfigOpen(false)}
        onSave={updateColumns}
        onReset={resetColDefaults}
      />
    </Box>
  );
};

export default TaskLogsTable;
