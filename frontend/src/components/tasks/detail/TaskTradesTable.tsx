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
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  type SelectChangeEvent,
} from '@mui/material';
import {
  Settings as SettingsIcon,
  Search as SearchIcon,
  Clear as ClearIcon,
} from '@mui/icons-material';
import DataTable, { type Column } from '../../common/DataTable';
import { TableSelectionToolbar } from '../../common/TableSelectionToolbar';
import { useTableRowSelection } from '../../../hooks/useTableRowSelection';
import {
  useTaskTrades,
  type TaskTrade,
  type TaskTradeKindFilter,
} from '../../../hooks/useTaskTrades';
import type { TaskType } from '../../../types/common';
import { ColumnConfigDialog } from '../../common/ColumnConfigDialog';
import {
  useColumnConfig,
  columnsToDefaults,
  applyColumnConfig,
} from '../../../hooks/useColumnConfig';
import { buildCopyHandler } from '../../../utils/tableCopyUtils';
import {
  currencySymbol,
  formatAppNumber,
  formatMoneyAmount,
} from '../../../utils/numberFormat';
import { useDateTimeFormatter } from '../../../hooks/useDateTimeFormatter';
import { DateRangeFilter } from '../../common/DateRangeFilter';
import { TableFilterBar } from '../../common/TableFilterBar';
import {
  tableFilterDateRangeSx,
  tableFilterFieldSx,
} from '../../common/tableFilterLayout';

const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

interface TaskTradesTableProps {
  taskId: string | number;
  taskType: TaskType;
  executionRunId?: string;
  enableRealTimeUpdates?: boolean;
  pipSize?: number | null;
  strategyType?: string;
}

type SortOrder = 'asc' | 'desc';

const toOrdering = (field: string, order: SortOrder): string =>
  order === 'desc' ? `-${field}` : field;

export const TaskTradesTable: React.FC<TaskTradesTableProps> = ({
  taskId,
  taskType,
  executionRunId,
  enableRealTimeUpdates = false,
  pipSize,
  strategyType,
}) => {
  const { t } = useTranslation('common');
  const { formatDateTime } = useDateTimeFormatter({
    includeSeconds: true,
    includeTimezone: true,
  });
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(50);
  const [sortField, setSortField] = useState('timestamp');
  const [sortOrder, setSortOrder] = useState<SortOrder>('desc');
  const [isReloading, setIsReloading] = useState(false);
  const [cycleIdFilter, setCycleIdFilter] = useState('');
  const hasCycleIdFilter = cycleIdFilter.trim().length > 0;
  const isCycleIdFilterValid =
    !hasCycleIdFilter || UUID_PATTERN.test(cycleIdFilter.trim());
  const effectiveCycleId = isCycleIdFilterValid ? cycleIdFilter.trim() : '';

  // Trade ID filter (prefix match on UUID — accept 4+ hex characters/dashes).
  const [tradeIdFilter, setTradeIdFilter] = useState('');
  const hasTradeIdFilter = tradeIdFilter.trim().length > 0;
  const TRADE_ID_PREFIX_PATTERN = /^[0-9a-f-]{4,}$/i;
  const isTradeIdFilterValid =
    !hasTradeIdFilter || TRADE_ID_PREFIX_PATTERN.test(tradeIdFilter.trim());
  const effectiveTradeId =
    hasTradeIdFilter && isTradeIdFilterValid ? tradeIdFilter.trim() : '';

  // --- Date range filter ---
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [tradeKind, setTradeKind] = useState<TaskTradeKindFilter>('all');

  const handleTradeKindChange = (
    event: SelectChangeEvent<TaskTradeKindFilter>
  ) => {
    setTradeKind(event.target.value as TaskTradeKindFilter);
    setPage(0);
  };

  const { trades, totalCount, isLoading, error, refresh } = useTaskTrades({
    taskId,
    taskType,
    executionRunId,
    page: page + 1,
    pageSize: rowsPerPage,
    cycleId: effectiveCycleId || undefined,
    tradeId: effectiveTradeId || undefined,
    tradeKind,
    ordering: toOrdering(sortField, sortOrder),
    timestampFrom: dateFrom ? new Date(dateFrom).toISOString() : undefined,
    timestampTo: dateTo ? new Date(dateTo).toISOString() : undefined,
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

  const handleSortChange = useCallback((field: string, order: SortOrder) => {
    setSortField(field);
    setSortOrder(order);
    setPage(0);
  }, []);

  const formatTimestamp = useCallback(
    (timestamp: string): string => formatDateTime(timestamp),
    [formatDateTime]
  );

  const formatPrice = useCallback(
    (value: string | number | null | undefined, digits = 5): string => {
      if (value == null || value === '') return '-';
      const numericValue =
        typeof value === 'string' ? parseFloat(value) : Number(value);
      if (!Number.isFinite(numericValue)) return '-';
      return formatAppNumber(numericValue, {
        minimumFractionDigits: digits,
        maximumFractionDigits: digits,
        useGrouping: false,
      });
    },
    []
  );

  const formatCurrencyPrefix = useCallback(
    (currency?: string | null): string => {
      const symbol = currency ? currencySymbol(currency) : '';
      return symbol.length > 2 ? `${symbol} ` : symbol;
    },
    []
  );

  const formatSignedMoney = useCallback(
    (value: number, currency?: string | null): string =>
      formatMoneyAmount(value, currency, {
        minimumFractionDigits: 0,
        maximumFractionDigits: 0,
        signed: true,
      }),
    []
  );

  const formatPriceWithCurrency = useCallback(
    (
      value: string | number | null | undefined,
      currency?: string | null,
      digits = 5
    ): string => {
      const formatted = formatPrice(value, digits);
      return formatted === '-'
        ? formatted
        : `${formatCurrencyPrefix(currency)}${formatted}`;
    },
    [formatCurrencyPrefix, formatPrice]
  );

  const columns: Column<TaskTrade>[] = [
    {
      id: 'id',
      label: t('tables.trades.tradeId'),
      width: 120,
      minWidth: 80,
      render: (row) => (row.id ? String(row.id).slice(0, 8) : '-'),
    },
    {
      id: 'replayed_at',
      label: 'Replay',
      width: 105,
      minWidth: 90,
      render: (row) =>
        row.replayed_at ? (
          <Tooltip title={`Replayed at ${formatTimestamp(row.replayed_at)}`}>
            <Chip
              label="REPLAY"
              size="small"
              color="warning"
              variant="filled"
            />
          </Tooltip>
        ) : (
          '-'
        ),
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
        const methodKey = row.execution_method || '';
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
      render: (row) =>
        row.units != null ? formatAppNumber(Number(row.units)) : '-',
    },
    {
      id: 'price',
      label: t('tables.trades.price'),
      width: 120,
      minWidth: 120,
      align: 'right',
      render: (row: TaskTrade) =>
        formatPriceWithCurrency(row.price, row.price_currency, 5),
    },
    {
      id: 'pnl',
      label: t('tables.trades.pnl', { defaultValue: 'PnL' }),
      width: 120,
      minWidth: 90,
      align: 'right',
      render: (row: TaskTrade) => {
        if (row.pnl == null || row.pnl === '') return '-';
        const value = parseFloat(row.pnl);
        if (!Number.isFinite(value)) return '-';
        return (
          <Typography
            variant="body2"
            color={value >= 0 ? 'success.main' : 'error.main'}
            fontWeight="bold"
          >
            {formatSignedMoney(value, row.price_currency)}
          </Typography>
        );
      },
    },
    {
      id: 'pips',
      label: t('tables.trades.pips', { defaultValue: 'Pips' }),
      width: 90,
      minWidth: 70,
      align: 'right',
      render: (row: TaskTrade) => {
        if (!pipSize || !row.entry_price || !row.price) return '-';
        const isClose =
          row.execution_method !== 'open_position' &&
          row.execution_method !== 'rebuild_position';
        if (!isClose) return '-';
        const entry = parseFloat(row.entry_price);
        const exit = parseFloat(row.price);
        if (!Number.isFinite(entry) || !Number.isFinite(exit)) return '-';
        const dir = row.direction ? String(row.direction).toLowerCase() : '';
        const pips =
          dir === 'long' ? (exit - entry) / pipSize : (entry - exit) / pipSize;
        if (!Number.isFinite(pips)) return '-';
        return (
          <Typography
            variant="body2"
            color={pips >= 0 ? 'success.main' : 'error.main'}
            fontWeight="bold"
          >
            {formatAppNumber(pips, {
              minimumFractionDigits: 1,
              maximumFractionDigits: 1,
              signed: true,
            })}
          </Typography>
        );
      },
    },
    {
      id: 'order_id',
      label: 'Order',
      width: 140,
      minWidth: 110,
      render: (row: TaskTrade) =>
        row.order_id ? (
          <Typography variant="body2" fontFamily="monospace">
            {row.order_id}
          </Typography>
        ) : (
          '-'
        ),
    },
    {
      id: 'oanda_trade_id',
      label: 'OANDA Trade',
      width: 150,
      minWidth: 120,
      render: (row: TaskTrade) =>
        row.oanda_trade_id ? (
          <Typography variant="body2" fontFamily="monospace">
            {row.oanda_trade_id}
          </Typography>
        ) : (
          '-'
        ),
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
      width: 400,
      minWidth: 240,
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
          ? formatPriceWithCurrency(row.stop_loss_price, row.price_currency, 3)
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
  const isSnowballStrategy = strategyType === 'snowball';
  const snowballOnlyColumnIds = ['layer_index', 'retracement_count'];
  const defaultColItems = columnsToDefaults(columns).map((c) =>
    [
      'stop_loss_price',
      'is_rebuild',
      'replayed_at',
      'order_id',
      'oanda_trade_id',
      ...(!isSnowballStrategy ? snowballOnlyColumnIds : []),
    ].includes(c.id)
      ? { ...c, visible: false }
      : c
  );
  const {
    columns: colConfig,
    updateColumns,
    resetToDefaults,
  } = useColumnConfig(
    isSnowballStrategy ? 'task_trades' : 'task_trades_generic',
    defaultColItems
  );
  const visibleColumns = applyColumnConfig(columns, colConfig);

  const handleCopy = useCallback(() => {
    const tradesMap = new Map(trades.map((tr) => [String(tr.id), tr]));
    const extractors: Record<string, (r: TaskTrade) => string> = {
      id: (r) => (r.id ? String(r.id).slice(0, 8) : '-'),
      timestamp: (r) => (r.timestamp ? formatTimestamp(r.timestamp) : '-'),
      instrument: (r) => r.instrument ?? '-',
      execution_method: (r) => {
        const methodKey = r.execution_method || '';
        const i18nLabel = t(`tables.trades.executionMethod.${methodKey}`, {
          defaultValue: '',
        });
        return (
          i18nLabel || r.execution_method_display || r.execution_method || '-'
        );
      },
      direction: (r) => String(r.direction ?? '').toUpperCase(),
      replayed_at: (r) =>
        r.replayed_at ? formatTimestamp(r.replayed_at) : '-',
      units: (r) => (r.units != null ? formatAppNumber(Number(r.units)) : '-'),
      price: (r) => formatPriceWithCurrency(r.price, r.price_currency, 5),
      pnl: (r) => {
        if (r.pnl == null || r.pnl === '') return '-';
        const value = parseFloat(r.pnl);
        if (!Number.isFinite(value)) return '-';
        return formatSignedMoney(value, r.price_currency);
      },
      pips: (r) => {
        if (!pipSize || !r.entry_price || !r.price) return '-';
        const isClose =
          r.execution_method !== 'open_position' &&
          r.execution_method !== 'rebuild_position';
        if (!isClose) return '-';
        const entry = parseFloat(r.entry_price);
        const exit = parseFloat(r.price);
        if (!Number.isFinite(entry) || !Number.isFinite(exit)) return '-';
        const dir = r.direction ? String(r.direction).toLowerCase() : '';
        const pips =
          dir === 'long' ? (exit - entry) / pipSize : (entry - exit) / pipSize;
        if (!Number.isFinite(pips)) return '-';
        return formatAppNumber(pips, {
          minimumFractionDigits: 1,
          maximumFractionDigits: 1,
          signed: true,
        });
      },
      order_id: (r) => r.order_id ?? '-',
      oanda_trade_id: (r) => r.oanda_trade_id ?? '-',
      layer_index: (r) => (r.layer_index != null ? String(r.layer_index) : '-'),
      retracement_count: (r) =>
        r.retracement_count != null ? String(r.retracement_count) : '-',
      description: (r) => r.description || '-',
      stop_loss_price: (r) =>
        r.stop_loss_price
          ? formatPriceWithCurrency(r.stop_loss_price, r.price_currency, 3)
          : '-',
      is_rebuild: (r) => (r.is_rebuild ? 'Yes' : '-'),
    };
    const { headers, formatRow } = buildCopyHandler(
      visibleColumns,
      extractors,
      tradesMap
    );
    selection.copySelectedRows(headers, formatRow, pageRowIds);
  }, [
    formatPriceWithCurrency,
    formatSignedMoney,
    formatTimestamp,
    pageRowIds,
    pipSize,
    selection,
    t,
    trades,
    visibleColumns,
  ]);

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
          mb: 1,
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          gap: 1,
          flexWrap: 'wrap',
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
      <TableFilterBar>
        <FormControl
          size="small"
          sx={{ flex: { xs: '1 1 100%', sm: '0 1 180px' }, minWidth: 0 }}
        >
          <InputLabel>{t('tables.trades.tradeKindFilter')}</InputLabel>
          <Select<TaskTradeKindFilter>
            value={tradeKind}
            label={t('tables.trades.tradeKindFilter')}
            onChange={handleTradeKindChange}
          >
            <MenuItem value="all">{t('tables.trades.tradeKindAll')}</MenuItem>
            <MenuItem value="order">
              {t('tables.trades.tradeKindOrder')}
            </MenuItem>
            <MenuItem value="close">
              {t('tables.trades.tradeKindClose')}
            </MenuItem>
          </Select>
        </FormControl>
        <TextField
          size="small"
          placeholder={t('tables.trades.cycleIdFilter')}
          value={cycleIdFilter}
          onChange={(e) => setCycleIdFilter(e.target.value)}
          error={hasCycleIdFilter && !isCycleIdFilterValid}
          helperText={
            hasCycleIdFilter && !isCycleIdFilterValid
              ? t('tables.trades.invalidCycleId')
              : undefined
          }
          sx={tableFilterFieldSx}
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
        <TextField
          size="small"
          placeholder={t('tables.trades.tradeIdFilter')}
          value={tradeIdFilter}
          onChange={(e) => {
            setTradeIdFilter(e.target.value);
            setPage(0);
          }}
          error={hasTradeIdFilter && !isTradeIdFilterValid}
          helperText={
            hasTradeIdFilter && !isTradeIdFilterValid
              ? t('tables.trades.invalidTradeId')
              : undefined
          }
          sx={tableFilterFieldSx}
          slotProps={{
            input: {
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon fontSize="small" />
                </InputAdornment>
              ),
              endAdornment: tradeIdFilter ? (
                <InputAdornment position="end">
                  <IconButton
                    size="small"
                    onClick={() => setTradeIdFilter('')}
                    edge="end"
                  >
                    <ClearIcon fontSize="small" />
                  </IconButton>
                </InputAdornment>
              ) : null,
            },
          }}
        />
        <DateRangeFilter
          from={dateFrom}
          to={dateTo}
          onFromChange={(v) => {
            setDateFrom(v);
            setPage(0);
          }}
          onToChange={(v) => {
            setDateTo(v);
            setPage(0);
          }}
          sx={tableFilterDateRangeSx}
        />
      </TableFilterBar>

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
        sortMode="server"
        orderBy={sortField}
        order={sortOrder}
        onSortChange={handleSortChange}
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
