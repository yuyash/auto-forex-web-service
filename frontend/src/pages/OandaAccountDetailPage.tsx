import { useMemo, useState, useCallback } from 'react';
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  CircularProgress,
  Container,
  Typography,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TablePagination,
  IconButton,
  Tooltip,
  Chip,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
} from '@mui/material';
import {
  Code as CodeIcon,
  Settings as SettingsIcon,
  Add as AddIcon,
  Close as CloseIcon,
} from '@mui/icons-material';
import { useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAccount } from '../hooks/useAccounts';
import { useToast } from '../components/common/useToast';
import { Breadcrumbs } from '../components/common';
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
import { useQuery, useQueryClient } from '@tanstack/react-query';

const DEFAULT_ACCOUNT_CURRENCY = 'USD';

const resolveCurrencyCode = (currency?: string | null) => {
  if (!currency) return DEFAULT_ACCOUNT_CURRENCY;
  const trimmed = currency.trim().toUpperCase();
  return trimmed.length === 3 ? trimmed : DEFAULT_ACCOUNT_CURRENCY;
};

const formatBalance = (
  balance: string | number | null | undefined,
  currency?: string
) => {
  if (balance == null) return '\u2014';
  const numericBalance =
    typeof balance === 'string' ? Number(balance) : balance;
  if (Number.isNaN(numericBalance)) return '\u2014';
  const currencyCode = resolveCurrencyCode(currency);
  try {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: currencyCode,
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(numericBalance);
  } catch {
    return `${currencyCode} ${numericBalance.toFixed(2)}`;
  }
};

const formatJson = (value: unknown) => {
  if (value == null) return '\u2014';
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
};

const formatTimestamp = (timestamp: string | null): string => {
  if (!timestamp) return '\u2014';
  return new Date(timestamp).toLocaleString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
};

// --- Positions Table ---

function PositionsTable({ accountDbId }: { accountDbId: number }) {
  const { t } = useTranslation('common');
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(25);
  const [isReloading, setIsReloading] = useState(false);
  const [colConfigOpen, setColConfigOpen] = useState(false);
  const [closeDialogOpen, setCloseDialogOpen] = useState(false);
  const [positionToClose, setPositionToClose] = useState<OandaPosition | null>(
    null
  );
  const [closeUnits, setCloseUnits] = useState('');
  const [closing, setClosing] = useState(false);
  const [closingSelected, setClosingSelected] = useState(false);
  const [openDialogOpen, setOpenDialogOpen] = useState(false);
  const [openForm, setOpenForm] = useState({
    instrument: '',
    direction: 'long' as 'long' | 'short',
    units: '',
    take_profit: '',
    stop_loss: '',
  });
  const [opening, setOpening] = useState(false);

  const {
    data: positionsData,
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: ['oanda-positions', accountDbId, page, rowsPerPage],
    queryFn: () =>
      oandaMarketApi.getPositions({
        account_id: accountDbId,
        status: 'open',
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
    if (selection.isAllPageSelected(pageRowIds)) {
      selection.deselectAllOnPage(pageRowIds);
    } else {
      selection.selectAllOnPage(pageRowIds);
    }
  };

  const handleReload = useCallback(async () => {
    setIsReloading(true);
    await refetch();
    setIsReloading(false);
  }, [refetch]);

  const columns: Column<OandaPosition>[] = [
    {
      id: 'id',
      label: t('tables.positions.positionId'),
      width: 100,
      minWidth: 80,
    },
    {
      id: 'instrument',
      label: t('tables.positions.instrument'),
      width: 120,
      minWidth: 100,
    },
    {
      id: 'direction',
      label: t('tables.positions.direction'),
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
      label: t('tables.positions.units'),
      width: 100,
      align: 'right',
    },
    {
      id: 'entry_price',
      label: t('tables.positions.openPrice'),
      width: 120,
      align: 'right',
    },
    {
      id: 'unrealized_pnl',
      label: t('tables.positions.unrealizedPnl'),
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
            {pnl >= 0 ? '+' : ''}
            {pnl.toFixed(2)}
          </Typography>
        );
      },
    },
    {
      id: 'open_time',
      label: t('tables.positions.openTimestamp'),
      width: 180,
      render: (row) => formatTimestamp(row.open_time),
    },
    { id: 'state', label: t('tables.positions.status'), width: 80 },
    {
      id: 'actions' as keyof OandaPosition,
      label: '',
      width: 60,
      sortable: false,
      render: (row) => (
        <Tooltip title={t('actions.close')}>
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
      ),
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
    entry_price: (r: OandaPosition) => r.entry_price,
    unrealized_pnl: (r: OandaPosition) => r.unrealized_pnl,
    open_time: (r: OandaPosition) => r.open_time ?? '',
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
      showSuccess(t('actions.close') + ' OK');
      setCloseDialogOpen(false);
      setPositionToClose(null);
      queryClient.invalidateQueries({
        queryKey: ['oanda-positions', accountDbId],
      });
    } catch {
      showError(t('errors.unexpectedError'));
    } finally {
      setClosing(false);
    }
  };

  const handleCloseSelected = async () => {
    const selectedIds = [...selection.selectedRowIds];
    if (selectedIds.length === 0) return;
    setClosingSelected(true);
    let successCount = 0;
    for (const id of selectedIds) {
      try {
        await oandaMarketApi.closePosition(id, {
          account_id: accountDbId,
        });
        successCount++;
      } catch {
        // continue closing remaining
      }
    }
    if (successCount > 0) {
      showSuccess(`${successCount} position(s) closed`);
      selection.resetSelection();
      queryClient.invalidateQueries({
        queryKey: ['oanda-positions', accountDbId],
      });
    }
    if (successCount < selectedIds.length) {
      showError(
        `${selectedIds.length - successCount} position(s) failed to close`
      );
    }
    setClosingSelected(false);
  };

  const handleOpenPosition = async () => {
    if (!openForm.instrument.trim() || !openForm.units.trim()) return;
    setOpening(true);
    try {
      await oandaMarketApi.openPosition({
        account_id: accountDbId,
        instrument: openForm.instrument.trim(),
        direction: openForm.direction,
        units: parseFloat(openForm.units),
        take_profit: openForm.take_profit
          ? parseFloat(openForm.take_profit)
          : undefined,
        stop_loss: openForm.stop_loss
          ? parseFloat(openForm.stop_loss)
          : undefined,
      });
      showSuccess(t('actions.add') + ' OK');
      setOpenDialogOpen(false);
      setOpenForm({
        instrument: '',
        direction: 'long',
        units: '',
        take_profit: '',
        stop_loss: '',
      });
      queryClient.invalidateQueries({
        queryKey: ['oanda-positions', accountDbId],
      });
    } catch {
      showError(t('errors.unexpectedError'));
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
      >
        <Typography variant="subtitle1">
          {t('tables.positions.openPositions')} ({totalCount})
        </Typography>
        <Box display="flex" alignItems="center" gap={0.5}>
          <Button
            size="small"
            variant="outlined"
            startIcon={<AddIcon />}
            onClick={() => setOpenDialogOpen(true)}
          >
            {t('actions.add')}
          </Button>
          <Button
            size="small"
            variant="outlined"
            color="error"
            startIcon={<CloseIcon />}
            onClick={handleCloseSelected}
            disabled={selection.selectedRowIds.size === 0 || closingSelected}
          >
            {closingSelected ? (
              <CircularProgress size={16} />
            ) : (
              t('actions.close')
            )}
          </Button>
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
        emptyMessage={t('tables.positions.noPositions')}
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
        <DialogTitle>{t('actions.close')} Position</DialogTitle>
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
            {t('actions.cancel')}
          </Button>
          <Button
            onClick={handleClosePosition}
            variant="contained"
            color="error"
            disabled={closing}
          >
            {closing ? <CircularProgress size={20} /> : t('actions.close')}
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
        <DialogTitle>{t('actions.add')} Position</DialogTitle>
        <DialogContent>
          <Box sx={{ pt: 1 }}>
            <TextField
              fullWidth
              label={t('tables.positions.instrument')}
              placeholder="EUR_USD"
              value={openForm.instrument}
              onChange={(e) =>
                setOpenForm({ ...openForm, instrument: e.target.value })
              }
              margin="normal"
              required
            />
            <FormControl fullWidth margin="normal">
              <InputLabel>{t('tables.positions.direction')}</InputLabel>
              <Select
                value={openForm.direction}
                label={t('tables.positions.direction')}
                onChange={(e) =>
                  setOpenForm({
                    ...openForm,
                    direction: e.target.value as 'long' | 'short',
                  })
                }
              >
                <MenuItem value="long">{t('tables.positions.long')}</MenuItem>
                <MenuItem value="short">{t('tables.positions.short')}</MenuItem>
              </Select>
            </FormControl>
            <TextField
              fullWidth
              label={t('tables.positions.units')}
              value={openForm.units}
              onChange={(e) =>
                setOpenForm({ ...openForm, units: e.target.value })
              }
              margin="normal"
              type="number"
              required
            />
            <TextField
              fullWidth
              label="Take Profit"
              value={openForm.take_profit}
              onChange={(e) =>
                setOpenForm({ ...openForm, take_profit: e.target.value })
              }
              margin="normal"
              type="number"
            />
            <TextField
              fullWidth
              label="Stop Loss"
              value={openForm.stop_loss}
              onChange={(e) =>
                setOpenForm({ ...openForm, stop_loss: e.target.value })
              }
              margin="normal"
              type="number"
            />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpenDialogOpen(false)} disabled={opening}>
            {t('actions.cancel')}
          </Button>
          <Button
            onClick={handleOpenPosition}
            variant="contained"
            color="primary"
            disabled={opening || !openForm.instrument || !openForm.units}
          >
            {opening ? <CircularProgress size={20} /> : t('actions.add')}
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

  const {
    data: ordersData,
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: ['oanda-orders', accountDbId, page, rowsPerPage],
    queryFn: () =>
      oandaMarketApi.getOrders({
        account_id: accountDbId,
        status: 'pending',
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
    if (selection.isAllPageSelected(pageRowIds)) {
      selection.deselectAllOnPage(pageRowIds);
    } else {
      selection.selectAllOnPage(pageRowIds);
    }
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
      render: (row) => <>{row.price ?? '\u2014'}</>,
    },
    { id: 'state', label: t('tables.orders.status'), width: 100 },
    { id: 'time_in_force', label: 'TIF', width: 60 },
    {
      id: 'create_time',
      label: t('tables.orders.timestamp'),
      width: 180,
      render: (row) => formatTimestamp(row.create_time),
    },
    {
      id: 'take_profit',
      label: 'TP',
      width: 100,
      align: 'right',
      render: (row) => <>{row.take_profit ?? '\u2014'}</>,
    },
    {
      id: 'stop_loss',
      label: 'SL',
      width: 100,
      align: 'right',
      render: (row) => <>{row.stop_loss ?? '\u2014'}</>,
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
    price: (r: OandaOrder) => r.price ?? '',
    state: (r: OandaOrder) => r.state,
    time_in_force: (r: OandaOrder) => r.time_in_force,
    create_time: (r: OandaOrder) => r.create_time ?? '',
    take_profit: (r: OandaOrder) => r.take_profit ?? '',
    stop_loss: (r: OandaOrder) => r.stop_loss ?? '',
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
      >
        <Typography variant="subtitle1">
          {t('tables.orders.title')} ({totalCount})
        </Typography>
        <Box display="flex" alignItems="center" gap={0.5}>
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
  const [rawDataOpen, setRawDataOpen] = useState(false);

  const containerSx = useMemo(() => ({ mt: 4, mb: 4, px: 3 }), []);

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

  const error =
    accountId === null
      ? 'Invalid account id'
      : queryError instanceof Error
        ? queryError.message
        : queryError
          ? t('common:errors.fetchFailed')
          : null;

  if (loading) {
    return (
      <Container maxWidth={false} sx={containerSx}>
        <Box display="flex" justifyContent="center" alignItems="center" py={4}>
          <CircularProgress />
        </Box>
      </Container>
    );
  }

  if (error) {
    return (
      <Container maxWidth={false} sx={containerSx}>
        <Breadcrumbs />
        <Alert severity="error">{error}</Alert>
      </Container>
    );
  }

  if (!account) {
    return (
      <Container maxWidth={false} sx={containerSx}>
        <Breadcrumbs />
        <Alert severity="info">{t('common:messages.noData')}</Alert>
      </Container>
    );
  }

  return (
    <Container maxWidth={false} sx={containerSx}>
      <Breadcrumbs />
      <Box
        display="flex"
        alignItems="center"
        justifyContent="space-between"
        mb={2}
      >
        <Typography variant="h5">
          {t('settings:accounts.accountDetails')}: {account.account_id}
        </Typography>
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
                {formatBalance(account.balance, account.currency)}
              </Typography>
            </Box>
            <Box>
              <Typography variant="body2" color="text.secondary">
                {t('settings:accounts.nav')}
              </Typography>
              <Typography variant="h6">
                {formatBalance(account.nav ?? null, account.currency)}
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
                {formatBalance(account.unrealized_pnl, account.currency)}
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
                {formatBalance(account.margin_used, account.currency)}
              </Typography>
            </Box>
            <Box>
              <Typography variant="body2" color="text.secondary">
                {t('settings:accounts.marginAvailable')}
              </Typography>
              <Typography variant="body1">
                {formatBalance(account.margin_available, account.currency)}
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
            {formatJson(account.oanda_account)}
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setRawDataOpen(false)}>
            {t('common:actions.close')}
          </Button>
        </DialogActions>
      </Dialog>
    </Container>
  );
}
