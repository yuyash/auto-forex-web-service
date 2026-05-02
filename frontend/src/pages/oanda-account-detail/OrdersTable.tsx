import { useCallback, useState } from 'react';
import {
  Box,
  Chip,
  IconButton,
  TablePagination,
  ToggleButton,
  ToggleButtonGroup,
  Tooltip,
  Typography,
} from '@mui/material';
import { Settings as SettingsIcon } from '@mui/icons-material';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import DataTable, { type Column } from '../../components/common/DataTable';
import { TableSelectionToolbar } from '../../components/common/TableSelectionToolbar';
import { ColumnConfigDialog } from '../../components/common/ColumnConfigDialog';
import {
  applyColumnConfig,
  columnsToDefaults,
  useColumnConfig,
} from '../../hooks/useColumnConfig';
import { useTableRowSelection } from '../../hooks/useTableRowSelection';
import {
  oandaMarketApi,
  type OandaOrder,
} from '../../services/api/oandaMarket';
import { buildCopyHandler } from '../../utils/tableCopyUtils';
import { useDateTimeFormatter } from '../../hooks/useDateTimeFormatter';
import { fmtQuoteValue, toOrdering, type SortOrder } from './formatters';

export function OrdersTable({ accountDbId }: { accountDbId: number }) {
  const { t } = useTranslation('common');
  const { formatDateTime } = useDateTimeFormatter({
    includeSeconds: true,
    includeTimezone: true,
  });
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(25);
  const [sortField, setSortField] = useState('create_time');
  const [sortOrder, setSortOrder] = useState<SortOrder>('desc');
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
      sortField,
      sortOrder,
      page,
      rowsPerPage,
    ],
    queryFn: () =>
      oandaMarketApi.getOrders({
        account_id: accountDbId,
        status: orderStatusFilter,
        ordering: toOrdering(sortField, sortOrder),
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
      width: 220,
      minWidth: 220,
      render: (row) => fmtTimestamp(row.create_time),
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
    create_time: (r: OandaOrder) => fmtTimestamp(r.create_time),
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
        sortMode="server"
        orderBy={sortField}
        order={sortOrder}
        onSortChange={handleSortChange}
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
