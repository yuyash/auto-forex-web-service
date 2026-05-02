/**
 * TaskLogsTable Component
 *
 * Displays task logs with server-side pagination.
 */

import React, { useCallback, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Box,
  Chip,
  Checkbox,
  FormControl,
  IconButton,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Tooltip,
  Typography,
  Alert,
  TablePagination,
  TextField,
  type SelectChangeEvent,
} from '@mui/material';
import { useMediaQuery, useTheme } from '@mui/material';
import FilterListOffIcon from '@mui/icons-material/FilterListOff';
import { Settings as SettingsIcon } from '@mui/icons-material';
import DataTable, { type Column } from '../../common/DataTable';
import { TableSelectionToolbar } from '../../common/TableSelectionToolbar';
import { DateRangeFilter } from '../../common/DateRangeFilter';
import { TableFilterBar } from '../../common/TableFilterBar';
import { tableFilterDateRangeSx } from '../../common/tableFilterLayout';
import { useTableRowSelection } from '../../../hooks/useTableRowSelection';
import {
  useTaskLogs,
  type TaskLog,
  type TaskLogMessageMatchMode,
} from '../../../hooks/useTaskLogs';
import { useTaskLogComponents } from '../../../hooks/useTaskLogComponents';
import type { TaskType } from '../../../types/common';
import { ColumnConfigDialog } from '../../common/ColumnConfigDialog';
import {
  useColumnConfig,
  columnsToDefaults,
  applyColumnConfig,
} from '../../../hooks/useColumnConfig';
import { buildCopyHandler } from '../../../utils/tableCopyUtils';
import { useStrategies } from '../../../hooks/useStrategies';
import { useDateTimeFormatter } from '../../../hooks/useDateTimeFormatter';

interface TaskLogsTableProps {
  taskId: string;
  taskType: TaskType;
  executionRunId?: string;
  enableRealTimeUpdates?: boolean;
  strategyType?: string;
}

type SortOrder = 'asc' | 'desc';

const toOrdering = (field: string, order: SortOrder): string =>
  order === 'desc' ? `-${field}` : field;

export const TaskLogsTable: React.FC<TaskLogsTableProps> = ({
  taskId,
  taskType,
  executionRunId,
  enableRealTimeUpdates = false,
  strategyType,
}) => {
  const { t } = useTranslation('common');
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  const { formatDateTime } = useDateTimeFormatter({
    includeSeconds: true,
    includeMilliseconds: true,
    includeTimezone: true,
  });
  const [levelFilter, setLevelFilter] = useState<string[]>([]);
  const [componentFilter, setComponentFilter] = useState<string[]>([]);
  const [messageFilter, setMessageFilter] = useState('');
  const [messageMatchMode, setMessageMatchMode] =
    useState<TaskLogMessageMatchMode>('partial');
  const [timestampFrom, setTimestampFrom] = useState<string>('');
  const [timestampTo, setTimestampTo] = useState<string>('');
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(100);
  const [sortField, setSortField] = useState('timestamp');
  const [sortOrder, setSortOrder] = useState<SortOrder>('desc');
  const [isReloading, setIsReloading] = useState(false);
  const { strategies } = useStrategies();
  const strategyEventLabels = useMemo(
    () =>
      strategies.find((strategy) => strategy.id === strategyType)?.capabilities
        ?.events?.strategy_event_labels ?? {},
    [strategies, strategyType]
  );

  const { components: availableComponents } = useTaskLogComponents({
    taskId,
    taskType,
    executionRunId,
  });
  const messageRegexError = useMemo(() => {
    if (messageMatchMode !== 'regex' || !messageFilter) {
      return '';
    }
    try {
      new RegExp(messageFilter);
      return '';
    } catch {
      return t('tables.logs.invalidRegex');
    }
  }, [messageFilter, messageMatchMode, t]);

  const { logs, totalCount, isLoading, error, refresh } = useTaskLogs({
    taskId,
    taskType,
    executionRunId,
    level: levelFilter.length > 0 ? levelFilter : undefined,
    component: componentFilter.length > 0 ? componentFilter : undefined,
    message: messageFilter && !messageRegexError ? messageFilter : undefined,
    messageMatchMode,
    timestampFrom: timestampFrom
      ? new Date(timestampFrom).toISOString()
      : undefined,
    timestampTo: timestampTo ? new Date(timestampTo).toISOString() : undefined,
    ordering: toOrdering(sortField, sortOrder),
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
    await refresh();
    setIsReloading(false);
  }, [refresh]);

  const handleSortChange = useCallback((field: string, order: SortOrder) => {
    setSortField(field);
    setSortOrder(order);
    setPage(0);
  }, []);

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
  const handleMessageMatchModeChange = (
    event: SelectChangeEvent<TaskLogMessageMatchMode>
  ) => {
    setMessageMatchMode(event.target.value as TaskLogMessageMatchMode);
    setPage(0);
  };
  const auditComponents = availableComponents.filter((component) =>
    ['task.audit', 'config.audit'].includes(component)
  );

  // Reset page when executionRunId changes
  const [prevExecutionRunId, setPrevExecutionRunId] = useState(executionRunId);
  if (prevExecutionRunId !== executionRunId) {
    setPrevExecutionRunId(executionRunId);
    if (page !== 0) setPage(0);
  }

  const formatTimestamp = useCallback(
    (timestamp: string): string => formatDateTime(timestamp),
    [formatDateTime]
  );

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

  const getStrategyEventLabel = useCallback(
    (row: TaskLog): string | null => {
      const eventType = String(row.details?.strategy_event_type ?? '').trim();
      if (!eventType) return null;
      return strategyEventLabels[eventType] ?? eventType.replace(/_/g, ' ');
    },
    [strategyEventLabels]
  );

  const columns: Column<TaskLog>[] = [
    {
      id: 'timestamp',
      label: t('tables.logs.timestamp'),
      width: 280,
      minWidth: 240,
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
      width: 1000,
      minWidth: 400,
      render: (row) => {
        const strategyEventLabel = getStrategyEventLabel(row);
        return (
          <Box
            sx={{
              display: 'grid',
              gap: 0.75,
              maxWidth: '100%',
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
              overflowWrap: 'anywhere',
              fontFamily: 'monospace',
            }}
          >
            {strategyEventLabel ? (
              <Chip
                label={strategyEventLabel}
                size="small"
                variant="outlined"
                sx={{ justifySelf: 'start', fontFamily: 'inherit' }}
              />
            ) : null}
            <span>{String(row.message ?? '')}</span>
          </Box>
        );
      },
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
        r.timestamp ? formatTimestamp(r.timestamp as string) : '-',
      level: (r) => (r.level as string) ?? '-',
      component: (r) => (r.component as string) ?? '-',
      message: (r) => {
        const strategyEventLabel = getStrategyEventLabel(r);
        return [strategyEventLabel, (r.message as string) ?? '-']
          .filter(Boolean)
          .join(' | ');
      },
    };
    const { headers, formatRow } = buildCopyHandler(
      visibleColumns,
      extractors,
      logsMap
    );
    selection.copySelectedRows(headers, formatRow, pageRowIds);
  }, [
    formatTimestamp,
    getStrategyEventLabel,
    logs,
    pageRowIds,
    selection,
    visibleColumns,
  ]);

  const renderMobileCell = useCallback(
    (column: Column<TaskLog>, row: TaskLog) => {
      if (column.render) {
        return column.render(row);
      }
      return String(row[column.id as keyof TaskLog] ?? '');
    },
    []
  );

  if (error) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="error">{error.message}</Alert>
      </Box>
    );
  }

  return (
    <Box sx={{ p: { xs: 1.5, sm: 3 } }}>
      <Box
        sx={{
          mb: 1,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <Typography variant="h6">{t('tables.logs.title')}</Typography>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
          <Tooltip title={t('tables.logs.resetFilters')}>
            <IconButton
              size="small"
              onClick={() => {
                setLevelFilter([]);
                setComponentFilter([]);
                setMessageFilter('');
                setMessageMatchMode('partial');
                setTimestampFrom('');
                setTimestampTo('');
                setPage(0);
              }}
            >
              <FilterListOffIcon fontSize="small" />
            </IconButton>
          </Tooltip>
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
      <TableFilterBar>
        <FormControl
          sx={{
            flex: { xs: '1 1 100%', sm: '0 1 200px' },
            minWidth: 0,
          }}
          size="small"
        >
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
        <FormControl
          sx={{
            flex: { xs: '1 1 100%', sm: '0 1 320px' },
            minWidth: 0,
            maxWidth: { xs: '100%', sm: 350 },
          }}
          size="small"
        >
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
        <DateRangeFilter
          from={timestampFrom}
          to={timestampTo}
          onFromChange={(v) => {
            setTimestampFrom(v);
            setPage(0);
          }}
          onToChange={(v) => {
            setTimestampTo(v);
            setPage(0);
          }}
          fromLabel={t('tables.logs.timestampFrom')}
          toLabel={t('tables.logs.timestampTo')}
          sx={tableFilterDateRangeSx}
        />
        <TextField
          size="small"
          label={t('tables.logs.messageFilter')}
          placeholder={t('tables.logs.messageFilterPlaceholder')}
          value={messageFilter}
          onChange={(event) => {
            setMessageFilter(event.target.value);
            setPage(0);
          }}
          error={Boolean(messageRegexError)}
          helperText={messageRegexError || undefined}
          sx={{
            flex: { xs: '1 1 100%', md: '1 1 340px' },
            minWidth: 0,
          }}
        />
        <FormControl
          sx={{
            flex: { xs: '1 1 100%', sm: '0 1 190px' },
            minWidth: 0,
          }}
          size="small"
        >
          <InputLabel>{t('tables.logs.messageMatchMode')}</InputLabel>
          <Select<TaskLogMessageMatchMode>
            value={messageMatchMode}
            label={t('tables.logs.messageMatchMode')}
            onChange={handleMessageMatchModeChange}
          >
            <MenuItem value="partial">
              {t('tables.logs.messageMatchPartial')}
            </MenuItem>
            <MenuItem value="exact">
              {t('tables.logs.messageMatchExact')}
            </MenuItem>
            <MenuItem value="regex">
              {t('tables.logs.messageMatchRegex')}
            </MenuItem>
          </Select>
        </FormControl>
        {auditComponents.length > 0 && (
          <Box
            sx={{
              display: 'flex',
              gap: 0.75,
              flex: { xs: '1 1 100%', sm: '0 1 auto' },
              flexWrap: 'wrap',
            }}
          >
            {auditComponents.map((component) => {
              const selected = componentFilter.includes(component);
              return (
                <Chip
                  key={component}
                  label={
                    component === 'config.audit' ? 'Config edits' : 'Task edits'
                  }
                  color={selected ? 'primary' : 'default'}
                  variant={selected ? 'filled' : 'outlined'}
                  onClick={() => {
                    setComponentFilter(selected ? [] : [component]);
                    setPage(0);
                  }}
                />
              );
            })}
          </Box>
        )}
      </TableFilterBar>

      {isMobile ? (
        <Box sx={{ display: 'grid', gap: 1.5 }}>
          {isLoading && logs.length === 0 ? (
            <Paper variant="outlined" sx={{ p: 2 }}>
              <Typography color="text.secondary">
                {t('common.loading')}
              </Typography>
            </Paper>
          ) : logs.length === 0 ? (
            <Paper variant="outlined" sx={{ p: 2 }}>
              <Typography color="text.secondary">
                {t('tables.logs.noLogs')}
              </Typography>
            </Paper>
          ) : (
            logs.map((row) => {
              const rowId = getRowId(row);
              const isSelected = selection.selectedRowIds.has(rowId);
              return (
                <Paper key={rowId} variant="outlined" sx={{ p: 1.5 }}>
                  <Box
                    sx={{
                      display: 'flex',
                      alignItems: 'flex-start',
                      justifyContent: 'space-between',
                      gap: 1,
                      mb: 1,
                    }}
                  >
                    <Box sx={{ minWidth: 0 }}>
                      <Typography variant="body2" fontWeight={600}>
                        {formatTimestamp(row.timestamp as string)}
                      </Typography>
                      <Box
                        sx={{
                          mt: 0.75,
                          display: 'flex',
                          gap: 0.75,
                          flexWrap: 'wrap',
                          alignItems: 'center',
                        }}
                      >
                        <Chip
                          label={row.level as string}
                          color={getLevelColor(row.level as string)}
                          size="small"
                        />
                        <Chip
                          label={String(row.component ?? '-')}
                          size="small"
                          variant="outlined"
                        />
                      </Box>
                    </Box>
                    <Checkbox
                      checked={isSelected}
                      onChange={() => selection.toggleRowSelection(rowId)}
                    />
                  </Box>

                  <Box sx={{ display: 'grid', gap: 1 }}>
                    {visibleColumns
                      .filter(
                        (column) =>
                          String(column.id) !== 'timestamp' &&
                          String(column.id) !== 'level' &&
                          String(column.id) !== 'component'
                      )
                      .map((column) => (
                        <Box key={String(column.id)}>
                          <Typography
                            variant="caption"
                            color="text.secondary"
                            sx={{ display: 'block', mb: 0.25 }}
                          >
                            {column.label}
                          </Typography>
                          <Box
                            sx={{
                              whiteSpace:
                                String(column.id) === 'message'
                                  ? 'pre-wrap'
                                  : 'normal',
                              wordBreak: 'break-word',
                              overflowWrap: 'anywhere',
                              fontFamily:
                                String(column.id) === 'message'
                                  ? 'monospace'
                                  : 'inherit',
                            }}
                          >
                            {renderMobileCell(column, row)}
                          </Box>
                        </Box>
                      ))}
                  </Box>
                </Paper>
              );
            })
          )}
        </Box>
      ) : (
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
          sortMode="server"
          orderBy={sortField}
          order={sortOrder}
          onSortChange={handleSortChange}
          fillEmptyRows
        />
      )}

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
        rowsPerPageOptions={[25, 50, 100, 200, 500, 1000]}
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
