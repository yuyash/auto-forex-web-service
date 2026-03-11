/**
 * TaskPositionsTable Component
 *
 * Displays two sections: Closed Positions and Open Positions.
 * Each section contains Long Positions and Short Positions tables stacked
 * vertically. Direction column is omitted since each table only shows one
 * direction.
 * Closed Positions section shows Total Realized PnL.
 * Open Positions section shows Total Unrealized PnL.
 */

import React, { useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Box,
  Typography,
  Alert,
  TablePagination,
  IconButton,
  Tooltip,
} from '@mui/material';
import {
  History as HistoryIcon,
  Settings as SettingsIcon,
} from '@mui/icons-material';
import DataTable, { type Column } from '../../common/DataTable';
import { TableSelectionToolbar } from '../../common/TableSelectionToolbar';
import { useTableRowSelection } from '../../../hooks/useTableRowSelection';
import {
  useTaskPositions,
  type TaskPosition,
} from '../../../hooks/useTaskPositions';
import { useTaskSummary } from '../../../hooks/useTaskSummary';
import { TaskType } from '../../../types/common';
import { PositionLifecycleDialog } from './PositionLifecycleDialog';
import { ColumnConfigDialog } from '../../common/ColumnConfigDialog';
import {
  useColumnConfig,
  columnsToDefaults,
  applyColumnConfig,
} from '../../../hooks/useColumnConfig';

interface TaskPositionsTableProps {
  taskId: string | number;
  taskType: TaskType;
  executionRunId?: string;
  enableRealTimeUpdates?: boolean;
  currentPrice?: number | null;
  pipSize?: number | null;
}

export const TaskPositionsTable: React.FC<TaskPositionsTableProps> = ({
  taskId,
  taskType,
  executionRunId,
  enableRealTimeUpdates = false,
  currentPrice,
  pipSize,
}) => {
  const { t } = useTranslation('common');

  // --- Pagination state ---
  const [closedLongPage, setClosedLongPage] = useState(0);
  const [closedShortPage, setClosedShortPage] = useState(0);
  const [openLongPage, setOpenLongPage] = useState(0);
  const [openShortPage, setOpenShortPage] = useState(0);
  const rpp = 10;
  const [closedLongRpp, setClosedLongRpp] = useState(rpp);
  const [closedShortRpp, setClosedShortRpp] = useState(rpp);
  const [openLongRpp, setOpenLongRpp] = useState(rpp);
  const [openShortRpp, setOpenShortRpp] = useState(rpp);

  // --- Reload state ---
  const [reloading, setReloading] = useState<Record<string, boolean>>({});

  // --- Selection ---
  const closedLongSel = useTableRowSelection();
  const closedShortSel = useTableRowSelection();
  const openLongSel = useTableRowSelection();
  const openShortSel = useTableRowSelection();

  // --- Data fetching ---
  const usePosQuery = (
    status: 'open' | 'closed',
    direction: 'long' | 'short',
    page: number,
    pageSize: number
  ) =>
    useTaskPositions({
      taskId,
      taskType,
      executionRunId,
      status,
      direction,
      page: page + 1,
      pageSize,
      enableRealTimeUpdates,
    });

  const {
    positions: closedLongPos,
    totalCount: closedLongTotal,
    isLoading: cl1,
    error: ce1,
    refetch: rCL,
  } = usePosQuery('closed', 'long', closedLongPage, closedLongRpp);
  const {
    positions: closedShortPos,
    totalCount: closedShortTotal,
    isLoading: cl2,
    error: ce2,
    refetch: rCS,
  } = usePosQuery('closed', 'short', closedShortPage, closedShortRpp);
  const {
    positions: openLongPos,
    totalCount: openLongTotal,
    isLoading: cl3,
    error: ce3,
    refetch: rOL,
  } = usePosQuery('open', 'long', openLongPage, openLongRpp);
  const {
    positions: openShortPos,
    totalCount: openShortTotal,
    isLoading: cl4,
    error: ce4,
    refetch: rOS,
  } = usePosQuery('open', 'short', openShortPage, openShortRpp);

  const isLoading = cl1 || cl2 || cl3 || cl4;
  const error = ce1 || ce2 || ce3 || ce4;

  // --- PnL summary ---
  const {
    summary: {
      pnl: { realized: totalRealizedPnl, unrealized: totalUnrealizedPnl },
    },
    refetch: refetchPnl,
  } = useTaskSummary(String(taskId), taskType, executionRunId);

  const prevRealTimeRef = React.useRef(enableRealTimeUpdates);
  React.useEffect(() => {
    if (prevRealTimeRef.current && !enableRealTimeUpdates) refetchPnl();
    prevRealTimeRef.current = enableRealTimeUpdates;
  }, [enableRealTimeUpdates, refetchPnl]);
  React.useEffect(() => {
    if (!enableRealTimeUpdates) return;
    const interval = setInterval(refetchPnl, 10000);
    return () => clearInterval(interval);
  }, [enableRealTimeUpdates, refetchPnl]);

  const getRowId = useCallback((row: TaskPosition) => String(row.id), []);

  // --- Lifecycle dialog state ---
  const [lifecycleOpen, setLifecycleOpen] = useState(false);
  const [lifecyclePositionId, setLifecyclePositionId] = useState<string>('');
  const [lifecyclePosition, setLifecyclePosition] =
    useState<TaskPosition | null>(null);

  const handleOpenLifecycle = useCallback(
    (positionId: string, position?: TaskPosition) => {
      setLifecyclePositionId(positionId);
      setLifecyclePosition(position ?? null);
      setLifecycleOpen(true);
    },
    []
  );

  const formatTimestamp = (ts: string): string =>
    new Date(ts).toLocaleString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });

  // --- Column builders ---
  const closedCols = (dir: 'long' | 'short'): Column<TaskPosition>[] => [
    {
      id: 'id',
      label: t('tables.positions.positionId'),
      width: 150,
      minWidth: 110,
      render: (r) =>
        r.id ? (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
            <Typography variant="body2" fontFamily="monospace">
              {String(r.id).slice(0, 8)}
            </Typography>
            <Tooltip title={t('tables.positions.lifecycle.viewLifecycle')}>
              <IconButton
                size="small"
                onClick={(e) => {
                  e.stopPropagation();
                  handleOpenLifecycle(String(r.id).slice(0, 8), r);
                }}
                aria-label={t('tables.positions.lifecycle.viewLifecycle')}
                sx={{ p: 0.25 }}
              >
                <HistoryIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          </Box>
        ) : (
          '-'
        ),
    },
    {
      id: 'entry_time',
      label: t('tables.positions.openTimestamp'),
      width: 180,
      minWidth: 140,
      render: (r) => (r.entry_time ? formatTimestamp(r.entry_time) : '-'),
    },
    {
      id: 'exit_time',
      label: t('tables.positions.closeTimestamp'),
      width: 180,
      minWidth: 140,
      render: (r) => (r.exit_time ? formatTimestamp(r.exit_time) : '-'),
    },
    {
      id: 'instrument',
      label: t('tables.positions.instrument'),
      width: 110,
      minWidth: 80,
    },
    {
      id: 'units',
      label: t('tables.positions.units'),
      width: 90,
      minWidth: 70,
      align: 'right',
      render: (r) => String(Math.abs(r.units)),
    },
    {
      id: 'layer_index',
      label: t('tables.positions.layer'),
      width: 70,
      minWidth: 50,
      align: 'right',
      render: (r) => (r.layer_index != null ? String(r.layer_index) : '-'),
    },
    {
      id: 'retracement_count',
      label: t('tables.positions.retracement'),
      width: 70,
      minWidth: 50,
      align: 'right',
      render: (r) =>
        r.retracement_count != null ? String(r.retracement_count) : '-',
    },
    {
      id: 'entry_price',
      label: t('tables.positions.openPrice'),
      width: 110,
      minWidth: 80,
      align: 'right',
      render: (r) =>
        r.entry_price ? `¥${parseFloat(r.entry_price).toFixed(3)}` : '-',
    },
    {
      id: 'exit_price',
      label: t('tables.positions.closePrice'),
      width: 110,
      minWidth: 80,
      align: 'right',
      render: (r) =>
        r.exit_price ? `¥${parseFloat(r.exit_price).toFixed(3)}` : '-',
    },
    {
      id: 'planned_exit_price',
      label: t('tables.positions.plannedExitPrice'),
      width: 130,
      minWidth: 90,
      align: 'right',
      render: (r) =>
        r.planned_exit_price
          ? `¥${parseFloat(r.planned_exit_price).toFixed(3)}`
          : '-',
    },
    {
      id: 'planned_exit_price_formula',
      label: t('tables.positions.plannedExitPriceFormula'),
      width: 220,
      minWidth: 150,
      render: (r) => r.planned_exit_price_formula ?? '-',
    },
    {
      id: 'pips',
      label: t('tables.positions.pips'),
      width: 90,
      minWidth: 70,
      align: 'right',
      render: (r) => {
        if (!r.entry_price || !r.exit_price || !pipSize) return '-';
        const ep = parseFloat(r.entry_price),
          xp = parseFloat(r.exit_price);
        const pips = (dir === 'long' ? xp - ep : ep - xp) / pipSize;
        if (!Number.isFinite(pips)) return '-';
        return (
          <Typography
            variant="body2"
            color={pips >= 0 ? 'success.main' : 'error.main'}
            fontWeight="bold"
          >
            {pips >= 0 ? '+' : ''}
            {pips.toFixed(1)}
          </Typography>
        );
      },
    },
    {
      id: 'realized_pnl',
      label: t('tables.positions.realizedPnl'),
      width: 120,
      minWidth: 90,
      align: 'right',
      render: (r) => {
        if (!r.exit_price || !r.entry_price) return '-';
        const ep = parseFloat(r.entry_price),
          xp = parseFloat(r.exit_price),
          u = Math.abs(r.units ?? 0);
        const val = dir === 'long' ? (xp - ep) * u : (ep - xp) * u;
        return (
          <Typography
            variant="body2"
            color={val >= 0 ? 'success.main' : 'error.main'}
            fontWeight="bold"
          >
            {val >= 0 ? '+' : ''}¥{val.toFixed(2)}
          </Typography>
        );
      },
    },
  ];

  const openCols = (dir: 'long' | 'short'): Column<TaskPosition>[] => [
    {
      id: 'id',
      label: t('tables.positions.positionId'),
      width: 150,
      minWidth: 110,
      render: (r) =>
        r.id ? (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
            <Typography variant="body2" fontFamily="monospace">
              {String(r.id).slice(0, 8)}
            </Typography>
            <Tooltip title={t('tables.positions.lifecycle.viewLifecycle')}>
              <IconButton
                size="small"
                onClick={(e) => {
                  e.stopPropagation();
                  handleOpenLifecycle(String(r.id).slice(0, 8), r);
                }}
                aria-label={t('tables.positions.lifecycle.viewLifecycle')}
                sx={{ p: 0.25 }}
              >
                <HistoryIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          </Box>
        ) : (
          '-'
        ),
    },
    {
      id: 'entry_time',
      label: t('tables.positions.openTimestamp'),
      width: 180,
      minWidth: 140,
      render: (r) => (r.entry_time ? formatTimestamp(r.entry_time) : '-'),
    },
    {
      id: 'instrument',
      label: t('tables.positions.instrument'),
      width: 110,
      minWidth: 80,
    },
    {
      id: 'units',
      label: t('tables.positions.units'),
      width: 90,
      minWidth: 70,
      align: 'right',
      render: (r) => String(Math.abs(r.units)),
    },
    {
      id: 'layer_index',
      label: t('tables.positions.layer'),
      width: 70,
      minWidth: 50,
      align: 'right',
      render: (r) => (r.layer_index != null ? String(r.layer_index) : '-'),
    },
    {
      id: 'retracement_count',
      label: t('tables.positions.retracement'),
      width: 70,
      minWidth: 50,
      align: 'right',
      render: (r) =>
        r.retracement_count != null ? String(r.retracement_count) : '-',
    },
    {
      id: 'entry_price',
      label: t('tables.positions.openPrice'),
      width: 110,
      minWidth: 80,
      align: 'right',
      render: (r) =>
        r.entry_price ? `¥${parseFloat(r.entry_price).toFixed(3)}` : '-',
    },
    {
      id: 'planned_exit_price',
      label: t('tables.positions.plannedExitPrice'),
      width: 130,
      minWidth: 90,
      align: 'right',
      render: (r) =>
        r.planned_exit_price
          ? `¥${parseFloat(r.planned_exit_price).toFixed(3)}`
          : '-',
    },
    {
      id: 'planned_exit_price_formula',
      label: t('tables.positions.plannedExitPriceFormula'),
      width: 220,
      minWidth: 150,
      render: (r) => r.planned_exit_price_formula ?? '-',
    },
    {
      id: 'pips',
      label: t('tables.positions.pips'),
      width: 90,
      minWidth: 70,
      align: 'right',
      render: (r) => {
        if (currentPrice == null || !r.entry_price || !pipSize) return '-';
        const ep = parseFloat(r.entry_price);
        const pips =
          (dir === 'long' ? currentPrice - ep : ep - currentPrice) / pipSize;
        return (
          <Typography
            variant="body2"
            color={pips >= 0 ? 'success.main' : 'error.main'}
            fontWeight="bold"
          >
            {pips >= 0 ? '+' : ''}
            {pips.toFixed(1)}
          </Typography>
        );
      },
    },
    {
      id: 'unrealized_pnl',
      label: t('tables.positions.unrealizedPnl'),
      width: 130,
      minWidth: 100,
      align: 'right',
      render: (r) => {
        if (currentPrice == null || !r.entry_price) return '-';
        const ep = parseFloat(r.entry_price),
          u = Math.abs(r.units ?? 0);
        const val =
          dir === 'long' ? (currentPrice - ep) * u : (ep - currentPrice) * u;
        return (
          <Typography
            variant="body2"
            color={val >= 0 ? 'success.main' : 'error.main'}
            fontWeight="bold"
          >
            {val >= 0 ? '+' : ''}¥{val.toFixed(2)}
          </Typography>
        );
      },
    },
  ];

  // --- Helpers ---

  // Column config for closed and open position tables
  const [closedColConfigOpen, setClosedColConfigOpen] = useState(false);
  const [openColConfigOpen, setOpenColConfigOpen] = useState(false);
  const closedColDefaults = columnsToDefaults(closedCols('long'));
  const openColDefaults = columnsToDefaults(openCols('long'));
  const {
    columns: closedColConfig,
    updateColumns: updateClosedCols,
    resetToDefaults: resetClosedCols,
  } = useColumnConfig('positions_closed', closedColDefaults);
  const {
    columns: openColConfig,
    updateColumns: updateOpenCols,
    resetToDefaults: resetOpenCols,
  } = useColumnConfig('positions_open', openColDefaults);

  const filteredClosedCols = (dir: 'long' | 'short') =>
    applyColumnConfig(closedCols(dir), closedColConfig);
  const filteredOpenCols = (dir: 'long' | 'short') =>
    applyColumnConfig(openCols(dir), openColConfig);

  const makeToggleAll = (sel: typeof closedLongSel, ids: string[]) => () => {
    if (sel.isAllPageSelected(ids)) {
      for (const id of ids) {
        if (sel.selectedRowIds.has(id)) sel.toggleRowSelection(id);
      }
    } else sel.selectAllOnPage(ids);
  };

  const makeReload =
    (key: string, refetch: () => Promise<void>) => async () => {
      setReloading((p) => ({ ...p, [key]: true }));
      await refetch();
      setReloading((p) => ({ ...p, [key]: false }));
    };

  const makeCopy =
    (
      positions: TaskPosition[],
      sel: typeof closedLongSel,
      headers: string[],
      rowFn: (r: TaskPosition) => string
    ) =>
    () => {
      const posMap = new Map(positions.map((p) => [String(p.id), p]));
      sel.copySelectedRows(headers, (id) => {
        const r = posMap.get(id);
        return r ? rowFn(r) : '';
      });
    };

  // --- Row formatters for copy ---
  const closedRowFn =
    (dir: 'long' | 'short') =>
    (r: TaskPosition): string => {
      const ep = r.entry_price ? parseFloat(r.entry_price) : null;
      const xp = r.exit_price ? parseFloat(r.exit_price) : null;
      const u = Math.abs(r.units ?? 0);
      let pipsStr = '-';
      let pnlStr = '-';
      if (ep != null && xp != null && pipSize) {
        const pips = (dir === 'long' ? xp - ep : ep - xp) / pipSize;
        if (Number.isFinite(pips)) pipsStr = pips.toFixed(1);
      }
      if (ep != null && xp != null) {
        const val = dir === 'long' ? (xp - ep) * u : (ep - xp) * u;
        pnlStr = val.toFixed(2);
      }
      return [
        r.entry_time ? formatTimestamp(r.entry_time) : '-',
        r.exit_time ? formatTimestamp(r.exit_time) : '-',
        r.instrument ?? '-',
        String(Math.abs(r.units)),
        r.layer_index != null ? String(r.layer_index) : '-',
        r.retracement_count != null ? String(r.retracement_count) : '-',
        ep != null ? `¥${ep.toFixed(3)}` : '-',
        xp != null ? `¥${xp.toFixed(3)}` : '-',
        r.planned_exit_price
          ? `¥${parseFloat(r.planned_exit_price).toFixed(3)}`
          : '-',
        r.planned_exit_price_formula ?? '-',
        pipsStr,
        pnlStr,
      ].join('\t');
    };

  const closedHeaders = [
    'Open Time',
    'Close Time',
    'Instrument',
    'Units',
    'Layer',
    'Retracement',
    'Open Price',
    'Close Price',
    'Planned Exit',
    'Exit Formula',
    'Pips',
    'Realized PnL',
  ];

  const openRowFn =
    (dir: 'long' | 'short') =>
    (r: TaskPosition): string => {
      const ep = r.entry_price ? parseFloat(r.entry_price) : null;
      let pipsStr = '-';
      let pnlStr = '-';
      if (currentPrice != null && ep != null && pipSize) {
        const pips =
          (dir === 'long' ? currentPrice - ep : ep - currentPrice) / pipSize;
        if (Number.isFinite(pips)) pipsStr = pips.toFixed(1);
      }
      if (currentPrice != null && ep != null) {
        const u = Math.abs(r.units ?? 0);
        const val =
          dir === 'long' ? (currentPrice - ep) * u : (ep - currentPrice) * u;
        pnlStr = val.toFixed(2);
      }
      return [
        r.entry_time ? formatTimestamp(r.entry_time) : '-',
        r.instrument ?? '-',
        String(Math.abs(r.units)),
        r.layer_index != null ? String(r.layer_index) : '-',
        r.retracement_count != null ? String(r.retracement_count) : '-',
        ep != null ? `¥${ep.toFixed(3)}` : '-',
        r.planned_exit_price
          ? `¥${parseFloat(r.planned_exit_price).toFixed(3)}`
          : '-',
        r.planned_exit_price_formula ?? '-',
        pipsStr,
        pnlStr,
      ].join('\t');
    };

  const openHeaders = [
    'Open Time',
    'Instrument',
    'Units',
    'Layer',
    'Retracement',
    'Open Price',
    'Planned Exit',
    'Exit Formula',
    'Pips',
    'Unrealized PnL',
  ];

  // --- Render a pair of Long/Short tables ---
  const renderPair = (
    label: string,
    longData: TaskPosition[],
    longTotal: number,
    longSel: typeof closedLongSel,
    longPage: number,
    setLongPage: (p: number) => void,
    longRpp: number,
    setLongRpp: (r: number) => void,
    longRefetch: () => Promise<void>,
    longKey: string,
    shortData: TaskPosition[],
    shortTotal: number,
    shortSel: typeof closedLongSel,
    shortPage: number,
    setShortPage: (p: number) => void,
    shortRpp: number,
    setShortRpp: (r: number) => void,
    shortRefetch: () => Promise<void>,
    shortKey: string,
    columns: (dir: 'long' | 'short') => Column<TaskPosition>[],
    pnlLabel: string,
    pnlValue: number,
    copyHeaders: string[],
    longCopyRowFn: (r: TaskPosition) => string,
    shortCopyRowFn: (r: TaskPosition) => string,
    onConfigClick: () => void
  ) => {
    const longIds = longData.map((r) => String(r.id));
    const shortIds = shortData.map((r) => String(r.id));
    return (
      <Box sx={{ mb: 4 }}>
        <Box
          sx={{
            mb: 2,
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Typography variant="h6">{label}</Typography>
          </Box>
          <Typography
            variant="subtitle1"
            fontWeight="bold"
            color={pnlValue >= 0 ? 'success.main' : 'error.main'}
          >
            {pnlLabel}: {pnlValue >= 0 ? '+' : ''}¥{pnlValue.toFixed(2)}
          </Typography>
        </Box>
        <Box
          sx={{
            display: 'flex',
            flexDirection: 'column',
            gap: 3,
          }}
        >
          {/* Long */}
          <Box sx={{ flex: 1, minWidth: 0 }}>
            <Box
              sx={{
                mb: 1,
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
              }}
            >
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <Typography variant="subtitle1">
                  {t('tables.positions.longPositions')}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  ({longTotal})
                </Typography>
              </Box>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                <Tooltip title={t('common:columnConfig.configureColumns')}>
                  <IconButton
                    size="small"
                    onClick={onConfigClick}
                    aria-label={t('common:columnConfig.configureColumns')}
                  >
                    <SettingsIcon fontSize="small" />
                  </IconButton>
                </Tooltip>
                <TableSelectionToolbar
                  selectedCount={longSel.selectedRowIds.size}
                  onCopy={makeCopy(
                    longData,
                    longSel,
                    copyHeaders,
                    longCopyRowFn
                  )}
                  onSelectAll={() => longSel.selectAllOnPage(longIds)}
                  onReset={longSel.resetSelection}
                  onReload={makeReload(longKey, longRefetch)}
                  isReloading={!!reloading[longKey]}
                />
              </Box>
            </Box>
            <DataTable
              columns={columns('long')}
              data={longData}
              isLoading={isLoading}
              emptyMessage={t('tables.positions.noLongPositions')}
              defaultRowsPerPage={longRpp}
              rowsPerPageOptions={[longRpp]}
              tableMaxHeight="none"
              hidePagination
              selectable
              getRowId={getRowId}
              selectedRowIds={longSel.selectedRowIds}
              onToggleRow={longSel.toggleRowSelection}
              allPageSelected={longSel.isAllPageSelected(longIds)}
              indeterminate={longSel.isIndeterminate(longIds)}
              onToggleAll={makeToggleAll(longSel, longIds)}
              defaultOrderBy="entry_time"
              defaultOrder="desc"
              fillEmptyRows
            />
            <TablePagination
              component="div"
              count={longTotal}
              page={longPage}
              onPageChange={(_e, p) => setLongPage(p)}
              rowsPerPage={longRpp}
              onRowsPerPageChange={(e) => {
                setLongRpp(parseInt(e.target.value, 10));
                setLongPage(0);
              }}
              rowsPerPageOptions={[10, 50, 100, 200]}
            />
          </Box>
          {/* Short */}
          <Box sx={{ flex: 1, minWidth: 0 }}>
            <Box
              sx={{
                mb: 1,
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
              }}
            >
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <Typography variant="subtitle1">
                  {t('tables.positions.shortPositions')}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  ({shortTotal})
                </Typography>
              </Box>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                <Tooltip title={t('common:columnConfig.configureColumns')}>
                  <IconButton
                    size="small"
                    onClick={onConfigClick}
                    aria-label={t('common:columnConfig.configureColumns')}
                  >
                    <SettingsIcon fontSize="small" />
                  </IconButton>
                </Tooltip>
                <TableSelectionToolbar
                  selectedCount={shortSel.selectedRowIds.size}
                  onCopy={makeCopy(
                    shortData,
                    shortSel,
                    copyHeaders,
                    shortCopyRowFn
                  )}
                  onSelectAll={() => shortSel.selectAllOnPage(shortIds)}
                  onReset={shortSel.resetSelection}
                  onReload={makeReload(shortKey, shortRefetch)}
                  isReloading={!!reloading[shortKey]}
                />
              </Box>
            </Box>
            <DataTable
              columns={columns('short')}
              data={shortData}
              isLoading={isLoading}
              emptyMessage={t('tables.positions.noShortPositions')}
              defaultRowsPerPage={shortRpp}
              rowsPerPageOptions={[shortRpp]}
              tableMaxHeight="none"
              hidePagination
              selectable
              getRowId={getRowId}
              selectedRowIds={shortSel.selectedRowIds}
              onToggleRow={shortSel.toggleRowSelection}
              allPageSelected={shortSel.isAllPageSelected(shortIds)}
              indeterminate={shortSel.isIndeterminate(shortIds)}
              onToggleAll={makeToggleAll(shortSel, shortIds)}
              defaultOrderBy="entry_time"
              defaultOrder="desc"
              fillEmptyRows
            />
            <TablePagination
              component="div"
              count={shortTotal}
              page={shortPage}
              onPageChange={(_e, p) => setShortPage(p)}
              rowsPerPage={shortRpp}
              onRowsPerPageChange={(e) => {
                setShortRpp(parseInt(e.target.value, 10));
                setShortPage(0);
              }}
              rowsPerPageOptions={[10, 50, 100, 200]}
            />
          </Box>
        </Box>
      </Box>
    );
  };

  if (error) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="error">{error.message}</Alert>
      </Box>
    );
  }

  return (
    <Box sx={{ p: 3 }}>
      {renderPair(
        t('tables.positions.closedPositions'),
        closedLongPos,
        closedLongTotal,
        closedLongSel,
        closedLongPage,
        setClosedLongPage,
        closedLongRpp,
        setClosedLongRpp,
        rCL,
        'cl',
        closedShortPos,
        closedShortTotal,
        closedShortSel,
        closedShortPage,
        setClosedShortPage,
        closedShortRpp,
        setClosedShortRpp,
        rCS,
        'cs',
        filteredClosedCols,
        t('tables.positions.totalRealizedPnl'),
        totalRealizedPnl,
        closedHeaders,
        closedRowFn('long'),
        closedRowFn('short'),
        () => setClosedColConfigOpen(true)
      )}
      {renderPair(
        t('tables.positions.openPositions'),
        openLongPos,
        openLongTotal,
        openLongSel,
        openLongPage,
        setOpenLongPage,
        openLongRpp,
        setOpenLongRpp,
        rOL,
        'ol',
        openShortPos,
        openShortTotal,
        openShortSel,
        openShortPage,
        setOpenShortPage,
        openShortRpp,
        setOpenShortRpp,
        rOS,
        'os',
        filteredOpenCols,
        t('tables.positions.totalUnrealizedPnl'),
        totalUnrealizedPnl,
        openHeaders,
        openRowFn('long'),
        openRowFn('short'),
        () => setOpenColConfigOpen(true)
      )}
      <ColumnConfigDialog
        open={closedColConfigOpen}
        columns={closedColConfig}
        onClose={() => setClosedColConfigOpen(false)}
        onSave={updateClosedCols}
        onReset={resetClosedCols}
      />
      <ColumnConfigDialog
        open={openColConfigOpen}
        columns={openColConfig}
        onClose={() => setOpenColConfigOpen(false)}
        onSave={updateOpenCols}
        onReset={resetOpenCols}
      />
      <PositionLifecycleDialog
        open={lifecycleOpen}
        onClose={() => setLifecycleOpen(false)}
        taskId={String(taskId)}
        taskType={taskType}
        executionRunId={executionRunId}
        initialPositionId={lifecyclePositionId}
        positionData={lifecyclePosition}
      />
    </Box>
  );
};

export default TaskPositionsTable;
