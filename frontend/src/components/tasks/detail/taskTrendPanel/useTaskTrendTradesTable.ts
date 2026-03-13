import { useCallback, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  useColumnConfig,
  type ColumnItem,
} from '../../../../hooks/useColumnConfig';
import { DEFAULT_REPLAY_WIDTHS } from './shared';
import type { ReplayTrade, SortableKey } from './shared';
import { useResizableColumns } from './useResizableColumns';

export function useTaskTrendTradesTable(trades: ReplayTrade[]) {
  const { t } = useTranslation('common');
  const [orderBy, setOrderBy] = useState<SortableKey>('timestamp');
  const [order, setOrder] = useState<'asc' | 'desc'>('desc');
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(10);
  const [selectedRowIds, setSelectedRowIds] = useState<Set<string>>(new Set());
  const [configOpen, setConfigOpen] = useState(false);
  const selectedRowRef = useRef<HTMLTableRowElement | null>(null);
  const { colWidths, createResizeHandle } = useResizableColumns(
    DEFAULT_REPLAY_WIDTHS
  );

  const tradesColDefaults: ColumnItem[] = [
    { id: 'timestamp', label: t('tables.trend.time'), visible: true },
    { id: 'direction', label: t('tables.trend.direction'), visible: true },
    { id: 'layer_index', label: t('tables.trend.layer'), visible: true },
    { id: 'retracement_count', label: t('tables.trend.ret'), visible: true },
    { id: 'units', label: t('tables.trend.units'), visible: true },
    { id: 'price', label: t('tables.trend.price'), visible: true },
    { id: 'execution_method', label: t('tables.trend.event'), visible: true },
  ];

  const {
    columns: columnConfig,
    updateColumns,
    resetToDefaults,
  } = useColumnConfig('trend_trades', tradesColDefaults);

  const sortedTrades = useMemo(() => {
    return [...trades].sort((a, b) => {
      let cmp = 0;
      switch (orderBy) {
        case 'timestamp':
          cmp =
            new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime();
          break;
        case 'direction':
          cmp = a.direction.localeCompare(b.direction);
          break;
        case 'layer_index':
          cmp = (a.layer_index ?? -1) - (b.layer_index ?? -1);
          break;
        case 'retracement_count':
          cmp = (a.retracement_count ?? -1) - (b.retracement_count ?? -1);
          break;
        case 'units':
          cmp = Number(a.units) - Number(b.units);
          break;
        case 'price':
          cmp = Number(a.price) - Number(b.price);
          break;
        case 'execution_method':
          cmp = (a.execution_method || '').localeCompare(
            b.execution_method || ''
          );
          break;
      }
      return order === 'asc' ? cmp : -cmp;
    });
  }, [order, orderBy, trades]);

  const paginatedTrades = useMemo(
    () =>
      sortedTrades.slice(page * rowsPerPage, page * rowsPerPage + rowsPerPage),
    [page, rowsPerPage, sortedTrades]
  );

  const isAllPageSelected =
    paginatedTrades.length > 0 &&
    paginatedTrades.every((row) => selectedRowIds.has(row.id));

  const handleSort = useCallback(
    (column: SortableKey) => {
      if (orderBy === column) {
        setOrder((prev) => (prev === 'asc' ? 'desc' : 'asc'));
        setPage(0);
        return;
      }
      setOrderBy(column);
      setOrder('asc');
      setPage(0);
    },
    [orderBy]
  );

  const toggleRowSelection = useCallback((id: string) => {
    setSelectedRowIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const selectAllOnPage = useCallback(() => {
    setSelectedRowIds((prev) => {
      const next = new Set(prev);
      for (const row of paginatedTrades) next.add(row.id);
      return next;
    });
  }, [paginatedTrades]);

  const togglePageSelection = useCallback(() => {
    if (isAllPageSelected) {
      setSelectedRowIds((prev) => {
        const next = new Set(prev);
        for (const row of paginatedTrades) next.delete(row.id);
        return next;
      });
      return;
    }
    selectAllOnPage();
  }, [isAllPageSelected, paginatedTrades, selectAllOnPage]);

  const resetSelection = useCallback(() => {
    setSelectedRowIds(new Set());
  }, []);

  const copySelectedRows = useCallback(() => {
    const extractors: Record<string, (row: ReplayTrade) => string> = {
      timestamp: (row) => new Date(row.timestamp).toLocaleString(),
      direction: (row) => (row.direction ? row.direction.toUpperCase() : ''),
      layer_index: (row) => String(row.layer_index ?? '-'),
      retracement_count: (row) => String(row.retracement_count ?? '-'),
      units: (row) => String(row.units),
      price: (row) =>
        row.price ? `¥${parseFloat(row.price).toFixed(3)}` : '-',
      execution_method: (row) =>
        row.execution_method_display || row.execution_method || '-',
    };

    const visibleCols = columnConfig.filter((column) => column.visible);
    const applicableCols = visibleCols.filter(
      (column) => extractors[column.id] != null
    );
    const header = applicableCols.map((column) => column.label).join('\t');
    const rows = sortedTrades
      .filter((row) => selectedRowIds.has(row.id))
      .map((row) =>
        applicableCols
          .map((column) => {
            const extractor = extractors[column.id];
            return extractor ? extractor(row) : '-';
          })
          .join('\t')
      );

    navigator.clipboard.writeText([header, ...rows].join('\n'));
  }, [columnConfig, selectedRowIds, sortedTrades]);

  return {
    orderBy,
    order,
    page,
    rowsPerPage,
    setPage,
    setRowsPerPage,
    selectedRowIds,
    setSelectedRowIds,
    selectedRowRef,
    sortedTrades,
    paginatedTrades,
    isAllPageSelected,
    colWidths,
    createResizeHandle,
    columnConfig,
    updateColumns,
    resetToDefaults,
    configOpen,
    setConfigOpen,
    handleSort,
    toggleRowSelection,
    togglePageSelection,
    resetSelection,
    copySelectedRows,
    selectAllOnPage,
  };
}
