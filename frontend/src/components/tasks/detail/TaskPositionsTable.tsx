/**
 * TaskPositionsTable Component
 *
 * Displays positions in one of three view modes:
 * - "all": Single table showing all positions (default)
 * - "byDirection": Two tables split by Long / Short
 * - "byStatus": Four tables split by Closed/Open × Long/Short (legacy layout)
 *
 * View mode preference is persisted to localStorage.
 */

import React, { useState, useCallback, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Box,
  Typography,
  Alert,
  TablePagination,
  IconButton,
  Tooltip,
  ToggleButtonGroup,
  ToggleButton,
  Chip,
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
import type { TaskType } from '../../../types/common';
import { useAuth } from '../../../contexts/AuthContext';
import { PositionLifecycleDialog } from './PositionLifecycleDialog';
import { ColumnConfigDialog } from '../../common/ColumnConfigDialog';
import {
  useColumnConfig,
  columnsToDefaults,
  applyColumnConfig,
} from '../../../hooks/useColumnConfig';
import {
  buildCopyHandler,
  type CopyValueExtractors,
} from '../../../utils/tableCopyUtils';
import { formatAppNumber } from '../../../utils/numberFormat';
import { formatDateTimeInTimezone } from '../../../utils/timezone';
import { TaskPositionFilterBar } from './TaskPositionFilterBar';
import { TaskPositionModeViews } from './TaskPositionModeViews';
import { useTaskPositionFilters } from './useTaskPositionFilters';
import { useTaskPositionViewMode } from './useTaskPositionViewMode';
import { useStrategies } from '../../../hooks/useStrategies';

interface TaskPositionsTableProps {
  taskId: string | number;
  taskType: TaskType;
  executionRunId?: string;
  enableRealTimeUpdates?: boolean;
  currentPrice?: number | null;
  pipSize?: number | null;
  strategyType?: string;
}

export const TaskPositionsTable: React.FC<TaskPositionsTableProps> = ({
  taskId,
  taskType,
  executionRunId,
  enableRealTimeUpdates = false,
  currentPrice,
  pipSize,
  strategyType,
}) => {
  const { t } = useTranslation('common');
  const { user } = useAuth();
  const { strategies } = useStrategies();
  const strategyCloseReasonLabels = useMemo(
    () =>
      strategies.find((strategy) => strategy.id === strategyType)?.capabilities
        ?.events?.close_reason_labels ?? {},
    [strategies, strategyType]
  );

  // --- View mode ---
  const { viewMode, handleViewModeChange } = useTaskPositionViewMode();

  // --- Pagination state (byStatus mode — 4 tables) ---
  const [closedLongPage, setClosedLongPage] = useState(0);
  const [closedShortPage, setClosedShortPage] = useState(0);
  const [openLongPage, setOpenLongPage] = useState(0);
  const [openShortPage, setOpenShortPage] = useState(0);
  const rpp = 10;
  const [closedLongRpp, setClosedLongRpp] = useState(rpp);
  const [closedShortRpp, setClosedShortRpp] = useState(rpp);
  const [openLongRpp, setOpenLongRpp] = useState(rpp);
  const [openShortRpp, setOpenShortRpp] = useState(rpp);

  // --- Pagination state (byDirection mode — 2 tables) ---
  const [longPage, setLongPage] = useState(0);
  const [shortPage, setShortPage] = useState(0);
  const [longRpp, setLongRpp] = useState(rpp);
  const [shortRpp, setShortRpp] = useState(rpp);

  // --- Pagination state (all mode — 1 table) ---
  const [allPage, setAllPage] = useState(0);
  const [allRpp, setAllRpp] = useState(25);

  // --- Reload state ---
  const [reloading, setReloading] = useState<Record<string, boolean>>({});

  const {
    cycleIdFilter,
    setCycleIdFilter,
    hasCycleIdFilter,
    isCycleIdFilterValid,
    effectiveCycleId,
    positionIdFilter,
    setPositionIdFilter,
    hasPositionIdFilter,
    isPositionIdFilterValid,
    effectivePositionId,
    dateFrom,
    setDateFrom,
    dateTo,
    setDateTo,
    rangeFrom,
    rangeTo,
  } = useTaskPositionFilters();

  // --- Selection ---
  const closedLongSel = useTableRowSelection();
  const closedShortSel = useTableRowSelection();
  const openLongSel = useTableRowSelection();
  const openShortSel = useTableRowSelection();
  const longSel = useTableRowSelection();
  const shortSel = useTableRowSelection();
  const allSel = useTableRowSelection();

  // --- Data fetching ---
  // byStatus mode: 4 queries (only active when viewMode === 'byStatus')
  const {
    positions: closedLongPos,
    totalCount: closedLongTotal,
    isLoading: cl1,
    error: ce1,
    refresh: rCL,
  } = useTaskPositions({
    taskId,
    taskType,
    executionRunId,
    status: 'closed',
    direction: 'long',
    page: closedLongPage + 1,
    pageSize: closedLongRpp,
    cycleId: effectiveCycleId || undefined,
    positionId: effectivePositionId || undefined,
    rangeFrom,
    rangeTo,
    enableRealTimeUpdates: enableRealTimeUpdates && viewMode === 'byStatus',
  });
  const {
    positions: closedShortPos,
    totalCount: closedShortTotal,
    isLoading: cl2,
    error: ce2,
    refresh: rCS,
  } = useTaskPositions({
    taskId,
    taskType,
    executionRunId,
    status: 'closed',
    direction: 'short',
    page: closedShortPage + 1,
    pageSize: closedShortRpp,
    cycleId: effectiveCycleId || undefined,
    positionId: effectivePositionId || undefined,
    rangeFrom,
    rangeTo,
    enableRealTimeUpdates: enableRealTimeUpdates && viewMode === 'byStatus',
  });
  const {
    positions: openLongPos,
    totalCount: openLongTotal,
    isLoading: cl3,
    error: ce3,
    refresh: rOL,
  } = useTaskPositions({
    taskId,
    taskType,
    executionRunId,
    status: 'open',
    direction: 'long',
    page: openLongPage + 1,
    pageSize: openLongRpp,
    cycleId: effectiveCycleId || undefined,
    positionId: effectivePositionId || undefined,
    rangeFrom,
    rangeTo,
    enableRealTimeUpdates: enableRealTimeUpdates && viewMode === 'byStatus',
  });
  const {
    positions: openShortPos,
    totalCount: openShortTotal,
    isLoading: cl4,
    error: ce4,
    refresh: rOS,
  } = useTaskPositions({
    taskId,
    taskType,
    executionRunId,
    status: 'open',
    direction: 'short',
    page: openShortPage + 1,
    pageSize: openShortRpp,
    cycleId: effectiveCycleId || undefined,
    positionId: effectivePositionId || undefined,
    rangeFrom,
    rangeTo,
    enableRealTimeUpdates: enableRealTimeUpdates && viewMode === 'byStatus',
  });

  // byDirection mode: 2 queries
  const {
    positions: longPos,
    totalCount: longTotal,
    isLoading: ld1,
    error: le1,
    refresh: rLong,
  } = useTaskPositions({
    taskId,
    taskType,
    executionRunId,
    direction: 'long',
    page: longPage + 1,
    pageSize: longRpp,
    cycleId: effectiveCycleId || undefined,
    positionId: effectivePositionId || undefined,
    rangeFrom,
    rangeTo,
    enableRealTimeUpdates: enableRealTimeUpdates && viewMode === 'byDirection',
  });
  const {
    positions: shortPos,
    totalCount: shortTotal,
    isLoading: ld2,
    error: le2,
    refresh: rShort,
  } = useTaskPositions({
    taskId,
    taskType,
    executionRunId,
    direction: 'short',
    page: shortPage + 1,
    pageSize: shortRpp,
    cycleId: effectiveCycleId || undefined,
    positionId: effectivePositionId || undefined,
    rangeFrom,
    rangeTo,
    enableRealTimeUpdates: enableRealTimeUpdates && viewMode === 'byDirection',
  });

  // all mode: 1 query
  const {
    positions: allPos,
    totalCount: allTotal,
    isLoading: ad1,
    error: ae1,
    refresh: rAll,
  } = useTaskPositions({
    taskId,
    taskType,
    executionRunId,
    page: allPage + 1,
    pageSize: allRpp,
    cycleId: effectiveCycleId || undefined,
    positionId: effectivePositionId || undefined,
    rangeFrom,
    rangeTo,
    enableRealTimeUpdates: enableRealTimeUpdates && viewMode === 'all',
  });

  const isLoading =
    viewMode === 'byStatus'
      ? cl1 || cl2 || cl3 || cl4
      : viewMode === 'byDirection'
        ? ld1 || ld2
        : ad1;
  const error =
    viewMode === 'byStatus'
      ? ce1 || ce2 || ce3 || ce4
      : viewMode === 'byDirection'
        ? le1 || le2
        : ae1;

  // --- PnL summary ---
  const {
    summary: {
      pnl: { realized: totalRealizedPnl, unrealized: totalUnrealizedPnl },
    },
    refresh: refreshPnl,
  } = useTaskSummary(String(taskId), taskType, executionRunId);

  const prevRealTimeRef = React.useRef(enableRealTimeUpdates);
  React.useEffect(() => {
    if (prevRealTimeRef.current && !enableRealTimeUpdates) {
      void refreshPnl();
    }
    prevRealTimeRef.current = enableRealTimeUpdates;
  }, [enableRealTimeUpdates, refreshPnl]);
  React.useEffect(() => {
    if (!enableRealTimeUpdates) return;
    const interval = setInterval(() => {
      void refreshPnl();
    }, 10000);
    return () => clearInterval(interval);
  }, [enableRealTimeUpdates, refreshPnl]);

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
    formatDateTimeInTimezone(ts, user?.timezone || 'UTC', user?.language, {
      includeSeconds: true,
      includeTimezone: true,
    });

  const formatPrice = (
    value: string | number | null | undefined,
    digits = 3
  ): string => {
    if (value == null || value === '') return '-';
    const numericValue =
      typeof value === 'string' ? parseFloat(value) : Number(value);
    if (!Number.isFinite(numericValue)) return '-';
    return formatAppNumber(numericValue, {
      minimumFractionDigits: digits,
      maximumFractionDigits: digits,
      useGrouping: false,
    });
  };

  const formatPips = (value: number): string =>
    formatAppNumber(value, {
      minimumFractionDigits: 1,
      maximumFractionDigits: 1,
      signed: value >= 0,
      useGrouping: false,
    });

  const formatSignedYen = (value: number): string =>
    `¥${formatAppNumber(value, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
      signed: true,
    })}`;

  // --- Shared column fragments ---
  const idCol: Column<TaskPosition> = {
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
                handleOpenLifecycle(String(r.id), r);
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
  };

  const directionCol: Column<TaskPosition> = {
    id: 'direction',
    label: t('tables.positions.direction'),
    width: 80,
    minWidth: 60,
    render: (r) => (
      <Chip
        label={
          r.direction === 'long'
            ? t('tables.positions.long')
            : t('tables.positions.short')
        }
        size="small"
        color={r.direction === 'long' ? 'success' : 'error'}
        variant="outlined"
      />
    ),
  };

  const replayCol: Column<TaskPosition> = {
    id: 'replayed_at',
    label: 'Replay',
    width: 105,
    minWidth: 90,
    render: (r) =>
      r.replayed_at ? (
        <Tooltip title={`Replayed at ${formatTimestamp(r.replayed_at)}`}>
          <Chip label="REPLAY" size="small" color="warning" variant="filled" />
        </Tooltip>
      ) : (
        '-'
      ),
  };

  const statusCol: Column<TaskPosition> = {
    id: 'is_open',
    label: t('tables.positions.status'),
    width: 90,
    minWidth: 70,
    render: (r) => (
      <Chip
        label={
          r.is_open ? t('tables.positions.open') : t('tables.positions.closed')
        }
        size="small"
        color={r.is_open ? 'info' : 'default'}
        variant="outlined"
      />
    ),
  };

  const entryTimeCol: Column<TaskPosition> = {
    id: 'entry_time',
    label: t('tables.positions.openTimestamp'),
    width: 180,
    minWidth: 140,
    render: (r) => (r.entry_time ? formatTimestamp(r.entry_time) : '-'),
  };
  const exitTimeCol: Column<TaskPosition> = {
    id: 'exit_time',
    label: t('tables.positions.closeTimestamp'),
    width: 180,
    minWidth: 140,
    render: (r) => (r.exit_time ? formatTimestamp(r.exit_time) : '-'),
  };
  const instrumentCol: Column<TaskPosition> = {
    id: 'instrument',
    label: t('tables.positions.instrument'),
    width: 110,
    minWidth: 80,
  };
  const unitsCol: Column<TaskPosition> = {
    id: 'units',
    label: t('tables.positions.units'),
    width: 90,
    minWidth: 70,
    align: 'right',
    render: (r) => formatAppNumber(Math.abs(r.units)),
  };
  const layerCol: Column<TaskPosition> = {
    id: 'layer_index',
    label: t('tables.positions.layer'),
    width: 70,
    minWidth: 50,
    align: 'right',
    render: (r) => (r.layer_index != null ? `L${r.layer_index}` : '-'),
  };
  const retracementCol: Column<TaskPosition> = {
    id: 'retracement_count',
    label: t('tables.positions.retracement'),
    width: 70,
    minWidth: 50,
    align: 'right',
    render: (r) =>
      r.retracement_count != null ? `R${r.retracement_count}` : '-',
  };
  const entryPriceCol: Column<TaskPosition> = {
    id: 'entry_price',
    label: t('tables.positions.openPrice'),
    width: 110,
    minWidth: 80,
    align: 'right',
    render: (r) => (r.entry_price ? `¥${formatPrice(r.entry_price, 3)}` : '-'),
  };
  const exitPriceCol: Column<TaskPosition> = {
    id: 'exit_price',
    label: t('tables.positions.closePrice'),
    width: 110,
    minWidth: 80,
    align: 'right',
    render: (r) => (r.exit_price ? `¥${formatPrice(r.exit_price, 3)}` : '-'),
  };
  const plannedExitPriceCol: Column<TaskPosition> = {
    id: 'planned_exit_price',
    label: t('tables.positions.plannedExitPrice'),
    width: 130,
    minWidth: 90,
    align: 'right',
    render: (r) =>
      r.planned_exit_price ? `¥${formatPrice(r.planned_exit_price, 3)}` : '-',
  };
  const plannedExitFormulaCol: Column<TaskPosition> = {
    id: 'planned_exit_price_formula',
    label: t('tables.positions.plannedExitPriceFormula'),
    width: 220,
    minWidth: 150,
    render: (r) => r.planned_exit_price_formula ?? '-',
  };
  const adversePipsCol: Column<TaskPosition> = {
    id: 'adverse_pips',
    label: t('tables.positions.adversePips'),
    width: 100,
    minWidth: 70,
    align: 'right',
    render: (r) =>
      r.adverse_pips != null ? formatPrice(r.adverse_pips, 1) : '-',
  };
  const stopLossPriceCol: Column<TaskPosition> = {
    id: 'stop_loss_price',
    label: t('tables.positions.stopLossPrice'),
    width: 130,
    minWidth: 90,
    align: 'right',
    render: (r) =>
      r.stop_loss_price ? `¥${formatPrice(r.stop_loss_price, 3)}` : '-',
  };
  const oandaTradeIdCol: Column<TaskPosition> = {
    id: 'oanda_trade_id',
    label: 'OANDA Trade',
    width: 150,
    minWidth: 120,
    render: (r) =>
      r.oanda_trade_id ? (
        <Typography variant="body2" fontFamily="monospace">
          {r.oanda_trade_id}
        </Typography>
      ) : (
        '-'
      ),
  };
  const isRebuildCol: Column<TaskPosition> = {
    id: 'is_rebuild',
    label: t('tables.positions.isRebuild'),
    width: 80,
    minWidth: 60,
    render: (r) =>
      r.is_rebuild ? (
        <Chip
          label={t('tables.positions.rebuild')}
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
  };

  const closeReasonCol: Column<TaskPosition> = {
    id: 'close_reason',
    label: t('tables.positions.closeReason'),
    width: 120,
    minWidth: 90,
    render: (r) => {
      if (!r.close_reason) return '-';

      // Map close_reason values to i18n keys
      const closeReasonKeyMap: Record<string, string> = {
        normal: 'closeReasonNormal',
        stop_loss: 'closeReasonStopLoss',
        shrink: 'closeReasonShrink',
        volatility_lock: 'closeReasonVolatilityLock',
        margin_protection: 'closeReasonMarginProtection',
        tp: 'closeReasonTp',
        counter_tp: 'closeReasonCounterTp',
        layer_initial_tp: 'closeReasonLayerInitialTp',
        lock_hedge_neutralize: 'closeReasonLockHedgeNeutralize',
        shrink_entered: 'closeReasonShrinkEntered',
        lock_entered: 'closeReasonLockEntered',
        lock_released: 'closeReasonLockReleased',
      };

      const i18nKey = closeReasonKeyMap[r.close_reason];
      const label =
        strategyCloseReasonLabels[r.close_reason] ??
        (i18nKey
          ? t(`tables.positions.${i18nKey}`)
          : r.close_reason.replace(/_/g, ' '));

      if (r.close_reason === 'normal') {
        return (
          <Chip
            label={label}
            size="small"
            color="success"
            variant="outlined"
            sx={{
              height: 22,
              '& .MuiChip-label': { px: 0.75, fontSize: '0.75rem' },
            }}
          />
        );
      }
      return (
        <Chip
          label={`⚠ ${label}`}
          size="small"
          color="warning"
          variant="filled"
          sx={{
            height: 22,
            '& .MuiChip-label': { px: 0.75, fontSize: '0.75rem' },
          }}
        />
      );
    },
  };

  /** Pips column — uses row direction for calculation when knownDir is not provided. */
  const pipsCol = (knownDir?: 'long' | 'short'): Column<TaskPosition> => ({
    id: 'pips',
    label: t('tables.positions.pips'),
    width: 90,
    minWidth: 70,
    align: 'right',
    render: (r) => {
      const dir = knownDir ?? r.direction;
      if (!pipSize) return '-';
      if (r.exit_price && r.entry_price) {
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
            {formatPips(pips)}
          </Typography>
        );
      }
      if (currentPrice != null && r.entry_price) {
        const ep = parseFloat(r.entry_price);
        const pips =
          (dir === 'long' ? currentPrice - ep : ep - currentPrice) / pipSize;
        return (
          <Typography
            variant="body2"
            color={pips >= 0 ? 'success.main' : 'error.main'}
            fontWeight="bold"
          >
            {formatPips(pips)}
          </Typography>
        );
      }
      return '-';
    },
  });

  /** Unified PnL column — shows realized for closed, unrealized for open. */
  const pnlCol = (knownDir?: 'long' | 'short'): Column<TaskPosition> => ({
    id: 'pnl',
    label:
      t('tables.positions.realizedPnl') +
      ' / ' +
      t('tables.positions.unrealizedPnl'),
    width: 130,
    minWidth: 100,
    align: 'right',
    render: (r) => {
      const dir = knownDir ?? r.direction;
      if (!r.is_open && r.exit_price && r.entry_price) {
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
            {formatSignedYen(val)}
          </Typography>
        );
      }
      if (r.is_open && currentPrice != null && r.entry_price) {
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
            {formatSignedYen(val)}
          </Typography>
        );
      }
      return '-';
    },
  });

  const realizedPnlCol = (dir: 'long' | 'short'): Column<TaskPosition> => ({
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
          {formatSignedYen(val)}
        </Typography>
      );
    },
  });

  const unrealizedPnlCol = (dir: 'long' | 'short'): Column<TaskPosition> => ({
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
          {formatSignedYen(val)}
        </Typography>
      );
    },
  });

  // --- Column sets for each mode ---
  /** byStatus: closed positions (direction known) */
  const closedCols = (dir: 'long' | 'short'): Column<TaskPosition>[] => [
    idCol,
    replayCol,
    entryTimeCol,
    exitTimeCol,
    instrumentCol,
    unitsCol,
    layerCol,
    retracementCol,
    adversePipsCol,
    entryPriceCol,
    exitPriceCol,
    plannedExitPriceCol,
    plannedExitFormulaCol,
    oandaTradeIdCol,
    stopLossPriceCol,
    pipsCol(dir),
    realizedPnlCol(dir),
    closeReasonCol,
    isRebuildCol,
  ];
  /** byStatus: open positions (direction known) */
  const openCols = (dir: 'long' | 'short'): Column<TaskPosition>[] => [
    idCol,
    replayCol,
    entryTimeCol,
    instrumentCol,
    unitsCol,
    layerCol,
    retracementCol,
    adversePipsCol,
    entryPriceCol,
    plannedExitPriceCol,
    plannedExitFormulaCol,
    oandaTradeIdCol,
    stopLossPriceCol,
    pipsCol(dir),
    unrealizedPnlCol(dir),
    isRebuildCol,
  ];
  /** byDirection: all statuses for a known direction */
  const dirCols = (dir: 'long' | 'short'): Column<TaskPosition>[] => [
    idCol,
    replayCol,
    statusCol,
    entryTimeCol,
    exitTimeCol,
    instrumentCol,
    unitsCol,
    layerCol,
    retracementCol,
    adversePipsCol,
    entryPriceCol,
    exitPriceCol,
    plannedExitPriceCol,
    plannedExitFormulaCol,
    oandaTradeIdCol,
    stopLossPriceCol,
    pipsCol(dir),
    pnlCol(dir),
    closeReasonCol,
    isRebuildCol,
  ];
  /** all: every position */
  const allCols = (): Column<TaskPosition>[] => [
    idCol,
    replayCol,
    directionCol,
    statusCol,
    entryTimeCol,
    exitTimeCol,
    instrumentCol,
    unitsCol,
    layerCol,
    retracementCol,
    adversePipsCol,
    entryPriceCol,
    exitPriceCol,
    plannedExitPriceCol,
    plannedExitFormulaCol,
    oandaTradeIdCol,
    stopLossPriceCol,
    pipsCol(),
    pnlCol(),
    closeReasonCol,
    isRebuildCol,
  ];

  // --- Column config ---
  const [closedColConfigOpen, setClosedColConfigOpen] = useState(false);
  const [openColConfigOpen, setOpenColConfigOpen] = useState(false);
  const [dirColConfigOpen, setDirColConfigOpen] = useState(false);
  const [allColConfigOpen, setAllColConfigOpen] = useState(false);
  const isSnowballStrategy = strategyType === 'snowball';
  const snowballOnlyColumnIds = ['layer_index', 'retracement_count'];

  const closedColDefaults = columnsToDefaults(closedCols('long')).map((c) =>
    [
      'planned_exit_price_formula',
      'stop_loss_price',
      'is_rebuild',
      'oanda_trade_id',
      'replayed_at',
      ...(!isSnowballStrategy ? snowballOnlyColumnIds : []),
    ].includes(c.id)
      ? { ...c, visible: false }
      : c
  );
  const openColDefaults = columnsToDefaults(openCols('long')).map((c) =>
    [
      'planned_exit_price_formula',
      'stop_loss_price',
      'is_rebuild',
      'oanda_trade_id',
      'replayed_at',
      ...(!isSnowballStrategy ? snowballOnlyColumnIds : []),
    ].includes(c.id)
      ? { ...c, visible: false }
      : c
  );
  const dirColDefaults = columnsToDefaults(dirCols('long')).map((c) =>
    [
      'planned_exit_price_formula',
      'stop_loss_price',
      'is_rebuild',
      'oanda_trade_id',
      'replayed_at',
      ...(!isSnowballStrategy ? snowballOnlyColumnIds : []),
    ].includes(c.id)
      ? { ...c, visible: false }
      : c
  );
  const allColDefaults = columnsToDefaults(allCols()).map((c) =>
    [
      'planned_exit_price_formula',
      'stop_loss_price',
      'is_rebuild',
      'oanda_trade_id',
      'replayed_at',
      ...(!isSnowballStrategy ? snowballOnlyColumnIds : []),
    ].includes(c.id)
      ? { ...c, visible: false }
      : c
  );

  const {
    columns: closedColConfig,
    updateColumns: updateClosedCols,
    resetToDefaults: resetClosedCols,
  } = useColumnConfig(
    isSnowballStrategy ? 'positions_closed' : 'positions_closed_generic',
    closedColDefaults
  );
  const {
    columns: openColConfig,
    updateColumns: updateOpenCols,
    resetToDefaults: resetOpenCols,
  } = useColumnConfig(
    isSnowballStrategy ? 'positions_open' : 'positions_open_generic',
    openColDefaults
  );
  const {
    columns: dirColConfig,
    updateColumns: updateDirCols,
    resetToDefaults: resetDirCols,
  } = useColumnConfig(
    isSnowballStrategy ? 'positions_dir' : 'positions_dir_generic',
    dirColDefaults
  );
  const {
    columns: allColConfig,
    updateColumns: updateAllCols,
    resetToDefaults: resetAllCols,
  } = useColumnConfig(
    isSnowballStrategy ? 'positions_all' : 'positions_all_generic',
    allColDefaults
  );

  const filteredClosedCols = (dir: 'long' | 'short') =>
    applyColumnConfig(closedCols(dir), closedColConfig);
  const filteredOpenCols = (dir: 'long' | 'short') =>
    applyColumnConfig(openCols(dir), openColConfig);
  const filteredDirCols = (dir: 'long' | 'short') =>
    applyColumnConfig(dirCols(dir), dirColConfig);
  const filteredAllCols = () => applyColumnConfig(allCols(), allColConfig);

  // --- Helpers ---
  const makeToggleAll = (sel: typeof closedLongSel, ids: string[]) => () => {
    if (sel.isAllPageSelected(ids)) {
      for (const id of ids) {
        if (sel.selectedRowIds.has(id)) sel.toggleRowSelection(id);
      }
    } else sel.selectAllOnPage(ids);
  };

  const makeReload =
    (key: string, refresh: () => Promise<unknown>) => async () => {
      setReloading((p) => ({ ...p, [key]: true }));
      await refresh();
      setReloading((p) => ({ ...p, [key]: false }));
    };

  const makeCopy =
    (
      positions: TaskPosition[],
      sel: typeof closedLongSel,
      visCols: Column<TaskPosition>[],
      extractors: CopyValueExtractors<TaskPosition>,
      displayIds: string[]
    ) =>
    () => {
      const posMap = new Map(positions.map((p) => [String(p.id), p]));
      const { headers, formatRow } = buildCopyHandler(
        visCols,
        extractors,
        posMap
      );
      sel.copySelectedRows(headers, formatRow, displayIds);
    };

  // --- Copy value extractors for each view mode ---
  const closedExtractors = (
    dir: 'long' | 'short'
  ): CopyValueExtractors<TaskPosition> => ({
    id: (r) => (r.id ? String(r.id).slice(0, 8) : '-'),
    replayed_at: (r) => (r.replayed_at ? formatTimestamp(r.replayed_at) : '-'),
    entry_time: (r) => (r.entry_time ? formatTimestamp(r.entry_time) : '-'),
    exit_time: (r) => (r.exit_time ? formatTimestamp(r.exit_time) : '-'),
    instrument: (r) => r.instrument ?? '-',
    units: (r) => formatAppNumber(Math.abs(r.units)),
    layer_index: (r) => (r.layer_index != null ? String(r.layer_index) : '-'),
    retracement_count: (r) =>
      r.retracement_count != null ? String(r.retracement_count) : '-',
    entry_price: (r) =>
      r.entry_price ? `¥${formatPrice(r.entry_price, 3)}` : '-',
    exit_price: (r) =>
      r.exit_price ? `¥${formatPrice(r.exit_price, 3)}` : '-',
    planned_exit_price: (r) =>
      r.planned_exit_price ? `¥${formatPrice(r.planned_exit_price, 3)}` : '-',
    planned_exit_price_formula: (r) => r.planned_exit_price_formula ?? '-',
    oanda_trade_id: (r) => r.oanda_trade_id ?? '-',
    pips: (r) => {
      const ep = r.entry_price ? parseFloat(r.entry_price) : null;
      const xp = r.exit_price ? parseFloat(r.exit_price) : null;
      if (ep != null && xp != null && pipSize) {
        const pips = (dir === 'long' ? xp - ep : ep - xp) / pipSize;
        if (Number.isFinite(pips)) return formatPrice(pips, 1);
      }
      return '-';
    },
    realized_pnl: (r) => {
      const ep = r.entry_price ? parseFloat(r.entry_price) : null;
      const xp = r.exit_price ? parseFloat(r.exit_price) : null;
      if (ep != null && xp != null) {
        const u = Math.abs(r.units ?? 0);
        const val = dir === 'long' ? (xp - ep) * u : (ep - xp) * u;
        return formatAppNumber(val, {
          minimumFractionDigits: 2,
          maximumFractionDigits: 2,
        });
      }
      return '-';
    },
    close_reason: (r) => r.close_reason ?? '-',
    stop_loss_price: (r) =>
      r.stop_loss_price ? `¥${formatPrice(r.stop_loss_price, 3)}` : '-',
    is_rebuild: (r) => (r.is_rebuild ? 'Yes' : '-'),
  });

  const openExtractors = (
    dir: 'long' | 'short'
  ): CopyValueExtractors<TaskPosition> => ({
    id: (r) => (r.id ? String(r.id).slice(0, 8) : '-'),
    replayed_at: (r) => (r.replayed_at ? formatTimestamp(r.replayed_at) : '-'),
    entry_time: (r) => (r.entry_time ? formatTimestamp(r.entry_time) : '-'),
    instrument: (r) => r.instrument ?? '-',
    units: (r) => formatAppNumber(Math.abs(r.units)),
    layer_index: (r) => (r.layer_index != null ? String(r.layer_index) : '-'),
    retracement_count: (r) =>
      r.retracement_count != null ? String(r.retracement_count) : '-',
    entry_price: (r) =>
      r.entry_price ? `¥${formatPrice(r.entry_price, 3)}` : '-',
    planned_exit_price: (r) =>
      r.planned_exit_price ? `¥${formatPrice(r.planned_exit_price, 3)}` : '-',
    planned_exit_price_formula: (r) => r.planned_exit_price_formula ?? '-',
    oanda_trade_id: (r) => r.oanda_trade_id ?? '-',
    pips: (r) => {
      const ep = r.entry_price ? parseFloat(r.entry_price) : null;
      if (currentPrice != null && ep != null && pipSize) {
        const pips =
          (dir === 'long' ? currentPrice - ep : ep - currentPrice) / pipSize;
        if (Number.isFinite(pips)) return formatPrice(pips, 1);
      }
      return '-';
    },
    unrealized_pnl: (r) => {
      const ep = r.entry_price ? parseFloat(r.entry_price) : null;
      if (currentPrice != null && ep != null) {
        const u = Math.abs(r.units ?? 0);
        const val =
          dir === 'long' ? (currentPrice - ep) * u : (ep - currentPrice) * u;
        return formatAppNumber(val, {
          minimumFractionDigits: 2,
          maximumFractionDigits: 2,
        });
      }
      return '-';
    },
    stop_loss_price: (r) =>
      r.stop_loss_price ? `¥${formatPrice(r.stop_loss_price, 3)}` : '-',
    is_rebuild: (r) => (r.is_rebuild ? 'Yes' : '-'),
  });

  const genericExtractors: CopyValueExtractors<TaskPosition> = {
    id: (r) => (r.id ? String(r.id).slice(0, 8) : '-'),
    replayed_at: (r) => (r.replayed_at ? formatTimestamp(r.replayed_at) : '-'),
    direction: (r) => r.direction ?? '-',
    is_open: (r) => (r.is_open ? 'Open' : 'Closed'),
    entry_time: (r) => (r.entry_time ? formatTimestamp(r.entry_time) : '-'),
    exit_time: (r) => (r.exit_time ? formatTimestamp(r.exit_time) : '-'),
    instrument: (r) => r.instrument ?? '-',
    units: (r) => formatAppNumber(Math.abs(r.units)),
    layer_index: (r) => (r.layer_index != null ? String(r.layer_index) : '-'),
    retracement_count: (r) =>
      r.retracement_count != null ? String(r.retracement_count) : '-',
    entry_price: (r) =>
      r.entry_price ? `¥${formatPrice(r.entry_price, 3)}` : '-',
    exit_price: (r) =>
      r.exit_price ? `¥${formatPrice(r.exit_price, 3)}` : '-',
    planned_exit_price: (r) =>
      r.planned_exit_price ? `¥${formatPrice(r.planned_exit_price, 3)}` : '-',
    planned_exit_price_formula: (r) => r.planned_exit_price_formula ?? '-',
    oanda_trade_id: (r) => r.oanda_trade_id ?? '-',
    pips: (r) => {
      const dir = r.direction;
      const ep = r.entry_price ? parseFloat(r.entry_price) : null;
      const xp = r.exit_price ? parseFloat(r.exit_price) : null;
      if (ep != null && xp != null && pipSize) {
        const pips = (dir === 'long' ? xp - ep : ep - xp) / pipSize;
        if (Number.isFinite(pips)) return formatPrice(pips, 1);
      }
      if (r.is_open && currentPrice != null && ep != null && pipSize) {
        const pips =
          (dir === 'long' ? currentPrice - ep : ep - currentPrice) / pipSize;
        if (Number.isFinite(pips)) return formatPrice(pips, 1);
      }
      return '-';
    },
    pnl: (r) => {
      const dir = r.direction;
      const ep = r.entry_price ? parseFloat(r.entry_price) : null;
      const xp = r.exit_price ? parseFloat(r.exit_price) : null;
      const u = Math.abs(r.units ?? 0);
      if (!r.is_open && ep != null && xp != null) {
        return formatAppNumber(dir === 'long' ? (xp - ep) * u : (ep - xp) * u, {
          minimumFractionDigits: 2,
          maximumFractionDigits: 2,
        });
      }
      if (r.is_open && currentPrice != null && ep != null) {
        return formatAppNumber(
          dir === 'long' ? (currentPrice - ep) * u : (ep - currentPrice) * u,
          {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
          }
        );
      }
      return '-';
    },
    close_reason: (r) => r.close_reason ?? '-',
    stop_loss_price: (r) =>
      r.stop_loss_price ? `¥${formatPrice(r.stop_loss_price, 3)}` : '-',
    is_rebuild: (r) => (r.is_rebuild ? 'Yes' : '-'),
  };

  // --- Render a pair of Long/Short tables (used by byStatus mode) ---
  const renderPair = (
    label: string,
    longData: TaskPosition[],
    longTotal: number,
    longSelObj: typeof closedLongSel,
    longPageVal: number,
    setLongPageFn: (p: number) => void,
    longRppVal: number,
    setLongRppFn: (r: number) => void,
    longRefetch: () => Promise<unknown>,
    longKey: string,
    shortData: TaskPosition[],
    shortTotal: number,
    shortSelObj: typeof closedLongSel,
    shortPageVal: number,
    setShortPageFn: (p: number) => void,
    shortRppVal: number,
    setShortRppFn: (r: number) => void,
    shortRefetch: () => Promise<unknown>,
    shortKey: string,
    columns: (dir: 'long' | 'short') => Column<TaskPosition>[],
    pnlLabel: string,
    pnlValue: number,
    extractors: (dir: 'long' | 'short') => CopyValueExtractors<TaskPosition>,
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
          <Typography variant="h6">{label}</Typography>
          <Typography
            variant="subtitle1"
            fontWeight="bold"
            color={pnlValue >= 0 ? 'success.main' : 'error.main'}
          >
            {pnlLabel}: {formatSignedYen(pnlValue)}
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
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
                  selectedCount={longSelObj.selectedRowIds.size}
                  onCopy={makeCopy(
                    longData,
                    longSelObj,
                    columns('long'),
                    extractors('long'),
                    longIds
                  )}
                  onSelectAll={() => longSelObj.selectAllOnPage(longIds)}
                  onReset={longSelObj.resetSelection}
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
              defaultRowsPerPage={longRppVal}
              rowsPerPageOptions={[longRppVal]}
              tableMaxHeight="none"
              hidePagination
              selectable
              getRowId={getRowId}
              selectedRowIds={longSelObj.selectedRowIds}
              onToggleRow={longSelObj.toggleRowSelection}
              allPageSelected={longSelObj.isAllPageSelected(longIds)}
              indeterminate={longSelObj.isIndeterminate(longIds)}
              onToggleAll={makeToggleAll(longSelObj, longIds)}
              defaultOrderBy="entry_time"
              defaultOrder="desc"
              fillEmptyRows
            />
            <TablePagination
              component="div"
              count={longTotal}
              page={longPageVal}
              onPageChange={(_e, p) => setLongPageFn(p)}
              rowsPerPage={longRppVal}
              onRowsPerPageChange={(e) => {
                setLongRppFn(parseInt(e.target.value, 10));
                setLongPageFn(0);
              }}
              rowsPerPageOptions={[10, 25, 50, 100, 200, 500, 1000]}
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
                  selectedCount={shortSelObj.selectedRowIds.size}
                  onCopy={makeCopy(
                    shortData,
                    shortSelObj,
                    columns('short'),
                    extractors('short'),
                    shortIds
                  )}
                  onSelectAll={() => shortSelObj.selectAllOnPage(shortIds)}
                  onReset={shortSelObj.resetSelection}
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
              defaultRowsPerPage={shortRppVal}
              rowsPerPageOptions={[shortRppVal]}
              tableMaxHeight="none"
              hidePagination
              selectable
              getRowId={getRowId}
              selectedRowIds={shortSelObj.selectedRowIds}
              onToggleRow={shortSelObj.toggleRowSelection}
              allPageSelected={shortSelObj.isAllPageSelected(shortIds)}
              indeterminate={shortSelObj.isIndeterminate(shortIds)}
              onToggleAll={makeToggleAll(shortSelObj, shortIds)}
              defaultOrderBy="entry_time"
              defaultOrder="desc"
              fillEmptyRows
            />
            <TablePagination
              component="div"
              count={shortTotal}
              page={shortPageVal}
              onPageChange={(_e, p) => setShortPageFn(p)}
              rowsPerPage={shortRppVal}
              onRowsPerPageChange={(e) => {
                setShortRppFn(parseInt(e.target.value, 10));
                setShortPageFn(0);
              }}
              rowsPerPageOptions={[10, 25, 50, 100, 200, 500, 1000]}
            />
          </Box>
        </Box>
      </Box>
    );
  };

  // --- Render a single table section ---
  const renderSingleTable = (
    label: string,
    data: TaskPosition[],
    total: number,
    selObj: typeof allSel,
    pageVal: number,
    setPageFn: (p: number) => void,
    rppVal: number,
    setRppFn: (r: number) => void,
    refresh: () => Promise<unknown>,
    key: string,
    columns: Column<TaskPosition>[],
    extractors: CopyValueExtractors<TaskPosition>,
    onConfigClick: () => void,
    pnlLabel?: string,
    pnlValue?: number
  ) => {
    const ids = data.map((r) => String(r.id));
    return (
      <Box sx={{ mb: 4 }}>
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
            {label} ({total})
          </Typography>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            {pnlLabel != null && pnlValue != null && (
              <Typography
                variant="subtitle1"
                fontWeight="bold"
                color={pnlValue >= 0 ? 'success.main' : 'error.main'}
              >
                {pnlLabel}: {formatSignedYen(pnlValue)}
              </Typography>
            )}
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
              selectedCount={selObj.selectedRowIds.size}
              onCopy={makeCopy(data, selObj, columns, extractors, ids)}
              onSelectAll={() => selObj.selectAllOnPage(ids)}
              onReset={selObj.resetSelection}
              onReload={makeReload(key, refresh)}
              isReloading={!!reloading[key]}
            />
          </Box>
        </Box>
        <TaskPositionFilterBar
          cycleIdFilter={cycleIdFilter}
          onCycleIdFilterChange={setCycleIdFilter}
          hasCycleIdFilter={hasCycleIdFilter}
          isCycleIdFilterValid={isCycleIdFilterValid}
          positionIdFilter={positionIdFilter}
          onPositionIdFilterChange={(value) => {
            setPositionIdFilter(value);
            setAllPage(0);
          }}
          hasPositionIdFilter={hasPositionIdFilter}
          isPositionIdFilterValid={isPositionIdFilterValid}
          dateFrom={dateFrom}
          dateTo={dateTo}
          onDateFromChange={(value) => {
            setDateFrom(value);
            setAllPage(0);
          }}
          onDateToChange={(value) => {
            setDateTo(value);
            setAllPage(0);
          }}
        />
        <DataTable
          columns={columns}
          data={data}
          isLoading={isLoading}
          emptyMessage={t('tables.positions.noPositions')}
          defaultRowsPerPage={rppVal}
          rowsPerPageOptions={[rppVal]}
          tableMaxHeight="none"
          hidePagination
          selectable
          getRowId={getRowId}
          selectedRowIds={selObj.selectedRowIds}
          onToggleRow={selObj.toggleRowSelection}
          allPageSelected={selObj.isAllPageSelected(ids)}
          indeterminate={selObj.isIndeterminate(ids)}
          onToggleAll={makeToggleAll(selObj, ids)}
          defaultOrderBy="entry_time"
          defaultOrder="desc"
          fillEmptyRows
        />
        <TablePagination
          component="div"
          count={total}
          page={pageVal}
          onPageChange={(_e, p) => setPageFn(p)}
          rowsPerPage={rppVal}
          onRowsPerPageChange={(e) => {
            setRppFn(parseInt(e.target.value, 10));
            setPageFn(0);
          }}
          rowsPerPageOptions={[10, 25, 50, 100, 200, 500, 1000]}
        />
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

  const totalPnl = totalRealizedPnl + totalUnrealizedPnl;
  const directionTables = [
    {
      key: 'long',
      label: t('tables.positions.longPositions'),
      data: longPos,
      total: longTotal,
      selection: longSel,
      page: longPage,
      setPage: setLongPage,
      rowsPerPage: longRpp,
      setRowsPerPage: setLongRpp,
      refresh: rLong,
      columns: filteredDirCols('long'),
    },
    {
      key: 'short',
      label: t('tables.positions.shortPositions'),
      data: shortPos,
      total: shortTotal,
      selection: shortSel,
      page: shortPage,
      setPage: setShortPage,
      rowsPerPage: shortRpp,
      setRowsPerPage: setShortRpp,
      refresh: rShort,
      columns: filteredDirCols('short'),
    },
  ];
  const statusPairs = [
    {
      key: 'closed',
      label: t('tables.positions.closedPositions'),
      longData: closedLongPos,
      longTotal: closedLongTotal,
      longSelection: closedLongSel,
      longPage: closedLongPage,
      setLongPage: setClosedLongPage,
      longRowsPerPage: closedLongRpp,
      setLongRowsPerPage: setClosedLongRpp,
      longRefresh: rCL,
      longReloadKey: 'cl',
      shortData: closedShortPos,
      shortTotal: closedShortTotal,
      shortSelection: closedShortSel,
      shortPage: closedShortPage,
      setShortPage: setClosedShortPage,
      shortRowsPerPage: closedShortRpp,
      setShortRowsPerPage: setClosedShortRpp,
      shortRefresh: rCS,
      shortReloadKey: 'cs',
      columns: filteredClosedCols,
      pnlLabel: t('tables.positions.totalRealizedPnl'),
      pnlValue: totalRealizedPnl,
      extractors: closedExtractors,
      onConfigClick: () => setClosedColConfigOpen(true),
    },
    {
      key: 'open',
      label: t('tables.positions.openPositions'),
      longData: openLongPos,
      longTotal: openLongTotal,
      longSelection: openLongSel,
      longPage: openLongPage,
      setLongPage: setOpenLongPage,
      longRowsPerPage: openLongRpp,
      setLongRowsPerPage: setOpenLongRpp,
      longRefresh: rOL,
      longReloadKey: 'ol',
      shortData: openShortPos,
      shortTotal: openShortTotal,
      shortSelection: openShortSel,
      shortPage: openShortPage,
      setShortPage: setOpenShortPage,
      shortRowsPerPage: openShortRpp,
      setShortRowsPerPage: setOpenShortRpp,
      shortRefresh: rOS,
      shortReloadKey: 'os',
      columns: filteredOpenCols,
      pnlLabel: t('tables.positions.totalUnrealizedPnl'),
      pnlValue: totalUnrealizedPnl,
      extractors: openExtractors,
      onConfigClick: () => setOpenColConfigOpen(true),
    },
  ];

  return (
    <Box sx={{ p: 3 }}>
      {/* View mode toggle + PnL summary */}
      <Box
        sx={{
          mb: 3,
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: 1,
        }}
      >
        <ToggleButtonGroup
          value={viewMode}
          exclusive
          onChange={handleViewModeChange}
          size="small"
        >
          <ToggleButton value="all">
            {t('tables.positions.viewMode.all')}
          </ToggleButton>
          <ToggleButton value="byDirection">
            {t('tables.positions.viewMode.byDirection')}
          </ToggleButton>
          <ToggleButton value="byStatus">
            {t('tables.positions.viewMode.byStatus')}
          </ToggleButton>
        </ToggleButtonGroup>
        {viewMode !== 'byStatus' && (
          <Typography
            variant="subtitle1"
            fontWeight="bold"
            color={totalPnl >= 0 ? 'success.main' : 'error.main'}
          >
            {t('tables.positions.totalPnl')}: {formatSignedYen(totalPnl)}
          </Typography>
        )}
      </Box>

      <TaskPositionModeViews
        viewMode={viewMode}
        all={renderSingleTable(
          t('tables.positions.allPositions'),
          allPos,
          allTotal,
          allSel,
          allPage,
          setAllPage,
          allRpp,
          setAllRpp,
          rAll,
          'all',
          filteredAllCols(),
          genericExtractors,
          () => setAllColConfigOpen(true)
        )}
        byDirection={
          <>
            {directionTables.map((table) => (
              <React.Fragment key={table.key}>
                {renderSingleTable(
                  table.label,
                  table.data,
                  table.total,
                  table.selection,
                  table.page,
                  table.setPage,
                  table.rowsPerPage,
                  table.setRowsPerPage,
                  table.refresh,
                  table.key,
                  table.columns,
                  genericExtractors,
                  () => setDirColConfigOpen(true)
                )}
              </React.Fragment>
            ))}
          </>
        }
        byStatus={
          <>
            <TaskPositionFilterBar
              cycleIdFilter={cycleIdFilter}
              onCycleIdFilterChange={setCycleIdFilter}
              hasCycleIdFilter={hasCycleIdFilter}
              isCycleIdFilterValid={isCycleIdFilterValid}
              positionIdFilter={positionIdFilter}
              onPositionIdFilterChange={setPositionIdFilter}
              hasPositionIdFilter={hasPositionIdFilter}
              isPositionIdFilterValid={isPositionIdFilterValid}
            />
            {statusPairs.map((pair) => (
              <React.Fragment key={pair.key}>
                {renderPair(
                  pair.label,
                  pair.longData,
                  pair.longTotal,
                  pair.longSelection,
                  pair.longPage,
                  pair.setLongPage,
                  pair.longRowsPerPage,
                  pair.setLongRowsPerPage,
                  pair.longRefresh,
                  pair.longReloadKey,
                  pair.shortData,
                  pair.shortTotal,
                  pair.shortSelection,
                  pair.shortPage,
                  pair.setShortPage,
                  pair.shortRowsPerPage,
                  pair.setShortRowsPerPage,
                  pair.shortRefresh,
                  pair.shortReloadKey,
                  pair.columns,
                  pair.pnlLabel,
                  pair.pnlValue,
                  pair.extractors,
                  pair.onConfigClick
                )}
              </React.Fragment>
            ))}
          </>
        }
      />

      {/* Column config dialogs */}
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
      <ColumnConfigDialog
        open={dirColConfigOpen}
        columns={dirColConfig}
        onClose={() => setDirColConfigOpen(false)}
        onSave={updateDirCols}
        onReset={resetDirCols}
      />
      <ColumnConfigDialog
        open={allColConfigOpen}
        columns={allColConfig}
        onClose={() => setAllColConfigOpen(false)}
        onSave={updateAllCols}
        onReset={resetAllCols}
      />

      <PositionLifecycleDialog
        open={lifecycleOpen}
        onClose={() => setLifecycleOpen(false)}
        taskId={String(taskId)}
        taskType={taskType}
        executionRunId={executionRunId}
        initialPositionId={lifecyclePositionId}
        positionData={lifecyclePosition}
        closeReasonLabels={strategyCloseReasonLabels}
      />
    </Box>
  );
};

export default TaskPositionsTable;
