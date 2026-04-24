import { useMemo, useState, useCallback } from 'react';
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Checkbox,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  FormControlLabel,
  IconButton,
  InputLabel,
  MenuItem,
  Select,
  TablePagination,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Tooltip,
  Typography,
} from '@mui/material';
import {
  Code as CodeIcon,
  Settings as SettingsIcon,
  Add as AddIcon,
  Close as CloseIcon,
  Refresh as RefreshIcon,
} from '@mui/icons-material';
import { useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAccount } from '../hooks/useAccounts';
import { useToast } from '../components/common/useToast';
import { Breadcrumbs, PageContainer } from '../components/common';
import DataTable, { type Column } from '../components/common/DataTable';
import { TableSelectionToolbar } from '../components/common/TableSelectionToolbar';
import { useTableRowSelection } from '../hooks/useTableRowSelection';
import { ColumnConfigDialog } from '../components/common/ColumnConfigDialog';
import {
  useColumnConfig,
  columnsToDefaults,
  applyColumnConfig,
} from '../hooks/useColumnConfig';
import { buildCopyHandler } from '../utils/tableCopyUtils';
import {
  oandaMarketApi,
  type OandaPosition,
  type OandaOrder,
} from '../services/api/oandaMarket';
import { marketApi } from '../services/api/market';
import { useSupportedInstruments } from '../hooks/useMarketConfig';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { formatAppNumber } from '../utils/numberFormat';
import { formatDateTimeInTimezone } from '../utils/timezone';

const DEFAULT_CURRENCY = 'USD';

const resolveCurrency = (c?: string | null) => {
  if (!c) return DEFAULT_CURRENCY;
  const t = c.trim().toUpperCase();
  return t.length === 3 ? t : DEFAULT_CURRENCY;
};

const resolveQuoteCurrency = (instrument?: string | null) => {
  if (!instrument || !instrument.includes('_')) return null;
  const [, quoteCurrency] = instrument.split('_');
  const normalized = quoteCurrency?.trim().toUpperCase();
  return normalized && normalized.length === 3 ? normalized : null;
};

const fmtBal = (v: string | number | null | undefined, cur?: string) => {
  if (v == null) return '\u2014';
  const n = typeof v === 'string' ? Number(v) : v;
  if (Number.isNaN(n)) return '\u2014';
  const code = resolveCurrency(cur);
  try {
    return `${code} ${formatAppNumber(n, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })}`;
  } catch {
    return `${code} ${formatAppNumber(n, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })}`;
  }
};

const fmtQuoteValue = (
  value: string | number | null | undefined,
  instrument?: string | null
) => {
  if (value == null) return '\u2014';
  const n = typeof value === 'string' ? Number(value) : value;
  if (Number.isNaN(n)) return '\u2014';
  const currency = resolveQuoteCurrency(instrument);
  const formatted = formatAppNumber(n, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  return currency ? `${formatted} ${currency}` : formatted;
};

const fmtSignedQuoteValue = (
  value: string | number | null | undefined,
  instrument?: string | null
) => {
  if (value == null) return '\u2014';
  const n = typeof value === 'string' ? Number(value) : value;
  if (Number.isNaN(n)) return '\u2014';
  const sign = n >= 0 ? '+' : '';
  return `${sign}${fmtQuoteValue(n, instrument)}`;
};

const fmtJson = (v: unknown) => {
  if (v == null) return '\u2014';
  try {
    return JSON.stringify(v, null, 2);
  } catch {
    return String(v);
  }
};

const fmtTs = (ts: string | null): string => {
  if (!ts) return '\u2014';
  return formatDateTimeInTimezone(ts, 'UTC', undefined, {
    includeSeconds: true,
    includeTimezone: true,
  });
};

// --- Positions Table ---

function PositionsTable({ accountDbId }: { accountDbId: number }) {
  const { t } = useTranslation(['common', 'settings']);
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();
  const { instruments } = useSupportedInstruments();
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(25);
  const [isReloading, setIsReloading] = useState(false);
  const [colConfigOpen, setColConfigOpen] = useState(false);
  const [positionStatusFilter, setPositionStatusFilter] = useState<
    'open' | 'all'
  >('open');
  const [closeDialogOpen, setCloseDialogOpen] = useState(false);
  const [positionToClose, setPositionToClose] = useState<OandaPosition | null>(
    null
  );
  const [closeUnits, setCloseUnits] = useState('');
  const [closing, setClosing] = useState(false);
  const [closingSelected, setClosingSelected] = useState(false);
  const [openDialogOpen, setOpenDialogOpen] = useState(false);
  const [openForm, setOpenForm] = useState({
    orderType: 'market' as 'market' | 'limit' | 'stop',
    instrument: 'USD_JPY',
    direction: 'long' as 'long' | 'short',
    units: '1000',
    tpEnabled: false,
    take_profit: '',
    slEnabled: false,
    stop_loss: '',
  });
  const [opening, setOpening] = useState(false);

  const {
    data: positionsData,
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: [
      'oanda-positions',
      accountDbId,
      positionStatusFilter,
      page,
      rowsPerPage,
    ],
    queryFn: () =>
      oandaMarketApi.getPositions({
        account_id: accountDbId,
        status: positionStatusFilter,
        page: page + 1,
        page_size: rowsPerPage,
      }),
    refetchInterval: 15000,
  });

  const positions = positionsData?.results ?? [];
  const totalCount = positionsData?.count ?? 0;
  const selection = useTableRowSelection();
  const getRowId = useCallback((row: OandaPosition) => row.id, []);
  const pageRowIds = positions.map((r) => r.id);

  const handleToggleAll = () => {
    if (selection.isAllPageSelected(pageRowIds))
      selection.deselectAllOnPage(pageRowIds);
    else selection.selectAllOnPage(pageRowIds);
  };

  const handleReload = useCallback(async () => {
    setIsReloading(true);
    await refetch();
    setIsReloading(false);
  }, [refetch]);

  const columns: Column<OandaPosition>[] = [
    {
      id: 'id',
      label: t('common:tables.positions.positionId'),
      width: 100,
      minWidth: 80,
    },
    {
      id: 'instrument',
      label: t('common:tables.positions.instrument'),
      width: 120,
      minWidth: 100,
    },
    {
      id: 'direction',
      label: t('common:tables.positions.direction'),
      width: 80,
      render: (row) => (
        <Chip
          label={row.direction.toUpperCase()}
          color={row.direction === 'long' ? 'success' : 'error'}
          size="small"
        />
      ),
    },
    {
      id: 'units',
      label: t('common:tables.positions.units'),
      width: 100,
      align: 'right',
    },
    {
      id: 'entry_price',
      label: t('common:tables.positions.openPrice'),
      width: 120,
      align: 'right',
      render: (row) => <>{fmtQuoteValue(row.entry_price, row.instrument)}</>,
    },
    {
      id: 'unrealized_pnl',
      label: t('common:tables.positions.unrealizedPnl'),
      width: 130,
      align: 'right',
      render: (row) => {
        const pnl = parseFloat(row.unrealized_pnl);
        return (
          <Typography
            variant="body2"
            sx={{
              color: pnl >= 0 ? 'success.main' : 'error.main',
              fontWeight: 500,
            }}
          >
            {fmtSignedQuoteValue(row.unrealized_pnl, row.instrument)}
          </Typography>
        );
      },
    },
    {
      id: 'open_time',
      label: t('common:tables.positions.openTimestamp'),
      width: 180,
      render: (row) => fmtTs(row.open_time),
    },
    {
      id: 'close_time' as keyof OandaPosition,
      label: t('common:tables.positions.closeTimestamp'),
      width: 180,
      render: (row) => fmtTs(row.close_time ?? null),
    },
    { id: 'state', label: t('common:tables.positions.status'), width: 80 },
    {
      id: 'actions' as keyof OandaPosition,
      label: '',
      width: 60,
      sortable: false,
      render: (row) =>
        row.status === 'open' ? (
          <Tooltip title={t('common:actions.closePosition')}>
            <IconButton
              size="small"
              color="error"
              onClick={(e) => {
                e.stopPropagation();
                setPositionToClose(row);
                setCloseUnits('');
                setCloseDialogOpen(true);
              }}
            >
              <CloseIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        ) : null,
    },
  ];

  const colDefaults = columnsToDefaults(columns);
  const {
    columns: colConfig,
    updateColumns,
    resetToDefaults,
  } = useColumnConfig('oanda_positions', colDefaults);
  const visibleColumns = applyColumnConfig(columns, colConfig);

  const extractors = {
    id: (r: OandaPosition) => r.id,
    instrument: (r: OandaPosition) => r.instrument,
    direction: (r: OandaPosition) => r.direction,
    units: (r: OandaPosition) => r.units,
    entry_price: (r: OandaPosition) =>
      fmtQuoteValue(r.entry_price, r.instrument),
    unrealized_pnl: (r: OandaPosition) =>
      fmtSignedQuoteValue(r.unrealized_pnl, r.instrument),
    open_time: (r: OandaPosition) => r.open_time ?? '',
    close_time: (r: OandaPosition) => r.close_time ?? '',
    state: (r: OandaPosition) => r.state,
  };
  const dataMap = new Map(positions.map((r) => [getRowId(r), r]));
  const copyData = buildCopyHandler(
    visibleColumns.filter((c) => c.id !== 'actions'),
    extractors,
    dataMap
  );
  const handleCopy = () => {
    selection.copySelectedRows(
      copyData.headers,
      copyData.formatRow,
      pageRowIds
    );
  };

  const handleClosePosition = async () => {
    if (!positionToClose) return;
    setClosing(true);
    try {
      const units = closeUnits.trim() ? parseFloat(closeUnits) : undefined;
      await oandaMarketApi.closePosition(positionToClose.id, {
        account_id: accountDbId,
        units,
      });
      showSuccess(t('common:actions.closePosition') + ' OK');
      setCloseDialogOpen(false);
      setPositionToClose(null);
      queryClient.invalidateQueries({
        queryKey: ['oanda-positions', accountDbId],
      });
    } catch {
      showError(t('common:errors.unexpectedError'));
    } finally {
      setClosing(false);
    }
  };

  const handleCloseSelected = async () => {
    const ids = [...selection.selectedRowIds].filter(
      (id) => dataMap.get(id)?.status === 'open'
    );
    if (ids.length === 0) return;
    setClosingSelected(true);
    let ok = 0;
    for (const id of ids) {
      try {
        await oandaMarketApi.closePosition(id, { account_id: accountDbId });
        ok++;
      } catch {
        /* continue */
      }
    }
    if (ok > 0) {
      showSuccess(`${ok} position(s) closed`);
      selection.resetSelection();
      queryClient.invalidateQueries({
        queryKey: ['oanda-positions', accountDbId],
      });
    }
    if (ok < ids.length) showError(`${ids.length - ok} position(s) failed`);
    setClosingSelected(false);
  };

  const handleOpenPosition = async () => {
    if (!openForm.instrument || !openForm.units) return;
    setOpening(true);
    try {
      await oandaMarketApi.openPosition({
        account_id: accountDbId,
        instrument: openForm.instrument,
        direction: openForm.direction,
        units: parseFloat(openForm.units),
        take_profit:
          openForm.tpEnabled && openForm.take_profit
            ? parseFloat(openForm.take_profit)
            : undefined,
        stop_loss:
          openForm.slEnabled && openForm.stop_loss
            ? parseFloat(openForm.stop_loss)
            : undefined,
      });
      showSuccess(t('common:actions.add') + ' OK');
      setOpenDialogOpen(false);
      queryClient.invalidateQueries({
        queryKey: ['oanda-positions', accountDbId],
      });
    } catch {
      showError(t('common:errors.unexpectedError'));
    } finally {
      setOpening(false);
    }
  };

  return (
    <Box>
      <Box
        display="flex"
        justifyContent="space-between"
        alignItems="center"
        mb={1}
        gap={1}
        flexWrap="wrap"
      >
        <Typography variant="subtitle1">
          {positionStatusFilter === 'open'
            ? t('common:tables.positions.openPositions')
            : t('common:tables.positions.allPositions')}{' '}
          ({totalCount})
        </Typography>
        <Box display="flex" alignItems="center" gap={0.5} flexWrap="wrap">
          <Button
            size="small"
            variant="outlined"
            startIcon={<AddIcon />}
            onClick={() => setOpenDialogOpen(true)}
          >
            {t('common:actions.add')}
          </Button>
          <Button
            size="small"
            variant="outlined"
            color="error"
            startIcon={<CloseIcon />}
            onClick={handleCloseSelected}
            disabled={
              selection.selectedRowIds.size === 0 ||
              closingSelected ||
              positionStatusFilter !== 'open'
            }
          >
            {closingSelected ? (
              <CircularProgress size={16} />
            ) : (
              t('common:actions.closePosition')
            )}
          </Button>
        </Box>
      </Box>
      <Box
        display="flex"
        justifyContent="flex-end"
        alignItems="center"
        gap={0.5}
        flexWrap="wrap"
        mb={1}
      >
        <ToggleButtonGroup
          size="small"
          exclusive
          value={positionStatusFilter}
          onChange={(_event, value: 'open' | 'all' | null) => {
            if (!value) return;
            setPositionStatusFilter(value);
            setPage(0);
            selection.resetSelection();
          }}
        >
          <ToggleButton value="open">
            {t('common:tables.positions.open')}
          </ToggleButton>
          <ToggleButton value="all">
            {t('common:tables.positions.allPositions')}
          </ToggleButton>
        </ToggleButtonGroup>
        <TableSelectionToolbar
          selectedCount={selection.selectedRowIds.size}
          onCopy={handleCopy}
          onSelectAll={handleToggleAll}
          onReset={selection.resetSelection}
          onReload={handleReload}
          isReloading={isReloading}
        />
        <Tooltip title={t('common:columnConfig.configureColumns')}>
          <IconButton onClick={() => setColConfigOpen(true)}>
            <SettingsIcon fontSize="small" />
          </IconButton>
        </Tooltip>
      </Box>

      <DataTable
        columns={visibleColumns}
        data={positions}
        isLoading={isLoading}
        error={error instanceof Error ? error : null}
        hidePagination
        selectable
        getRowId={getRowId}
        selectedRowIds={selection.selectedRowIds}
        onToggleRow={selection.toggleRowSelection}
        allPageSelected={selection.isAllPageSelected(pageRowIds)}
        indeterminate={selection.isIndeterminate(pageRowIds)}
        onToggleAll={handleToggleAll}
        emptyMessage={t('common:tables.positions.noPositions')}
        storageKey="oanda_positions_table"
        fillEmptyRows
      />

      <TablePagination
        component="div"
        count={totalCount}
        page={page}
        onPageChange={(_, p) => setPage(p)}
        rowsPerPage={rowsPerPage}
        onRowsPerPageChange={(e) => {
          setRowsPerPage(parseInt(e.target.value, 10));
          setPage(0);
        }}
        rowsPerPageOptions={[10, 25, 50, 100]}
      />

      <ColumnConfigDialog
        open={colConfigOpen}
        onClose={() => setColConfigOpen(false)}
        columns={colConfig}
        onSave={updateColumns}
        onReset={resetToDefaults}
      />

      {/* Close Position Dialog */}
      <Dialog
        open={closeDialogOpen}
        onClose={() => setCloseDialogOpen(false)}
        maxWidth="xs"
        fullWidth
      >
        <DialogTitle>{t('common:actions.closePosition')} Position</DialogTitle>
        <DialogContent>
          {positionToClose && (
            <Box sx={{ pt: 1 }}>
              <Typography variant="body2" gutterBottom>
                {positionToClose.instrument}{' '}
                {positionToClose.direction.toUpperCase()}{' '}
                {positionToClose.units} units
              </Typography>
              <TextField
                fullWidth
                label="Units (blank = all)"
                value={closeUnits}
                onChange={(e) => setCloseUnits(e.target.value)}
                margin="normal"
                type="number"
              />
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCloseDialogOpen(false)} disabled={closing}>
            {t('common:actions.cancel')}
          </Button>
          <Button
            onClick={handleClosePosition}
            variant="contained"
            color="error"
            disabled={closing}
          >
            {closing ? (
              <CircularProgress size={20} />
            ) : (
              t('common:actions.closePosition')
            )}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Open Position Dialog */}
      <Dialog
        open={openDialogOpen}
        onClose={() => setOpenDialogOpen(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>{t('common:actions.add')} Position</DialogTitle>
        <DialogContent>
          <Box sx={{ pt: 1 }}>
            <FormControl fullWidth margin="normal">
              <InputLabel>{t('settings:accounts.orderType')}</InputLabel>
              <Select
                value={openForm.orderType}
                label={t('settings:accounts.orderType')}
                onChange={(e) =>
                  setOpenForm({
                    ...openForm,
                    orderType: e.target.value as 'market' | 'limit' | 'stop',
                  })
                }
              >
                <MenuItem value="market">
                  {t('settings:accounts.marketOrder')}
                </MenuItem>
                <MenuItem value="limit">
                  {t('settings:accounts.limitOrder')}
                </MenuItem>
                <MenuItem value="stop">
                  {t('settings:accounts.stopOrder')}
                </MenuItem>
              </Select>
            </FormControl>
            <FormControl fullWidth margin="normal">
              <InputLabel>{t('common:tables.positions.instrument')}</InputLabel>
              <Select
                value={openForm.instrument}
                label={t('common:tables.positions.instrument')}
                onChange={(e) =>
                  setOpenForm({ ...openForm, instrument: e.target.value })
                }
              >
                {instruments.map((inst) => (
                  <MenuItem key={inst} value={inst}>
                    {inst.replace('_', '/')}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <FormControl fullWidth margin="normal">
              <InputLabel>{t('common:tables.positions.direction')}</InputLabel>
              <Select
                value={openForm.direction}
                label={t('common:tables.positions.direction')}
                onChange={(e) =>
                  setOpenForm({
                    ...openForm,
                    direction: e.target.value as 'long' | 'short',
                  })
                }
              >
                <MenuItem value="long">
                  {t('common:tables.positions.long')}
                </MenuItem>
                <MenuItem value="short">
                  {t('common:tables.positions.short')}
                </MenuItem>
              </Select>
            </FormControl>
            <TextField
              fullWidth
              label={t('common:tables.positions.units')}
              value={openForm.units}
              onChange={(e) =>
                setOpenForm({ ...openForm, units: e.target.value })
              }
              margin="normal"
              type="number"
              required
            />
            <Box sx={{ mt: 1 }}>
              <FormControlLabel
                control={
                  <Checkbox
                    checked={openForm.tpEnabled}
                    onChange={(e) =>
                      setOpenForm({ ...openForm, tpEnabled: e.target.checked })
                    }
                  />
                }
                label={t('settings:accounts.enableTakeProfit')}
              />
              {openForm.tpEnabled && (
                <TextField
                  fullWidth
                  label="Take Profit"
                  value={openForm.take_profit}
                  onChange={(e) =>
                    setOpenForm({ ...openForm, take_profit: e.target.value })
                  }
                  margin="dense"
                  type="number"
                />
              )}
            </Box>
            <Box sx={{ mt: 1 }}>
              <FormControlLabel
                control={
                  <Checkbox
                    checked={openForm.slEnabled}
                    onChange={(e) =>
                      setOpenForm({ ...openForm, slEnabled: e.target.checked })
                    }
                  />
                }
                label={t('settings:accounts.enableStopLoss')}
              />
              {openForm.slEnabled && (
                <TextField
                  fullWidth
                  label="Stop Loss"
                  value={openForm.stop_loss}
                  onChange={(e) =>
                    setOpenForm({ ...openForm, stop_loss: e.target.value })
                  }
                  margin="dense"
                  type="number"
                />
              )}
            </Box>
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpenDialogOpen(false)} disabled={opening}>
            {t('common:actions.cancel')}
          </Button>
          <Button
            onClick={handleOpenPosition}
            variant="contained"
            color="primary"
            disabled={opening || !openForm.instrument || !openForm.units}
          >
            {opening ? <CircularProgress size={20} /> : t('common:actions.add')}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}

// --- Orders Table ---

function OrdersTable({ accountDbId }: { accountDbId: number }) {
  const { t } = useTranslation('common');
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(25);
  const [isReloading, setIsReloading] = useState(false);
  const [colConfigOpen, setColConfigOpen] = useState(false);
  const [orderStatusFilter, setOrderStatusFilter] = useState<'all' | 'pending'>(
    'all'
  );

  const {
    data: ordersData,
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: [
      'oanda-orders',
      accountDbId,
      orderStatusFilter,
      page,
      rowsPerPage,
    ],
    queryFn: () =>
      oandaMarketApi.getOrders({
        account_id: accountDbId,
        status: orderStatusFilter,
        page: page + 1,
        page_size: rowsPerPage,
      }),
    refetchInterval: 15000,
  });

  const orders = ordersData?.results ?? [];
  const totalCount = ordersData?.count ?? 0;
  const selection = useTableRowSelection();
  const getRowId = useCallback((row: OandaOrder) => row.id, []);
  const pageRowIds = orders.map((r) => r.id);

  const handleToggleAll = () => {
    if (selection.isAllPageSelected(pageRowIds))
      selection.deselectAllOnPage(pageRowIds);
    else selection.selectAllOnPage(pageRowIds);
  };

  const handleReload = useCallback(async () => {
    setIsReloading(true);
    await refetch();
    setIsReloading(false);
  }, [refetch]);

  const columns: Column<OandaOrder>[] = [
    { id: 'id', label: t('tables.orders.orderId'), width: 100, minWidth: 80 },
    { id: 'instrument', label: t('tables.orders.instrument'), width: 120 },
    { id: 'type', label: t('tables.orders.type'), width: 100 },
    {
      id: 'direction',
      label: t('tables.orders.direction'),
      width: 80,
      render: (row) => (
        <Chip
          label={row.direction.toUpperCase()}
          color={row.direction === 'long' ? 'success' : 'error'}
          size="small"
        />
      ),
    },
    {
      id: 'units',
      label: t('tables.orders.units'),
      width: 100,
      align: 'right',
    },
    {
      id: 'price',
      label: t('tables.orders.requestedPrice'),
      width: 120,
      align: 'right',
      render: (row) => <>{fmtQuoteValue(row.price, row.instrument)}</>,
    },
    { id: 'state', label: t('tables.orders.status'), width: 100 },
    { id: 'time_in_force', label: 'TIF', width: 60 },
    {
      id: 'create_time',
      label: t('tables.orders.timestamp'),
      width: 180,
      render: (row) => fmtTs(row.create_time),
    },
    {
      id: 'take_profit',
      label: 'TP',
      width: 100,
      align: 'right',
      render: (row) => <>{fmtQuoteValue(row.take_profit, row.instrument)}</>,
    },
    {
      id: 'stop_loss',
      label: 'SL',
      width: 100,
      align: 'right',
      render: (row) => <>{fmtQuoteValue(row.stop_loss, row.instrument)}</>,
    },
  ];

  const colDefaults = columnsToDefaults(columns);
  const {
    columns: colConfig,
    updateColumns,
    resetToDefaults,
  } = useColumnConfig('oanda_orders', colDefaults);
  const visibleColumns = applyColumnConfig(columns, colConfig);

  const extractors = {
    id: (r: OandaOrder) => r.id,
    instrument: (r: OandaOrder) => r.instrument,
    type: (r: OandaOrder) => r.type,
    direction: (r: OandaOrder) => r.direction,
    units: (r: OandaOrder) => r.units,
    state: (r: OandaOrder) => r.state,
    time_in_force: (r: OandaOrder) => r.time_in_force,
    create_time: (r: OandaOrder) => r.create_time ?? '',
    price: (r: OandaOrder) => fmtQuoteValue(r.price, r.instrument),
    take_profit: (r: OandaOrder) => fmtQuoteValue(r.take_profit, r.instrument),
    stop_loss: (r: OandaOrder) => fmtQuoteValue(r.stop_loss, r.instrument),
  };
  const dataMap = new Map(orders.map((r) => [getRowId(r), r]));
  const copyData = buildCopyHandler(visibleColumns, extractors, dataMap);
  const handleCopy = () => {
    selection.copySelectedRows(
      copyData.headers,
      copyData.formatRow,
      pageRowIds
    );
  };

  return (
    <Box>
      <Box
        display="flex"
        justifyContent="space-between"
        alignItems="center"
        mb={1}
        gap={1}
        flexWrap="wrap"
      >
        <Typography variant="subtitle1">
          {t('tables.orders.title')} ({totalCount})
        </Typography>
        <Box display="flex" alignItems="center" gap={0.5}>
          <ToggleButtonGroup
            size="small"
            exclusive
            value={orderStatusFilter}
            onChange={(_event, value: 'all' | 'pending' | null) => {
              if (!value) return;
              setOrderStatusFilter(value);
              setPage(0);
              selection.resetSelection();
            }}
          >
            <ToggleButton value="all">{t('actions.viewAll')}</ToggleButton>
            <ToggleButton value="pending">{t('status.pending')}</ToggleButton>
          </ToggleButtonGroup>
          <TableSelectionToolbar
            selectedCount={selection.selectedRowIds.size}
            onCopy={handleCopy}
            onSelectAll={handleToggleAll}
            onReset={selection.resetSelection}
            onReload={handleReload}
            isReloading={isReloading}
          />
          <Tooltip title={t('columnConfig.configureColumns')}>
            <IconButton onClick={() => setColConfigOpen(true)}>
              <SettingsIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </Box>
      </Box>
      <DataTable
        columns={visibleColumns}
        data={orders}
        isLoading={isLoading}
        error={error instanceof Error ? error : null}
        hidePagination
        selectable
        getRowId={getRowId}
        selectedRowIds={selection.selectedRowIds}
        onToggleRow={selection.toggleRowSelection}
        allPageSelected={selection.isAllPageSelected(pageRowIds)}
        indeterminate={selection.isIndeterminate(pageRowIds)}
        onToggleAll={handleToggleAll}
        emptyMessage={t('tables.orders.noOrders')}
        storageKey="oanda_orders_table"
        fillEmptyRows
      />
      <TablePagination
        component="div"
        count={totalCount}
        page={page}
        onPageChange={(_, p) => setPage(p)}
        rowsPerPage={rowsPerPage}
        onRowsPerPageChange={(e) => {
          setRowsPerPage(parseInt(e.target.value, 10));
          setPage(0);
        }}
        rowsPerPageOptions={[10, 25, 50, 100]}
      />
      <ColumnConfigDialog
        open={colConfigOpen}
        onClose={() => setColConfigOpen(false)}
        columns={colConfig}
        onSave={updateColumns}
        onReset={resetToDefaults}
      />
    </Box>
  );
}

// --- Main Detail Page ---

export default function OandaAccountDetailPage() {
  const { t } = useTranslation(['settings', 'common']);
  const params = useParams();
  const queryClient = useQueryClient();
  const [rawDataOpen, setRawDataOpen] = useState(false);

  const containerSx = useMemo(() => ({ mt: 4, mb: 4 }), []);

  const accountId = useMemo(() => {
    const raw = params.id;
    const parsed = raw ? Number(raw) : NaN;
    return Number.isFinite(parsed) ? parsed : null;
  }, [params.id]);

  const {
    data: account = null,
    isLoading: loading,
    error: queryError,
  } = useAccount(accountId ?? 0, { enabled: accountId !== null });

  const { data: marketStatus } = useQuery({
    queryKey: ['market-status'],
    queryFn: () => marketApi.getMarketStatus(),
    refetchInterval: 60000,
  });

  const error =
    accountId === null
      ? 'Invalid account id'
      : queryError instanceof Error
        ? queryError.message
        : queryError
          ? t('common:errors.fetchFailed')
          : null;

  const handleReloadAll = () => {
    queryClient.invalidateQueries({ queryKey: ['accounts'] });
    if (accountId) {
      queryClient.invalidateQueries({ queryKey: ['accounts', accountId] });
      queryClient.invalidateQueries({
        queryKey: ['oanda-positions', accountId],
      });
      queryClient.invalidateQueries({ queryKey: ['oanda-orders', accountId] });
    }
  };

  if (loading) {
    return (
      <PageContainer sx={containerSx}>
        <Breadcrumbs />
        <Box display="flex" justifyContent="center" alignItems="center" py={4}>
          <CircularProgress />
          <Typography variant="body2" color="text.secondary" sx={{ ml: 2 }}>
            {t('settings:accounts.loadingAccountData')}
          </Typography>
        </Box>
      </PageContainer>
    );
  }

  if (error) {
    return (
      <PageContainer sx={containerSx}>
        <Breadcrumbs />
        <Alert severity="error">{error}</Alert>
      </PageContainer>
    );
  }

  if (!account) {
    return (
      <PageContainer sx={containerSx}>
        <Breadcrumbs />
        <Alert severity="info">{t('common:messages.noData')}</Alert>
      </PageContainer>
    );
  }

  return (
    <PageContainer sx={containerSx}>
      <Breadcrumbs />
      <Box mb={2}>
        <Typography variant="h5">
          {t('settings:accounts.accountDetails')}: {account.account_id}
        </Typography>
      </Box>
      <Box
        display="flex"
        alignItems="center"
        justifyContent={{ xs: 'flex-end', sm: 'flex-end' }}
        gap={1}
        flexWrap="wrap"
        mb={2}
      >
        {/* Market Status */}
        {marketStatus && (
          <Chip
            label={
              marketStatus.is_open
                ? t('settings:accounts.marketOpen')
                : t('settings:accounts.marketClosed')
            }
            color={marketStatus.is_open ? 'success' : 'default'}
            size="small"
          />
        )}
        <Tooltip title={t('common:actions.reload')}>
          <IconButton onClick={handleReloadAll}>
            <RefreshIcon />
          </IconButton>
        </Tooltip>
        <Button
          variant="outlined"
          startIcon={<CodeIcon />}
          onClick={() => setRawDataOpen(true)}
        >
          {t('settings:accounts.rawData')}
        </Button>
      </Box>

      {/* Account Summary */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Box display="flex" alignItems="center" gap={1} mb={2}>
            <Typography variant="h6">{account.account_id}</Typography>
            <Chip
              label={
                account.api_type === 'practice'
                  ? t('settings:accounts.practice')
                  : t('settings:accounts.live')
              }
              color={account.api_type === 'practice' ? 'default' : 'warning'}
              size="small"
            />
            {account.is_active && (
              <Chip label="Active" color="success" size="small" />
            )}
            {account.is_default && (
              <Chip
                label="Default"
                color="primary"
                variant="outlined"
                size="small"
              />
            )}
          </Box>
          <Box
            display="grid"
            gridTemplateColumns={{
              xs: '1fr',
              sm: 'repeat(2, 1fr)',
              md: 'repeat(4, 1fr)',
            }}
            gap={2}
          >
            <Box>
              <Typography variant="body2" color="text.secondary">
                {t('settings:accounts.balance')}
              </Typography>
              <Typography variant="h6">
                {fmtBal(account.balance, account.currency)}
              </Typography>
            </Box>
            <Box>
              <Typography variant="body2" color="text.secondary">
                {t('settings:accounts.nav')}
              </Typography>
              <Typography variant="h6">
                {fmtBal(account.nav ?? null, account.currency)}
              </Typography>
            </Box>
            <Box>
              <Typography variant="body2" color="text.secondary">
                {t('settings:accounts.unrealizedPnL')}
              </Typography>
              <Typography
                variant="h6"
                sx={{
                  color:
                    parseFloat(account.unrealized_pnl) >= 0
                      ? 'success.main'
                      : 'error.main',
                }}
              >
                {parseFloat(account.unrealized_pnl) >= 0 ? '+' : ''}
                {fmtBal(account.unrealized_pnl, account.currency)}
              </Typography>
            </Box>
            <Box>
              <Typography variant="body2" color="text.secondary">
                {t('settings:accounts.currency')}
              </Typography>
              <Typography variant="h6">{account.currency}</Typography>
            </Box>
            <Box>
              <Typography variant="body2" color="text.secondary">
                {t('settings:accounts.marginUsed')}
              </Typography>
              <Typography variant="body1">
                {fmtBal(account.margin_used, account.currency)}
              </Typography>
            </Box>
            <Box>
              <Typography variant="body2" color="text.secondary">
                {t('settings:accounts.marginAvailable')}
              </Typography>
              <Typography variant="body1">
                {fmtBal(account.margin_available, account.currency)}
              </Typography>
            </Box>
            <Box>
              <Typography variant="body2" color="text.secondary">
                {t('settings:accounts.openTrades')}
              </Typography>
              <Typography variant="body1">
                {account.open_trade_count ?? '\u2014'}
              </Typography>
            </Box>
            <Box>
              <Typography variant="body2" color="text.secondary">
                {t('settings:accounts.openPositions')}
              </Typography>
              <Typography variant="body1">
                {account.open_position_count ?? '\u2014'}
              </Typography>
            </Box>
            <Box>
              <Typography variant="body2" color="text.secondary">
                {t('settings:accounts.pendingOrders')}
              </Typography>
              <Typography variant="body1">
                {account.pending_order_count ?? '\u2014'}
              </Typography>
            </Box>
            <Box>
              <Typography variant="body2" color="text.secondary">
                {t('settings:accounts.positionMode')}
              </Typography>
              <Typography variant="body1">
                {account.position_mode ?? '\u2014'}
              </Typography>
            </Box>
            <Box>
              <Typography variant="body2" color="text.secondary">
                {t('settings:accounts.hedgingEnabled')}
              </Typography>
              <Typography variant="body1">
                {typeof account.hedging_enabled === 'boolean'
                  ? String(account.hedging_enabled)
                  : '\u2014'}
              </Typography>
            </Box>
          </Box>
        </CardContent>
      </Card>

      {/* Positions */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            {t('common:navigation.positions')}
          </Typography>
          <PositionsTable accountDbId={account.id} />
        </CardContent>
      </Card>

      {/* Orders */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            {t('common:navigation.orders')}
          </Typography>
          <OrdersTable accountDbId={account.id} />
        </CardContent>
      </Card>

      {/* RAW Data Dialog */}
      <Dialog
        open={rawDataOpen}
        onClose={() => setRawDataOpen(false)}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>{t('settings:accounts.rawData')}</DialogTitle>
        <DialogContent>
          <Typography
            variant="body2"
            component="pre"
            sx={{
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
              bgcolor: 'grey.100',
              p: 2,
              borderRadius: 1,
              maxHeight: '60vh',
              overflow: 'auto',
              fontFamily: 'monospace',
              fontSize: '0.8rem',
            }}
          >
            {fmtJson(account.oanda_account)}
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setRawDataOpen(false)}>
            {t('common:actions.close')}
          </Button>
        </DialogActions>
      </Dialog>
    </PageContainer>
  );
}
