/**
 * ExecutionHistoryTable Component
 *
 * Displays paginated execution history for a task using the shared DataTable,
 * with column visibility/ordering via ColumnConfigDialog and multi-select
 * comparison support via checkboxes.
 */

import { useState, useCallback, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  Box,
  Button,
  Chip,
  Typography,
  TablePagination,
  IconButton,
  Tooltip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Paper,
  TextField,
} from '@mui/material';
import {
  CompareArrows as CompareIcon,
  Settings as SettingsIcon,
  Refresh as RefreshIcon,
  Delete as DeleteIcon,
  NoteAdd as NoteAddIcon,
  StickyNote2 as NoteIcon,
} from '@mui/icons-material';
import DataTable, { type Column } from '../../common/DataTable';
import { ColumnConfigDialog } from '../../common/ColumnConfigDialog';
import {
  useColumnConfig,
  columnsToDefaults,
  applyColumnConfig,
} from '../../../hooks/useColumnConfig';
import { useTaskExecutions } from '../../../hooks/useTaskExecutions';
import { useTableRowSelection } from '../../../hooks/useTableRowSelection';
import { StatusBadge } from './StatusBadge';
import { ExecutionComparisonDialog } from '../detail/ExecutionComparisonDialog';
import { TaskType } from '../../../types/common';
import type { TaskExecution } from '../../../types/execution';
import { useAuth } from '../../../contexts/AuthContext';
import { useAppSettings } from '../../../hooks/useAppSettings';
import {
  formatAppPercent,
  formatMoneyAmount,
  formatMoneyPayload,
} from '../../../utils/numberFormat';
import {
  getStrategyConfigSnapshotHash,
  getStrategyConfigSnapshotRevision,
} from '../../../utils/strategyConfigRevision';
import { quoteCurrencyFromInstrument } from '../../../utils/instrumentCurrency';
import { formatDateTimeInTimezone } from '../../../utils/timezone';
import { formatCurrencyConversionContext } from '../../../utils/currencyConversion';
import { backtestTasksApi, tradingTasksApi } from '../../../services/api';

interface ExecutionHistoryTableProps {
  taskId: string;
  taskType: TaskType;
  instrument?: string;
}

export function ExecutionHistoryTable({
  taskId,
  taskType,
  instrument,
}: ExecutionHistoryTableProps) {
  const { t } = useTranslation('common');
  const { user } = useAuth();
  const { settings: appSettings } = useAppSettings();
  const [searchParams, setSearchParams] = useSearchParams();
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(10);
  const [colConfigOpen, setColConfigOpen] = useState(false);
  const [compareOpen, setCompareOpen] = useState(false);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [notesDialogOpen, setNotesDialogOpen] = useState(false);
  const [notesTarget, setNotesTarget] = useState<TaskExecution | null>(null);
  const [notesValue, setNotesValue] = useState('');
  const [revisionTarget, setRevisionTarget] = useState<TaskExecution | null>(
    null
  );

  // URL-driven comparison: ?compare=id1,id2,...
  const compareParam = searchParams.get('compare');
  const compareIdsFromUrl = useMemo(
    () =>
      compareParam ? compareParam.split(',').filter((id) => id.length > 0) : [],
    [compareParam]
  );

  const {
    selectedRowIds: checkedIds,
    toggleRowSelection: toggleCheck,
    selectAllOnPage: checkAllOnPage,
    deselectAllOnPage: uncheckAllOnPage,
    resetSelection: resetChecked,
    isAllPageSelected: isAllPageChecked,
    isIndeterminate: isCheckIndeterminate,
  } = useTableRowSelection();

  const { data, isLoading, refresh } = useTaskExecutions(
    taskId,
    taskType,
    { page: page + 1, page_size: rowsPerPage, include_metrics: true },
    {
      enablePolling: true,
      pollingInterval: appSettings.healthCheckIntervalSeconds * 1000,
    }
  );

  const executions = useMemo(() => data?.results ?? [], [data?.results]);
  const totalCount = data?.count ?? 0;
  const timezone = user?.timezone || 'UTC';
  const language = user?.language;

  const pageRowIds = useMemo(() => executions.map((e) => e.id), [executions]);

  const formatDate = useCallback(
    (v: string | undefined | null): string => {
      if (!v) return '-';
      return formatDateTimeInTimezone(v, timezone, language, {
        includeTimezone: true,
      });
    },
    [language, timezone]
  );

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

  const pnlCurrency = quoteCurrencyFromInstrument(instrument) ?? '';
  const formatMetricMoney = (
    money:
      | { amount?: string | number | null; currency?: string | null }
      | null
      | undefined,
    fallbackValue: number,
    fallbackCurrency: string
  ) =>
    money
      ? formatMoneyPayload(money, {
          signed: true,
        })
      : formatMoneyAmount(fallbackValue, fallbackCurrency, {
          signed: true,
        });

  const columns: Column<TaskExecution>[] = useMemo(() => {
    const baseColumns: Column<TaskExecution>[] = [
      {
        id: 'execution_number',
        label: t('tables.executions.executionId'),
        width: 300,
        minWidth: 200,
        render: (row: TaskExecution) => (
          <Typography
            variant="body2"
            fontWeight="medium"
            sx={{ fontFamily: 'monospace', whiteSpace: 'nowrap' }}
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
        id: 'segment_index',
        label: t('tables.executions.configSegment'),
        width: 100,
        minWidth: 80,
        align: 'right' as const,
        defaultVisible: false,
        render: (row: TaskExecution) => (
          <Tooltip title={t('tables.executions.configSegmentTooltip')}>
            <Typography variant="body2" sx={{ display: 'inline-block' }}>
              {row.segment_index ?? 1}
            </Typography>
          </Tooltip>
        ),
      },
      {
        id: 'config_revision_count',
        label: t('tables.executions.configRevisions'),
        width: 120,
        minWidth: 90,
        align: 'right' as const,
        render: (row: TaskExecution) => {
          const revision =
            row.configuration_revision ??
            getStrategyConfigSnapshotRevision(row.strategy_config);
          const hash =
            row.configuration_hash ??
            getStrategyConfigSnapshotHash(row.strategy_config);
          return (
            <Tooltip
              title={
                hash
                  ? t('tables.executions.configRevisionsTooltip', {
                      revision: revision ?? '-',
                      hash,
                    })
                  : t('tables.executions.configRevisionsTooltipNoHash', {
                      revision: revision ?? '-',
                    })
              }
            >
              <Chip
                label={revision ? `Rev.${revision}` : '-'}
                size="small"
                variant={revision ? 'filled' : 'outlined'}
                clickable
                onClick={(event) => {
                  event.stopPropagation();
                  setRevisionTarget(row);
                }}
              />
            </Tooltip>
          );
        },
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
          if (row.metrics?.total_return == null)
            return (
              <Typography variant="body2" color="text.secondary">
                -
              </Typography>
            );
          const v = parseFloat(String(row.metrics.total_return));
          if (isNaN(v))
            return (
              <Typography variant="body2" color="text.secondary">
                -
              </Typography>
            );
          return (
            <Chip
              label={formatAppPercent(v, 2, true)}
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
        width: 160,
        minWidth: 110,
        align: 'right' as const,
        render: (row: TaskExecution) => {
          if (row.metrics?.total_pnl == null) return '-';
          const v = parseFloat(String(row.metrics.total_pnl));
          if (isNaN(v)) return '-';
          const acctCcy = row.metrics?.pnl_currency || '';
          const quoteCcy = row.metrics?.quote_currency || pnlCurrency || '';
          const hasQuote =
            row.metrics?.total_pnl_quote != null &&
            quoteCcy &&
            quoteCcy !== acctCcy;
          const conversionTooltip = formatCurrencyConversionContext(
            row.metrics?.display_conversion_context,
            { language, separators: appSettings, t, timezone }
          );
          const qv = hasQuote
            ? parseFloat(String(row.metrics.total_pnl_quote))
            : NaN;
          return (
            <Box>
              <Tooltip
                title={conversionTooltip}
                arrow
                disableHoverListener={!conversionTooltip}
              >
                <Typography
                  variant="body2"
                  color={v >= 0 ? 'success.main' : 'error.main'}
                  sx={{ whiteSpace: 'nowrap' }}
                >
                  {formatMetricMoney(
                    row.metrics?.total_pnl_display_money ??
                      row.metrics?.total_pnl_money,
                    v,
                    acctCcy
                  )}
                </Typography>
              </Tooltip>
              {hasQuote && !isNaN(qv) && (
                <Typography
                  variant="caption"
                  color="text.secondary"
                  sx={{ whiteSpace: 'nowrap' }}
                >
                  {formatMetricMoney(
                    row.metrics?.total_pnl_quote_money,
                    qv,
                    quoteCcy
                  )}
                </Typography>
              )}
            </Box>
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
          row.metrics?.win_rate != null
            ? formatAppPercent(Number(row.metrics.win_rate), 2)
            : '-',
      },
      {
        id: 'notes',
        label: t('tables.executions.notes'),
        width: 160,
        minWidth: 100,
        render: (row: TaskExecution) =>
          row.notes ? (
            <Tooltip
              title={row.notes}
              placement="bottom-start"
              slotProps={{
                tooltip: {
                  sx: {
                    maxWidth: 400,
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-word',
                  },
                },
              }}
            >
              <Typography
                variant="body2"
                sx={{
                  display: '-webkit-box',
                  WebkitLineClamp: 2,
                  WebkitBoxOrient: 'vertical',
                  overflow: 'hidden',
                  cursor: 'help',
                }}
              >
                {row.notes}
              </Typography>
            </Tooltip>
          ) : (
            '-'
          ),
      },
      {
        id: 'error_message',
        label: t('tables.executions.error'),
        width: 200,
        minWidth: 120,
        render: (row: TaskExecution) =>
          row.error_message ? (
            <Tooltip
              title={row.error_message}
              placement="bottom-start"
              slotProps={{
                tooltip: {
                  sx: {
                    maxWidth: 500,
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-word',
                  },
                },
              }}
            >
              <Typography
                variant="body2"
                color="error"
                sx={{
                  display: '-webkit-box',
                  WebkitLineClamp: 3,
                  WebkitBoxOrient: 'vertical',
                  overflow: 'hidden',
                  cursor: 'help',
                }}
              >
                {row.error_message}
              </Typography>
            </Tooltip>
          ) : (
            '-'
          ),
      },
    ];

    if (taskType === TaskType.BACKTEST) {
      baseColumns.splice(2, 0, {
        id: 'progress',
        label: t('tables.executions.progress'),
        width: 90,
        minWidth: 70,
        align: 'right' as const,
        render: (row: TaskExecution) =>
          formatAppPercent(Number(row.progress ?? 0), 0),
      });
    }

    return baseColumns;
  }, [appSettings, formatDate, language, pnlCurrency, t, taskType, timezone]);

  const defaultColItems = useMemo(() => columnsToDefaults(columns), [columns]);
  const storageKey = `exec_history_${taskType}_v3`;
  const {
    columns: colConfig,
    updateColumns,
    resetToDefaults,
  } = useColumnConfig(storageKey, defaultColItems);
  const visibleColumns = applyColumnConfig(columns, colConfig);

  const handleRowClick = useCallback(
    (exec: TaskExecution) => {
      const tab = searchParams.get('tab') || 'overview';
      setSearchParams({ tab, execution: exec.id });
    },
    [searchParams, setSearchParams]
  );

  const handleToggleAll = useCallback(() => {
    if (isAllPageChecked(pageRowIds)) {
      uncheckAllOnPage(pageRowIds);
    } else {
      checkAllOnPage(pageRowIds);
    }
  }, [pageRowIds, isAllPageChecked, uncheckAllOnPage, checkAllOnPage]);

  const checkedCount = checkedIds.size;

  // Build the list of checked executions for the comparison dialog
  const checkedExecutions = useMemo(
    () => executions.filter((e) => checkedIds.has(e.id)),
    [executions, checkedIds]
  );

  // URL-driven comparison: auto-open dialog when ?compare= is present
  // and we have matching execution data loaded
  const urlCompareExecutions = useMemo(() => {
    if (compareIdsFromUrl.length < 2) return [];
    const idSet = new Set(compareIdsFromUrl);
    return executions.filter((e) => idSet.has(e.id));
  }, [compareIdsFromUrl, executions]);

  const isCompareFromUrl =
    compareIdsFromUrl.length >= 2 && urlCompareExecutions.length >= 2;
  const effectiveCompareOpen = compareOpen || isCompareFromUrl;
  const effectiveCompareExecutions = isCompareFromUrl
    ? urlCompareExecutions
    : checkedExecutions;

  const handleCompareOpen = useCallback(() => {
    // Set URL param with selected execution IDs
    const ids = [...checkedIds].join(',');
    const next = new URLSearchParams(searchParams);
    next.set('compare', ids);
    setSearchParams(next);
    setCompareOpen(true);
  }, [checkedIds, searchParams, setSearchParams]);

  const handleCompareClose = useCallback(() => {
    setCompareOpen(false);
    resetChecked();
    // Remove compare param from URL
    const next = new URLSearchParams(searchParams);
    next.delete('compare');
    setSearchParams(next);
  }, [resetChecked, searchParams, setSearchParams]);

  return (
    <Box>
      <Typography variant="subtitle1" sx={{ mb: 1 }}>
        {t('tables.executions.title')}
      </Typography>
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          mb: 1,
          flexWrap: 'wrap',
          gap: 1,
        }}
      >
        <Button
          size="small"
          variant="contained"
          startIcon={<CompareIcon />}
          disabled={checkedCount < 2}
          onClick={handleCompareOpen}
        >
          {checkedCount >= 2
            ? t('tables.executions.compareSelected', { count: checkedCount })
            : t('tables.executions.compare')}
        </Button>
        <Button
          size="small"
          variant="outlined"
          color="error"
          startIcon={<DeleteIcon />}
          disabled={checkedCount < 1}
          onClick={() => setDeleteConfirmOpen(true)}
        >
          {t('actions.delete')}
        </Button>
        <Button
          size="small"
          variant="outlined"
          startIcon={<NoteAddIcon />}
          disabled={checkedCount !== 1}
          onClick={() => {
            const target = executions.find((e) => checkedIds.has(e.id));
            if (target) {
              setNotesTarget(target);
              setNotesValue(target.notes ?? '');
              setNotesDialogOpen(true);
            }
          }}
        >
          {t('tables.executions.notes')}
        </Button>
        <Box sx={{ flex: 1 }} />
        <Tooltip title={t('tables.executions.refresh')}>
          <IconButton
            size="small"
            onClick={() => void refresh()}
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
        selectable
        getRowId={(row) => row.id}
        selectedRowIds={checkedIds}
        onToggleRow={toggleCheck}
        allPageSelected={isAllPageChecked(pageRowIds)}
        indeterminate={isCheckIndeterminate(pageRowIds)}
        onToggleAll={handleToggleAll}
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

      {effectiveCompareOpen && effectiveCompareExecutions.length >= 2 && (
        <ExecutionComparisonDialog
          open={effectiveCompareOpen}
          onClose={handleCompareClose}
          executions={effectiveCompareExecutions}
          taskId={taskId}
          taskType={taskType}
        />
      )}

      {/* Delete confirmation dialog */}
      <Dialog
        open={deleteConfirmOpen}
        onClose={() => !isDeleting && setDeleteConfirmOpen(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>{t('tables.executions.deleteTitle')}</DialogTitle>
        <DialogContent>
          <Typography>
            {t('tables.executions.deleteMessage', { count: checkedCount })}
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button
            onClick={() => setDeleteConfirmOpen(false)}
            disabled={isDeleting}
          >
            {t('actions.cancel')}
          </Button>
          <Button
            color="error"
            variant="contained"
            disabled={isDeleting}
            onClick={async () => {
              setIsDeleting(true);
              const api =
                taskType === TaskType.BACKTEST
                  ? backtestTasksApi
                  : tradingTasksApi;
              try {
                for (const id of checkedIds) {
                  await api.deleteExecution(taskId, id);
                }
                resetChecked();
                setDeleteConfirmOpen(false);
                void refresh();
              } catch {
                // error handled by API layer
              } finally {
                setIsDeleting(false);
              }
            }}
          >
            {isDeleting ? t('actions.deleting') : t('actions.delete')}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Notes dialog */}
      <Dialog
        open={notesDialogOpen}
        onClose={() => setNotesDialogOpen(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <NoteIcon />
            {t('tables.executions.notesDialogTitle')}
          </Box>
        </DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            multiline
            minRows={3}
            maxRows={8}
            fullWidth
            value={notesValue}
            onChange={(e) => setNotesValue(e.target.value)}
            placeholder={t('tables.executions.notesPlaceholder')}
            sx={{ mt: 1 }}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setNotesDialogOpen(false)}>
            {t('actions.cancel')}
          </Button>
          <Button
            variant="contained"
            onClick={async () => {
              if (!notesTarget) return;
              const api =
                taskType === TaskType.BACKTEST
                  ? backtestTasksApi
                  : tradingTasksApi;
              try {
                await api.updateExecutionNotes(
                  taskId,
                  notesTarget.id,
                  notesValue
                );
                setNotesDialogOpen(false);
                setNotesTarget(null);
                void refresh();
              } catch {
                // error handled by API layer
              }
            }}
          >
            {t('actions.ok')}
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog
        open={revisionTarget !== null}
        onClose={() => setRevisionTarget(null)}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>{t('tables.executions.configRevisionsTitle')}</DialogTitle>
        <DialogContent>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            {t('tables.executions.executionSegment', {
              execution: revisionTarget?.execution_number ?? '-',
              segment: revisionTarget?.segment_index ?? 1,
            })}
          </Typography>
          <Box sx={{ display: 'grid', gap: 1.5 }}>
            <Typography variant="body2">
              {t('tables.executions.configRevisions')}:{' '}
              <Box component="span" sx={{ fontFamily: 'monospace' }}>
                {revisionTarget?.configuration_revision ??
                  getStrategyConfigSnapshotRevision(
                    revisionTarget?.strategy_config
                  ) ??
                  '-'}
              </Box>
            </Typography>
            <Typography variant="body2">
              {t('tables.executions.currentConfigHash')}:{' '}
              <Box component="span" sx={{ fontFamily: 'monospace' }}>
                {revisionTarget?.configuration_hash ??
                  getStrategyConfigSnapshotHash(
                    revisionTarget?.strategy_config
                  ) ??
                  '-'}
              </Box>
            </Typography>
            <Typography variant="body2">
              {t('tables.executions.strategy')}:{' '}
              {revisionTarget?.strategy_config?.current?.name ??
                revisionTarget?.strategy_config?.name ??
                '-'}
            </Typography>
            <Box>
              <Typography variant="subtitle2" sx={{ mb: 1 }}>
                {t('tables.executions.revisionHistory')}
              </Typography>
              {revisionTarget?.strategy_config?.revisions?.length ? (
                revisionTarget.strategy_config.revisions.map(
                  (revision, index) => (
                    <Paper
                      key={`${revision.from_hash ?? index}-${revision.to_hash ?? index}`}
                      variant="outlined"
                      sx={{ p: 1.5, mb: 1 }}
                    >
                      <Typography
                        variant="body2"
                        sx={{ fontFamily: 'monospace' }}
                      >
                        {String(revision.from_hash ?? '-')} {'->'}{' '}
                        {String(revision.to_hash ?? '-')}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        {t('tables.executions.changedFields')}:{' '}
                        {Array.isArray(revision.changed_fields)
                          ? revision.changed_fields.join(', ')
                          : '-'}
                      </Typography>
                    </Paper>
                  )
                )
              ) : (
                <Typography variant="body2" color="text.secondary">
                  {t('tables.executions.noConfigRevisions')}
                </Typography>
              )}
            </Box>
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setRevisionTarget(null)}>
            {t('actions.close', 'Close')}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
