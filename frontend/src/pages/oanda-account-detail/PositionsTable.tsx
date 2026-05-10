import { useCallback, useState } from 'react';
import {
  Box,
  Button,
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
  Add as AddIcon,
  Close as CloseIcon,
  Settings as SettingsIcon,
} from '@mui/icons-material';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { useToast } from '../../components/common/useToast';
import DataTable, { type Column } from '../../components/common/DataTable';
import { TableSelectionToolbar } from '../../components/common/TableSelectionToolbar';
import { ColumnConfigDialog } from '../../components/common/ColumnConfigDialog';
import {
  applyColumnConfig,
  columnsToDefaults,
  useColumnConfig,
} from '../../hooks/useColumnConfig';
import { useSupportedInstruments } from '../../hooks/useMarketConfig';
import { useTableRowSelection } from '../../hooks/useTableRowSelection';
import {
  oandaMarketApi,
  type OandaPosition,
} from '../../services/api/oandaMarket';
import { buildCopyHandler } from '../../utils/tableCopyUtils';
import {
  fmtQuoteValue,
  fmtSignedQuoteValue,
  toOrdering,
  type SortOrder,
} from './formatters';
import { useDateTimeFormatter } from '../../hooks/useDateTimeFormatter';

export function PositionsTable({ accountDbId }: { accountDbId: number }) {
  const { t } = useTranslation(['common', 'settings']);
  const { formatDateTime } = useDateTimeFormatter({
    includeSeconds: true,
    includeTimezone: true,
  });
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();
  const { instruments } = useSupportedInstruments();
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(25);
  const [sortField, setSortField] = useState('open_time');
  const [sortOrder, setSortOrder] = useState<SortOrder>('desc');
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
      sortField,
      sortOrder,
      page,
      rowsPerPage,
    ],
    queryFn: () =>
      oandaMarketApi.getPositions({
        account_id: accountDbId,
        status: positionStatusFilter,
        ordering: toOrdering(sortField, sortOrder),
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

  const handleSortChange = useCallback((field: string, order: SortOrder) => {
    setSortField(field);
    setSortOrder(order);
    setPage(0);
  }, []);
  const fmtTimestamp = useCallback(
    (timestamp: string | null) =>
      timestamp ? formatDateTime(timestamp) : '\u2014',
    [formatDateTime]
  );

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
      width: 220,
      minWidth: 220,
      render: (row) => fmtTimestamp(row.open_time),
    },
    {
      id: 'close_time' as keyof OandaPosition,
      label: t('common:tables.positions.closeTimestamp'),
      width: 220,
      minWidth: 220,
      render: (row) => fmtTimestamp(row.close_time ?? null),
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
    open_time: (r: OandaPosition) => fmtTimestamp(r.open_time),
    close_time: (r: OandaPosition) => fmtTimestamp(r.close_time ?? null),
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
        sortMode="server"
        orderBy={sortField}
        order={sortOrder}
        onSortChange={handleSortChange}
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
                type="text"
                inputMode="decimal"
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
              type="text"
              inputMode="decimal"
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
                  type="text"
                  inputMode="decimal"
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
                  type="text"
                  inputMode="decimal"
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
