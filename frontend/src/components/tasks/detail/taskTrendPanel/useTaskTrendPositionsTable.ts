import { useCallback, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  useColumnConfig,
  type ColumnItem,
} from '../../../../hooks/useColumnConfig';
import {
  computePosPips,
  computePosPnl,
  DEFAULT_LS_POSITION_WIDTHS,
  formatTrendTimestamp,
} from './shared';
import type { LSPosSortableKey, TrendPosition } from './shared';
import { useResizableColumns } from './useResizableColumns';

interface UseTaskTrendPositionsTableParams {
  positions: TrendPosition[];
  currentPrice: number | null;
  pipSize: number | null | undefined;
  storageKey: string;
  timezone: string;
}

export function useTaskTrendPositionsTable({
  positions,
  currentPrice,
  pipSize,
  storageKey,
  timezone,
}: UseTaskTrendPositionsTableParams) {
  const { t } = useTranslation('common');
  const [showOpenOnly, setShowOpenOnly] = useState(false);
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(10);
  const [orderBy, setOrderBy] = useState<LSPosSortableKey>('entry_time');
  const [order, setOrder] = useState<'asc' | 'desc'>('desc');
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [configOpen, setConfigOpen] = useState(false);
  const { colWidths, createResizeHandle } = useResizableColumns(
    DEFAULT_LS_POSITION_WIDTHS
  );

  const positionColDefaults: ColumnItem[] = [
    { id: 'entry_time', label: t('tables.trend.openTime'), visible: true },
    { id: 'exit_time', label: t('tables.trend.closeTime'), visible: true },
    { id: '_status', label: t('tables.trend.status'), visible: true },
    { id: 'layer_index', label: t('tables.trend.layer'), visible: true },
    {
      id: 'retracement_count',
      label: t('tables.trend.retrace'),
      visible: true,
    },
    { id: 'units', label: t('tables.trend.units'), visible: true },
    { id: 'entry_price', label: t('tables.trend.entry'), visible: true },
    { id: 'exit_price', label: t('tables.trend.exit'), visible: true },
    { id: '_pips', label: t('tables.trend.pips'), visible: true },
    { id: '_pnl', label: t('tables.trend.pnl'), visible: true },
  ];

  const {
    columns: columnConfig,
    updateColumns,
    resetToDefaults,
  } = useColumnConfig(storageKey, positionColDefaults);

  const handleSort = useCallback((column: LSPosSortableKey) => {
    setOrderBy((prev) => {
      if (prev === column) {
        setOrder((current) => (current === 'asc' ? 'desc' : 'asc'));
        return prev;
      }
      setOrder(
        column === 'entry_time' || column === 'exit_time' ? 'desc' : 'asc'
      );
      return column;
    });
    setPage(0);
  }, []);

  const sortedPositions = useMemo(() => {
    const filtered = showOpenOnly
      ? positions.filter((position) => position._status === 'open')
      : positions;

    return [...filtered].sort((a, b) => {
      let cmp = 0;
      switch (orderBy) {
        case 'entry_time':
          cmp =
            new Date(a.entry_time).getTime() - new Date(b.entry_time).getTime();
          break;
        case 'exit_time': {
          const aT = a.exit_time ? new Date(a.exit_time).getTime() : 0;
          const bT = b.exit_time ? new Date(b.exit_time).getTime() : 0;
          cmp = aT - bT;
          break;
        }
        case '_status':
          cmp = a._status.localeCompare(b._status);
          break;
        case 'layer_index':
          cmp = (a.layer_index ?? -1) - (b.layer_index ?? -1);
          break;
        case 'retracement_count':
          cmp = (a.retracement_count ?? -1) - (b.retracement_count ?? -1);
          break;
        case 'units':
          cmp = Math.abs(a.units ?? 0) - Math.abs(b.units ?? 0);
          break;
        case 'entry_price':
          cmp =
            parseFloat(a.entry_price || '0') - parseFloat(b.entry_price || '0');
          break;
        case 'exit_price':
          cmp =
            parseFloat(a.exit_price || '0') - parseFloat(b.exit_price || '0');
          break;
        case '_pips':
          cmp =
            computePosPips(a, currentPrice, pipSize) -
            computePosPips(b, currentPrice, pipSize);
          break;
        case '_pnl':
          cmp = computePosPnl(a, currentPrice) - computePosPnl(b, currentPrice);
          break;
      }
      return order === 'asc' ? cmp : -cmp;
    });
  }, [currentPrice, order, orderBy, pipSize, positions, showOpenOnly]);

  const paginatedPositions = useMemo(
    () =>
      sortedPositions.slice(
        page * rowsPerPage,
        page * rowsPerPage + rowsPerPage
      ),
    [page, rowsPerPage, sortedPositions]
  );

  const isAllPageSelected =
    paginatedPositions.length > 0 &&
    paginatedPositions.every((row) => selectedIds.has(row.id));

  const toggleSelection = useCallback((id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const selectAllOnPage = useCallback(() => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      for (const row of paginatedPositions) next.add(row.id);
      return next;
    });
  }, [paginatedPositions]);

  const togglePageSelection = useCallback(() => {
    if (isAllPageSelected) {
      setSelectedIds((prev) => {
        const next = new Set(prev);
        for (const row of paginatedPositions) next.delete(row.id);
        return next;
      });
      return;
    }
    selectAllOnPage();
  }, [isAllPageSelected, paginatedPositions, selectAllOnPage]);

  const resetSelection = useCallback(() => {
    setSelectedIds(new Set());
  }, []);

  const copySelectedPositions = useCallback(
    (isShort: boolean) => {
      const extractors: Record<string, (position: TrendPosition) => string> = {
        entry_time: (position) =>
          formatTrendTimestamp(position.entry_time, timezone),
        exit_time: (position) =>
          formatTrendTimestamp(position.exit_time, timezone),
        _status: (position) =>
          position._status === 'open' ? 'Open' : 'Closed',
        layer_index: (position) => String(position.layer_index ?? '-'),
        retracement_count: (position) =>
          String(position.retracement_count ?? '-'),
        units: (position) => String(position.units),
        entry_price: (position) => {
          const value = position.entry_price
            ? parseFloat(position.entry_price)
            : null;
          return value != null ? `¥${value.toFixed(3)}` : '-';
        },
        exit_price: (position) => {
          const value = position.exit_price
            ? parseFloat(position.exit_price)
            : null;
          return value != null ? `¥${value.toFixed(3)}` : '-';
        },
        _pips: (position) => {
          const entryPrice = position.entry_price
            ? parseFloat(position.entry_price)
            : null;
          const exitPrice = position.exit_price
            ? parseFloat(position.exit_price)
            : null;
          const isOpen = position._status === 'open';
          const hasPrice = isOpen
            ? currentPrice != null && entryPrice != null
            : exitPrice != null && entryPrice != null;

          return pipSize && hasPrice
            ? computePosPips(position, currentPrice, pipSize).toFixed(1)
            : '-';
        },
        _pnl: (position) => {
          const isOpen = position._status === 'open';
          const entryPrice = position.entry_price
            ? parseFloat(position.entry_price)
            : null;
          const exitPrice = position.exit_price
            ? parseFloat(position.exit_price)
            : null;
          const units = Math.abs(position.units ?? 0);
          let pnl: number | null = null;

          if (isOpen && currentPrice != null && entryPrice != null) {
            pnl = isShort
              ? (entryPrice - currentPrice) * units
              : (currentPrice - entryPrice) * units;
          } else if (!isOpen && exitPrice != null && entryPrice != null) {
            pnl = isShort
              ? (entryPrice - exitPrice) * units
              : (exitPrice - entryPrice) * units;
          }

          return pnl != null ? pnl.toFixed(2) : '-';
        },
      };

      const visibleCols = columnConfig.filter((column) => column.visible);
      const applicableCols = visibleCols.filter(
        (column) => extractors[column.id] != null
      );
      const header = applicableCols.map((column) => column.label).join('\t');
      const rows = sortedPositions
        .filter((position) => selectedIds.has(position.id))
        .map((position) =>
          applicableCols
            .map((column) => {
              const extractor = extractors[column.id];
              return extractor ? extractor(position) : '-';
            })
            .join('\t')
        );

      navigator.clipboard.writeText([header, ...rows].join('\n'));
    },
    [
      columnConfig,
      currentPrice,
      pipSize,
      selectedIds,
      sortedPositions,
      timezone,
    ]
  );

  const toggleOpenOnly = useCallback(() => {
    setShowOpenOnly((prev) => !prev);
    setPage(0);
  }, []);

  return {
    showOpenOnly,
    page,
    rowsPerPage,
    orderBy,
    order,
    selectedIds,
    setPage,
    setRowsPerPage,
    setSelectedIds,
    sortedPositions,
    paginatedPositions,
    isAllPageSelected,
    colWidths,
    createResizeHandle,
    columnConfig,
    updateColumns,
    resetToDefaults,
    configOpen,
    setConfigOpen,
    handleSort,
    toggleSelection,
    selectAllOnPage,
    togglePageSelection,
    resetSelection,
    copySelectedPositions,
    toggleOpenOnly,
  };
}
