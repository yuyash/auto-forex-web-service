/**
 * TaskEventsTable Component
 *
 * Displays task events with server-side pagination.
 */

import React, { useCallback, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Box,
  Chip,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
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
import {
  useTaskEvents,
  type TaskEvent,
  type TaskEventSource,
} from '../../../hooks/useTaskEvents';
import { TaskType } from '../../../types/common';
import { EventDetailDialog } from './EventDetailDialog';
import { ColumnConfigDialog } from '../../common/ColumnConfigDialog';
import {
  useColumnConfig,
  columnsToDefaults,
  applyColumnConfig,
} from '../../../hooks/useColumnConfig';

interface TaskEventsTableProps {
  taskId: string | number;
  taskType: TaskType;
  executionRunId?: string;
  enableRealTimeUpdates?: boolean;
}

export const TaskEventsTable: React.FC<TaskEventsTableProps> = ({
  taskId,
  taskType,
  executionRunId,
  enableRealTimeUpdates = false,
}) => {
  const { t } = useTranslation('common');
  const [severityFilter, setSeverityFilter] = useState<string>('');
  const [sourceFilter, setSourceFilter] = useState<TaskEventSource>('trading');
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(100);
  const [isReloading, setIsReloading] = useState(false);
  const [selectedEvent, setSelectedEvent] = useState<TaskEvent | null>(null);

  const { events, totalCount, isLoading, error, refetch } = useTaskEvents({
    taskId,
    taskType,
    executionRunId,
    source: sourceFilter,
    severity: severityFilter || undefined,
    page: page + 1,
    pageSize: rowsPerPage,
    enableRealTimeUpdates,
  });

  const selection = useTableRowSelection();

  const getRowId = useCallback((row: TaskEvent) => String(row.id), []);

  const pageRowIds = events.map((r) => String(r.id));

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
    const eventsMap = new Map(events.map((e) => [String(e.id), e]));
    selection.copySelectedRows(
      ['Timestamp', 'Event Type', 'Severity', 'Description'],
      (id) => {
        const r = eventsMap.get(id);
        if (!r) return '';
        return [
          r.created_at
            ? new Date(r.created_at as string).toLocaleString()
            : '-',
          r.event_type_display ?? r.event_type ?? '-',
          (r.severity as string) ?? '-',
          (r.description as string) ?? '-',
        ].join('\t');
      }
    );
  }, [events, selection]);

  const handleSeverityChange = (value: string) => {
    setSeverityFilter(value);
    setPage(0);
  };
  const handleSourceChange = (value: TaskEventSource) => {
    setSourceFilter(value);
    setPage(0);
  };

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

  const getSeverityColor = (
    severity: string
  ):
    | 'default'
    | 'primary'
    | 'secondary'
    | 'success'
    | 'error'
    | 'warning'
    | 'info' => {
    const lowerSeverity = severity.toLowerCase();
    switch (lowerSeverity) {
      case 'error':
      case 'critical':
        return 'error';
      case 'warning':
        return 'warning';
      case 'info':
        return 'info';
      default:
        return 'default';
    }
  };

  const columns: Column<TaskEvent>[] = [
    {
      id: 'created_at',
      label: t('tables.events.timestamp'),
      width: 240,
      minWidth: 200,
      render: (row) => formatTimestamp(row.created_at as string),
    },
    {
      id: 'event_type',
      label: t('tables.events.eventType'),
      width: 140,
      minWidth: 100,
      render: (row) => row.event_type_display ?? row.event_type,
    },
    {
      id: 'severity',
      label: t('tables.events.severity'),
      width: 100,
      minWidth: 80,
      render: (row) => (
        <Chip
          label={row.severity as string}
          color={getSeverityColor(row.severity as string)}
        />
      ),
    },
    {
      id: 'description',
      label: t('tables.events.description'),
      minWidth: 200,
    },
  ];

  // Column config
  const [colConfigOpen, setColConfigOpen] = useState(false);
  const defaultColItems = columnsToDefaults(columns);
  const {
    columns: colConfig,
    updateColumns,
    resetToDefaults,
  } = useColumnConfig('task_events', defaultColItems);
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
          gap: 2,
          alignItems: 'center',
        }}
      >
        <Typography variant="h6">{t('tables.events.title')}</Typography>
        <FormControl sx={{ minWidth: 170 }}>
          <InputLabel>{t('tables.events.category')}</InputLabel>
          <Select
            value={sourceFilter}
            label={t('tables.events.category')}
            onChange={(e) =>
              handleSourceChange(e.target.value as TaskEventSource)
            }
          >
            <MenuItem value="task">{t('tables.events.taskEvents')}</MenuItem>
            <MenuItem value="trading">
              {t('tables.events.tradingEvents')}
            </MenuItem>
            <MenuItem value="strategy">
              {t('tables.events.strategyEvents')}
            </MenuItem>
          </Select>
        </FormControl>
        <FormControl sx={{ minWidth: 150 }}>
          <InputLabel>{t('tables.events.severityFilter')}</InputLabel>
          <Select
            value={severityFilter}
            label={t('tables.events.severityFilter')}
            onChange={(e) => handleSeverityChange(e.target.value)}
          >
            <MenuItem value="">{t('tables.events.allSeverities')}</MenuItem>
            <MenuItem value="info">Info</MenuItem>
            <MenuItem value="warning">Warning</MenuItem>
            <MenuItem value="error">Error</MenuItem>
            <MenuItem value="critical">Critical</MenuItem>
          </Select>
        </FormControl>
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
        data={events}
        isLoading={isLoading}
        emptyMessage={t('tables.events.noEvents')}
        defaultRowsPerPage={rowsPerPage}
        rowsPerPageOptions={[rowsPerPage]}
        storageKey="task-events"
        tableMaxHeight="none"
        hidePagination
        selectable
        getRowId={getRowId}
        selectedRowIds={selection.selectedRowIds}
        onToggleRow={selection.toggleRowSelection}
        allPageSelected={selection.isAllPageSelected(pageRowIds)}
        indeterminate={selection.isIndeterminate(pageRowIds)}
        onToggleAll={handleToggleAll}
        onRowClick={setSelectedEvent}
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

      <EventDetailDialog
        open={selectedEvent !== null}
        event={selectedEvent}
        onClose={() => setSelectedEvent(null)}
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

export default TaskEventsTable;
