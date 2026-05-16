import React, { useCallback, useMemo, useRef, useState } from 'react';
import {
  Alert,
  Box,
  Chip,
  CircularProgress,
  Divider,
  IconButton,
  InputAdornment,
  Paper,
  Stack,
  TablePagination,
  TextField,
  Tooltip,
  Typography,
  alpha,
  useMediaQuery,
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import HistoryIcon from '@mui/icons-material/History';
import ClearIcon from '@mui/icons-material/Clear';
import CandlestickChartIcon from '@mui/icons-material/CandlestickChart';
import RefreshIcon from '@mui/icons-material/Refresh';
import SearchIcon from '@mui/icons-material/Search';
import SelectAllIcon from '@mui/icons-material/SelectAll';
import { useTheme } from '@mui/material/styles';
import { useTranslation } from 'react-i18next';
import { useTaskStrategyEvents } from '../../../../hooks/useTaskStrategyEvents';
import { useTaskTrades } from '../../../../hooks/useTaskTrades';
import type { TaskType } from '../../../../types/common';
import type {
  StrategyCycle,
  CycleTrade,
  StrategyGridState,
} from '../../../../types/strategyVisualization';
import { StrategyGroupChart } from './StrategyGroupChart';
import { StrategyGridIndicator } from './StrategyGridIndicator';
import { PositionLifecycleDialog } from '../PositionLifecycleDialog';
import {
  buildDisplayGridState,
  buildSlotBuildCounts,
  gridHasPositions,
} from './gridState';
import {
  formatAppNumber,
  formatAppPercent,
  formatMoneyAmount,
} from '../../../../utils/numberFormat';
import {
  formatDateTimeInTimezone,
  type DateTimeFormatOptions,
} from '../../../../utils/timezone';
import { quoteCurrencyFromInstrument } from '../../../../utils/instrumentCurrency';
import { useAppSettings } from '../../../../hooks/useAppSettings';

export interface TaskStrategyTabProps {
  taskId: string | number;
  taskType: TaskType;
  strategyType?: string;
  instrument?: string;
  executionRunId?: string;
  enableRealTimeUpdates?: boolean;
  timezone?: string;
}

function formatDateTime(
  value?: string | null,
  timezone = 'UTC',
  dateFormat?: DateTimeFormatOptions['dateFormat']
): string {
  if (!value) return '-';
  return formatDateTimeInTimezone(value, timezone, undefined, {
    includeTimezone: true,
    dateFormat,
  });
}

function getPnlCurrencyCode(instrument?: string): string | null {
  return quoteCurrencyFromInstrument(instrument);
}

function formatSignedCurrency(
  value: number,
  currencyCode: string | null,
  fractionDigits = 1
): string {
  return formatMoneyAmount(value, currencyCode, {
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
    signed: true,
  });
}

function getStatusColor(
  status: string
): 'success' | 'warning' | 'info' | 'default' {
  if (status === 'completed') return 'success';
  if (status === 'active') return 'warning';
  if (status === 'pending') return 'info';
  return 'default';
}

function formatStatusFallback(status: string): string {
  if (!status) return '-';
  return status.charAt(0).toUpperCase() + status.slice(1);
}

function formatCyclePnl(
  cycle: StrategyCycle,
  currencyCode: string | null
): {
  total: string;
  color: string;
} {
  const displayMoney = cycle.total_pnl_display_money ?? cycle.total_pnl_money;
  const moneyTotal = Number(displayMoney?.amount);
  const realized = parseFloat(cycle.realized_pnl ?? '0');
  const unrealized = parseFloat(cycle.unrealized_pnl ?? '0');
  const total = Number.isFinite(moneyTotal)
    ? moneyTotal
    : realized + unrealized;
  return {
    total: formatSignedCurrency(
      total,
      displayMoney?.currency ?? currencyCode,
      1
    ),
    color:
      total > 0 ? 'success.main' : total < 0 ? 'error.main' : 'text.secondary',
  };
}

export function TaskStrategyTab({
  taskId,
  taskType,
  instrument,
  executionRunId,
  timezone = 'UTC',
}: TaskStrategyTabProps) {
  const { t } = useTranslation(['common']);
  const theme = useTheme();
  const { settings } = useAppSettings();
  const formatCycleStatus = useCallback(
    (status: StrategyCycle['status'] | string) =>
      t(
        `common:strategyVisualization.labels.${status}`,
        formatStatusFallback(status)
      ),
    [t]
  );
  const [sortOrder, setSortOrderState] = useState<'asc' | 'desc'>('asc');
  const [statusFilter, setStatusFilterState] = useState<
    'all' | 'active' | 'completed' | 'pending'
  >('all');
  const [positionIdFilter, setPositionIdFilterState] = useState('');
  const [tradeIdFilter, setTradeIdFilterState] = useState('');
  const [cyclePage, setCyclePage] = useState(0);
  const [cycleRowsPerPage, setCycleRowsPerPage] = useState(50);
  const [selectedCycleId, setSelectedCycleId] = useState<string | null>(null);
  const [sidebarWidth, setSidebarWidth] = useState(400);
  const isDragging = useRef(false);
  const [showOhlcChart, setShowOhlcChart] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const isMobile = useMediaQuery(theme.breakpoints.down('lg'));
  const isSummaryCompact = useMediaQuery(theme.breakpoints.down('sm'));
  const [mobileShowDetail, setMobileShowDetail] = useState(false);
  const [tradePage, setTradePage] = useState(0);
  const [tradeRowsPerPage, setTradeRowsPerPage] = useState(50);

  // Wrap the filter/sort setters so that any change also resets the
  // cycle page back to the first page.  Without this the user can end
  // up on a page beyond the new filtered universe.
  const setSortOrder = useCallback((next: 'asc' | 'desc') => {
    setSortOrderState(next);
    setCyclePage(0);
  }, []);
  const setStatusFilter = useCallback(
    (next: 'all' | 'active' | 'completed' | 'pending') => {
      setStatusFilterState(next);
      setCyclePage(0);
    },
    []
  );
  const setPositionIdFilter = useCallback((next: string) => {
    setPositionIdFilterState(next);
    setCyclePage(0);
  }, []);
  const setTradeIdFilter = useCallback((next: string) => {
    setTradeIdFilterState(next);
    setCyclePage(0);
  }, []);

  // Server-side filter / sort / pagination params.  ``position_id`` and
  // ``trade_id`` are only sent when at least three characters are typed
  // because the backend ignores shorter substrings.
  const listParams = useMemo<
    Record<string, string | number | undefined>
  >(() => {
    const params: Record<string, string | number | undefined> = {
      cycle_page: cyclePage + 1,
      cycle_page_size: cycleRowsPerPage,
      cycle_sort: sortOrder,
    };
    if (statusFilter !== 'all') {
      params.cycle_status = statusFilter;
    }
    const trimmedPosition = positionIdFilter.trim();
    if (trimmedPosition.length >= 3) {
      params.position_id = trimmedPosition;
    }
    const trimmedTrade = tradeIdFilter.trim();
    if (trimmedTrade.length >= 3) {
      params.trade_id = trimmedTrade;
    }
    return params;
  }, [
    cyclePage,
    cycleRowsPerPage,
    sortOrder,
    statusFilter,
    positionIdFilter,
    tradeIdFilter,
  ]);

  const { data, isLoading, error, refresh } = useTaskStrategyEvents({
    taskId,
    taskType,
    executionRunId,
    enableRealTimeUpdates: true,
    refreshInterval: 5_000,
    params: listParams,
  });
  const {
    data: detailData,
    isLoading: isDetailLoading,
    error: detailError,
    refresh: refreshDetail,
  } = useTaskStrategyEvents({
    taskId,
    taskType,
    executionRunId,
    cycleId: selectedCycleId ?? undefined,
    enabled: Boolean(selectedCycleId),
    enableRealTimeUpdates: true,
    refreshInterval: 5_000,
  });

  const cycles = useMemo<StrategyCycle[]>(() => data?.cycles ?? [], [data]);
  const supportsGridVisualization = data?.visualization?.grid !== false;
  const pnlCurrencyCode = useMemo(
    () => getPnlCurrencyCode(instrument),
    [instrument]
  );

  // Task 2: Multi-select trades for chart marker highlighting
  const [selectedTradeIds, setSelectedTradeIds] = useState<Set<string>>(
    new Set()
  );

  // Task 3: Position lifecycle dialog state
  const [lifecycleOpen, setLifecycleOpen] = useState(false);
  const [lifecyclePositionId, setLifecyclePositionId] = useState('');

  // Trade sort order within the detail panel
  const [tradeSortOrder, setTradeSortOrder] = useState<'asc' | 'desc'>('asc');

  const handleOpenLifecycle = useCallback((positionId: string) => {
    setLifecyclePositionId(positionId.slice(0, 8));
    setLifecycleOpen(true);
  }, []);

  const handleToggleTradeSelection = useCallback((tradeId: string) => {
    setSelectedTradeIds((prev) => {
      const next = new Set(prev);
      if (next.has(tradeId)) {
        next.delete(tradeId);
      } else {
        next.add(tradeId);
      }
      return next;
    });
  }, []);

  const handleResetTradeSelection = useCallback(() => {
    setSelectedTradeIds(new Set());
  }, []);

  const handleResizeStart = useCallback(
    (e: React.PointerEvent) => {
      e.preventDefault();
      isDragging.current = true;
      const startX = e.clientX;
      const startWidth = sidebarWidth;
      const onMove = (ev: PointerEvent) => {
        if (!isDragging.current) return;
        const containerWidth =
          containerRef.current?.getBoundingClientRect().width ?? 800;
        const newWidth = Math.min(
          Math.max(startWidth + (ev.clientX - startX), 240),
          containerWidth * 0.6
        );
        setSidebarWidth(newWidth);
      };
      const onUp = () => {
        isDragging.current = false;
        document.removeEventListener('pointermove', onMove);
        document.removeEventListener('pointerup', onUp);
      };
      document.addEventListener('pointermove', onMove);
      document.addEventListener('pointerup', onUp);
    },
    [sidebarWidth]
  );

  const displayedCycles = cycles;

  /** Extended grid states for sidebar cycles (includes layers from trade history). */
  const sidebarExtendedGridStates = useMemo(() => {
    const map = new Map<string, StrategyGridState | null | undefined>();
    for (const cycle of displayedCycles) {
      map.set(cycle.cycle_id, buildDisplayGridState(cycle));
    }
    return map;
  }, [displayedCycles]);

  const handleSelectCycle = useCallback(
    (id: string) => {
      setSelectedCycleId(id);
      setSelectedTradeIds(new Set());
      setTradePage(0);
      if (isMobile) setMobileShowDetail(true);
    },
    [isMobile]
  );

  // Task 2: Handle marker click from chart → highlight trade in list
  const handleMarkerClick = useCallback((tradeId: string) => {
    setSelectedTradeIds((prev) => {
      const next = new Set(prev);
      if (next.has(tradeId)) {
        next.delete(tradeId);
      } else {
        next.add(tradeId);
      }
      return next;
    });
  }, []);

  const selectedCycle = useMemo(
    () =>
      (detailData?.cycles ?? []).find((c) => c.cycle_id === selectedCycleId) ??
      null,
    [detailData, selectedCycleId]
  );
  const selectedCycleSlotBuildCounts = useMemo(
    () => buildSlotBuildCounts(selectedCycle),
    [selectedCycle]
  );
  const selectedCycleExtendedGridState = useMemo(
    () => buildDisplayGridState(selectedCycle),
    [selectedCycle]
  );

  const {
    trades: pagedTradesRaw,
    totalCount: pagedTradeCount,
    isLoading: isPagedTradesLoading,
    error: pagedTradesError,
    refresh: refreshPagedTrades,
  } = useTaskTrades({
    taskId,
    taskType,
    executionRunId,
    cycleId: selectedCycleId ?? undefined,
    enabled: Boolean(selectedCycleId),
    page: tradePage + 1,
    pageSize: tradeRowsPerPage,
    ordering: tradeSortOrder,
  });

  const pagedTrades = useMemo<CycleTrade[]>(
    () =>
      pagedTradesRaw.map((trade) => ({
        id: String(trade.id),
        direction:
          trade.direction === 'long'
            ? 'buy'
            : trade.direction === 'short'
              ? 'sell'
              : null,
        units: Number(trade.units),
        price: trade.price,
        execution_method: trade.execution_method ?? '',
        layer_index: trade.layer_index,
        retracement_count: trade.retracement_count,
        description: trade.description,
        timestamp: trade.timestamp,
        position_id: trade.position_id ?? null,
        is_rebuild: trade.is_rebuild,
        pnl: trade.pnl ?? null,
        pnl_money: trade.pnl_money ?? null,
        pnl_display_money: trade.pnl_display_money ?? null,
        display_conversion_context: trade.display_conversion_context ?? null,
      })),
    [pagedTradesRaw]
  );

  const handleRefreshDetail = useCallback(async () => {
    await Promise.all([refresh(), refreshDetail(), refreshPagedTrades()]);
  }, [refresh, refreshDetail, refreshPagedTrades]);

  const handleSelectAllTrades = useCallback(() => {
    setSelectedTradeIds(new Set(pagedTrades.map((t) => t.id)));
  }, [pagedTrades]);

  const summary = data?.summary;
  const formatSummaryCount = useCallback(
    (value: number) =>
      formatAppNumber(value, {
        maximumFractionDigits: 0,
      }),
    []
  );
  const summaryChips = useMemo(() => {
    if (!summary) return [];

    return [
      {
        key: 'cycles',
        label: t('common:strategyVisualization.chips.cycles', {
          count: summary.cycle_count,
        }),
        compactLabel: `${t(
          'common:strategyVisualization.chips.compact.cycles',
          {
            defaultValue: 'C',
          }
        )}: ${formatSummaryCount(summary.cycle_count)}`,
      },
      {
        key: 'active',
        label: t('common:strategyVisualization.chips.active', {
          count: summary.active_count,
        }),
        compactLabel: `${t(
          'common:strategyVisualization.chips.compact.active',
          {
            defaultValue: 'A',
          }
        )}: ${formatSummaryCount(summary.active_count)}`,
      },
      ...(summary.pending_count > 0
        ? [
            {
              key: 'pending',
              label: t('common:strategyVisualization.chips.pending', {
                count: summary.pending_count,
              }),
              compactLabel: `${t(
                'common:strategyVisualization.chips.compact.pending',
                {
                  defaultValue: 'P',
                }
              )}: ${formatSummaryCount(summary.pending_count)}`,
              color: 'info' as const,
            },
          ]
        : []),
      {
        key: 'completed',
        label: t('common:strategyVisualization.chips.completed', {
          count: summary.completed_count,
        }),
        compactLabel: `${t(
          'common:strategyVisualization.chips.compact.completed',
          {
            defaultValue: 'D',
          }
        )}: ${formatSummaryCount(summary.completed_count)}`,
      },
      {
        key: 'trades',
        label: t('common:strategyVisualization.chips.trades', {
          count: summary.total_trades,
        }),
        compactLabel: `${t(
          'common:strategyVisualization.chips.compact.trades',
          {
            defaultValue: 'T',
          }
        )}: ${formatSummaryCount(summary.total_trades)}`,
      },
    ];
  }, [formatSummaryCount, summary, t]);

  if (isLoading) {
    return (
      <Box sx={{ p: 3, display: 'flex', justifyContent: 'center' }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="error">{error.message}</Alert>
      </Box>
    );
  }

  const hasAnyActiveFilter =
    statusFilter !== 'all' ||
    positionIdFilter.trim().length >= 3 ||
    tradeIdFilter.trim().length >= 3;

  if (!data) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="info">
          {t('common:strategyVisualization.noData')}
        </Alert>
      </Box>
    );
  }

  if (cycles.length === 0 && !hasAnyActiveFilter) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="info">
          {t('common:strategyVisualization.noData')}
        </Alert>
      </Box>
    );
  }

  return (
    <Box
      sx={{
        p: { xs: 0.75, sm: 1 },
        display: 'flex',
        flexDirection: 'column',
        height: {
          xs: 'max(640px, calc(100vh - 170px))',
          lg: 'max(680px, calc(100vh - 170px))',
        },
        minHeight: { xs: 640, lg: 680 },
        overflow: 'hidden',
      }}
    >
      {summary ? (
        <Stack
          direction="row"
          spacing={0}
          sx={{
            mb: 0.75,
            gap: { xs: 0.25, sm: 0.5 },
            flexWrap: 'nowrap',
            flexShrink: 0,
            alignItems: 'center',
            minWidth: 0,
            overflow: 'hidden',
          }}
        >
          {summaryChips.map((chip) => (
            <Tooltip key={chip.key} title={chip.label}>
              <Chip
                label={isSummaryCompact ? chip.compactLabel : chip.label}
                color={chip.color}
                size="small"
                sx={{
                  flex: { xs: '1 1 0', sm: '0 0 auto' },
                  minWidth: 0,
                  height: { xs: 24, sm: 32 },
                  '& .MuiChip-label': {
                    minWidth: 0,
                    px: { xs: 0.5, sm: 1.5 },
                    fontSize: { xs: '0.68rem', sm: '0.8125rem' },
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                  },
                }}
              />
            </Tooltip>
          ))}
          <Tooltip title={t('common:actions.refresh')}>
            <IconButton
              size="small"
              onClick={() => void refresh()}
              aria-label={t('common:actions.refresh')}
              sx={{
                flex: '0 0 auto',
                width: { xs: 28, sm: 32 },
                height: { xs: 28, sm: 32 },
              }}
            >
              <RefreshIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </Stack>
      ) : null}

      <Box
        ref={containerRef}
        sx={{
          display: 'grid',
          gap: 0,
          gridTemplateColumns: {
            xs: '1fr',
            lg: `${sidebarWidth}px 8px minmax(0,1fr)`,
          },
          alignItems: 'stretch',
          flex: 1,
          minHeight: 0,
        }}
      >
        {/* Sidebar */}
        <Paper
          variant="outlined"
          sx={{
            display: isMobile && mobileShowDetail ? 'none' : 'flex',
            flexDirection: 'column',
            overflowY: 'auto',
            minHeight: 0,
          }}
        >
          <Box
            sx={{
              px: 1,
              py: 0.75,
              flexShrink: 0,
              display: 'flex',
              alignItems: 'center',
              gap: 0.5,
              flexWrap: 'wrap',
            }}
          >
            <Typography variant="subtitle2" sx={{ mr: 0.5 }}>
              {t('common:strategyVisualization.cycleList.title')}
            </Typography>
            <Chip
              size="small"
              clickable
              color={sortOrder === 'asc' ? 'primary' : 'default'}
              variant={sortOrder === 'asc' ? 'filled' : 'outlined'}
              label={t('common:strategyVisualization.cycleList.sortOldest')}
              onClick={() => setSortOrder('asc')}
            />
            <Chip
              size="small"
              clickable
              color={sortOrder === 'desc' ? 'primary' : 'default'}
              variant={sortOrder === 'desc' ? 'filled' : 'outlined'}
              label={t('common:strategyVisualization.cycleList.sortNewest')}
              onClick={() => setSortOrder('desc')}
            />
            <Divider orientation="vertical" flexItem sx={{ mx: 0.25 }} />
            <Chip
              size="small"
              clickable
              color={statusFilter === 'active' ? 'primary' : 'default'}
              variant={statusFilter === 'active' ? 'filled' : 'outlined'}
              label={t('common:strategyVisualization.cycleList.filterActive')}
              onClick={() =>
                setStatusFilter(statusFilter === 'active' ? 'all' : 'active')
              }
            />
            <Chip
              size="small"
              clickable
              color={statusFilter === 'completed' ? 'primary' : 'default'}
              variant={statusFilter === 'completed' ? 'filled' : 'outlined'}
              label={t(
                'common:strategyVisualization.cycleList.filterCompleted'
              )}
              onClick={() =>
                setStatusFilter(
                  statusFilter === 'completed' ? 'all' : 'completed'
                )
              }
            />
            <Chip
              size="small"
              clickable
              color={statusFilter === 'pending' ? 'primary' : 'default'}
              variant={statusFilter === 'pending' ? 'filled' : 'outlined'}
              label={t(
                'common:strategyVisualization.cycleList.filterPending',
                'Pending'
              )}
              onClick={() =>
                setStatusFilter(statusFilter === 'pending' ? 'all' : 'pending')
              }
            />
          </Box>
          <Divider />
          <Box sx={{ px: 1, py: 0.5, flexShrink: 0 }}>
            <TextField
              size="small"
              fullWidth
              placeholder={t(
                'common:strategyVisualization.cycleList.positionIdFilter'
              )}
              value={positionIdFilter}
              onChange={(e) => setPositionIdFilter(e.target.value)}
              helperText={
                positionIdFilter.trim().length > 0 &&
                positionIdFilter.trim().length < 3
                  ? t(
                      'common:strategyVisualization.cycleList.idFilterTooShort',
                      'Enter at least 3 characters'
                    )
                  : undefined
              }
              slotProps={{
                input: {
                  startAdornment: (
                    <InputAdornment position="start">
                      <SearchIcon fontSize="small" />
                    </InputAdornment>
                  ),
                  endAdornment: positionIdFilter ? (
                    <InputAdornment position="end">
                      <IconButton
                        size="small"
                        onClick={() => setPositionIdFilter('')}
                        edge="end"
                      >
                        <ClearIcon fontSize="small" />
                      </IconButton>
                    </InputAdornment>
                  ) : null,
                },
              }}
            />
          </Box>
          <Box sx={{ px: 1, pb: 0.5, flexShrink: 0 }}>
            <TextField
              size="small"
              fullWidth
              placeholder={t(
                'common:strategyVisualization.cycleList.tradeIdFilter',
                'Filter by trade ID'
              )}
              value={tradeIdFilter}
              onChange={(e) => setTradeIdFilter(e.target.value)}
              helperText={
                tradeIdFilter.trim().length > 0 &&
                tradeIdFilter.trim().length < 3
                  ? t(
                      'common:strategyVisualization.cycleList.idFilterTooShort',
                      'Enter at least 3 characters'
                    )
                  : undefined
              }
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
          </Box>
          <Divider />
          <Box
            sx={{
              p: 0.75,
              display: 'grid',
              gap: 0.75,
              overflowY: 'auto',
              minHeight: 0,
            }}
          >
            {displayedCycles.length === 0 ? (
              <Box sx={{ p: 2 }}>
                <Alert severity="info">
                  {t('common:strategyVisualization.cycleList.noCyclesFound')}
                </Alert>
              </Box>
            ) : (
              displayedCycles.map((cycle) => (
                <Box
                  key={cycle.cycle_id}
                  role="button"
                  tabIndex={0}
                  onClick={() => handleSelectCycle(cycle.cycle_id)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      handleSelectCycle(cycle.cycle_id);
                    }
                  }}
                  sx={{
                    p: 0.75,
                    borderRadius: 1,
                    border: '1px solid',
                    borderColor:
                      cycle.cycle_id === selectedCycle?.cycle_id
                        ? 'primary.main'
                        : 'divider',
                    bgcolor:
                      cycle.cycle_id === selectedCycle?.cycle_id
                        ? alpha(theme.palette.primary.main, 0.08)
                        : 'background.paper',
                    cursor: 'pointer',
                    transition:
                      'border-color 120ms ease, background-color 120ms ease',
                    '&:hover': {
                      borderColor: 'primary.main',
                      bgcolor: alpha(theme.palette.primary.main, 0.05),
                    },
                  }}
                >
                  <Stack
                    direction="row"
                    spacing={0.5}
                    sx={{
                      mb: 0.5,
                      alignItems: 'center',
                      flexWrap: 'nowrap',
                      overflow: 'hidden',
                    }}
                  >
                    <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
                      {cycle.direction.toUpperCase()}
                    </Typography>
                    <Chip
                      size="small"
                      label={formatCycleStatus(cycle.status)}
                      color={getStatusColor(cycle.status)}
                      sx={{ fontSize: '0.7rem', height: 20 }}
                    />
                    <Chip
                      size="small"
                      variant="outlined"
                      label={t(
                        'common:strategyVisualization.cycleList.tradeCount',
                        { count: cycle.trade_count }
                      )}
                      sx={{ fontSize: '0.7rem', height: 20 }}
                    />
                    {cycle.has_protection ? (
                      <Chip
                        size="small"
                        color="error"
                        variant="filled"
                        label={`⚠ ${cycle.protection_count ?? ''}`}
                        sx={{ fontSize: '0.65rem', height: 20 }}
                      />
                    ) : null}
                    {(cycle.rebuild_count ?? 0) > 0 ? (
                      <Chip
                        size="small"
                        color="secondary"
                        variant="outlined"
                        label={`🔄 ${cycle.rebuild_count}`}
                        sx={{ fontSize: '0.65rem', height: 20 }}
                      />
                    ) : null}
                  </Stack>
                  <Typography variant="body2" color="text.secondary">
                    {formatDateTime(
                      cycle.started_at,
                      timezone,
                      settings.dateFormat
                    )}
                    <Typography
                      component="span"
                      variant="body2"
                      sx={{ ml: 1, fontWeight: 600 }}
                      color={formatCyclePnl(cycle, pnlCurrencyCode).color}
                    >
                      {formatCyclePnl(cycle, pnlCurrencyCode).total}
                    </Typography>
                  </Typography>
                  {supportsGridVisualization &&
                  cycle.grid_state &&
                  (cycle.status !== 'completed' ||
                    gridHasPositions(
                      sidebarExtendedGridStates.get(cycle.cycle_id) ??
                        cycle.grid_state
                    )) ? (
                    <Box sx={{ mt: 0.5 }}>
                      <StrategyGridIndicator
                        gridState={
                          sidebarExtendedGridStates.get(cycle.cycle_id) ??
                          cycle.grid_state
                        }
                        compact={true}
                        showLegend={false}
                        showSummary={false}
                        showSlotBuildCounts={false}
                      />
                    </Box>
                  ) : null}
                </Box>
              ))
            )}
          </Box>
          {data?.pagination ? (
            <>
              <Divider />
              <TablePagination
                component="div"
                count={data.pagination.total_count}
                page={Math.max(
                  0,
                  Math.min(
                    cyclePage,
                    Math.max(0, data.pagination.total_pages - 1)
                  )
                )}
                rowsPerPage={cycleRowsPerPage}
                rowsPerPageOptions={[25, 50, 100, 200]}
                onPageChange={(_event, nextPage) => setCyclePage(nextPage)}
                onRowsPerPageChange={(event) => {
                  const value = parseInt(event.target.value, 10);
                  if (!Number.isNaN(value)) {
                    setCycleRowsPerPage(value);
                    setCyclePage(0);
                  }
                }}
                labelRowsPerPage={t(
                  'common:strategyVisualization.cycleList.rowsPerPage',
                  'Cycles per page'
                )}
                sx={{
                  flexShrink: 0,
                  '& .MuiTablePagination-toolbar': {
                    minHeight: 36,
                    paddingLeft: 1,
                    paddingRight: 1,
                  },
                  '& .MuiTablePagination-selectLabel, & .MuiTablePagination-displayedRows':
                    {
                      fontSize: '0.75rem',
                      margin: 0,
                    },
                }}
              />
            </>
          ) : null}
        </Paper>

        {/* Resize handle */}
        <Box
          onPointerDown={handleResizeStart}
          sx={{
            display: { xs: 'none', lg: 'flex' },
            alignItems: 'center',
            justifyContent: 'center',
            width: 8,
            cursor: 'col-resize',
            userSelect: 'none',
            touchAction: 'none',
            alignSelf: 'stretch',
            '&:hover > div, &:active > div': { bgcolor: 'primary.main' },
          }}
        >
          <Box
            sx={{
              width: 3,
              height: 40,
              borderRadius: 1.5,
              bgcolor: 'divider',
              transition: 'background-color 120ms ease',
            }}
          />
        </Box>

        {/* Detail panel */}
        <Paper
          variant="outlined"
          sx={{
            minWidth: 0,
            display: isMobile && !mobileShowDetail ? 'none' : 'block',
            overflowY: 'auto',
            minHeight: 0,
          }}
        >
          {detailError && selectedCycleId ? (
            <Box sx={{ p: 3 }}>
              <Alert severity="error">{detailError.message}</Alert>
            </Box>
          ) : isDetailLoading && selectedCycleId && !selectedCycle ? (
            <Box
              sx={{
                p: 3,
                display: 'flex',
                justifyContent: 'center',
              }}
            >
              <CircularProgress />
            </Box>
          ) : selectedCycle ? (
            <Box sx={{ p: 1 }}>
              {isMobile ? (
                <Box
                  sx={{
                    position: 'sticky',
                    top: 0,
                    zIndex: 10,
                    bgcolor: 'background.paper',
                    pb: 0.5,
                  }}
                >
                  <IconButton
                    onClick={() => setMobileShowDetail(false)}
                    size="small"
                    aria-label={t(
                      'common:strategyVisualization.cycleList.back'
                    )}
                  >
                    <ArrowBackIcon />
                  </IconButton>
                </Box>
              ) : null}
              <Stack
                direction="row"
                spacing={0.75}
                sx={{ mb: 0.5, flexWrap: 'wrap', alignItems: 'center' }}
              >
                <Typography variant="h6">
                  {selectedCycle.direction.toUpperCase()}{' '}
                  {t('common:strategyVisualization.cycleList.cycle')}
                </Typography>
                <Chip
                  label={formatCycleStatus(selectedCycle.status)}
                  size="small"
                  color={getStatusColor(selectedCycle.status)}
                />
                <Tooltip title={t('common:actions.refresh')}>
                  <IconButton
                    size="small"
                    onClick={() => void handleRefreshDetail()}
                    aria-label={t('common:actions.refresh')}
                  >
                    <RefreshIcon fontSize="small" />
                  </IconButton>
                </Tooltip>
                {instrument && (
                  <Tooltip
                    title={
                      showOhlcChart
                        ? t(
                            'common:strategyVisualization.hideOhlcChart',
                            'Hide OHLC chart'
                          )
                        : t(
                            'common:strategyVisualization.showOhlcChart',
                            'Show OHLC chart'
                          )
                    }
                  >
                    <IconButton
                      size="small"
                      onClick={() => setShowOhlcChart((v) => !v)}
                      color={showOhlcChart ? 'primary' : 'default'}
                      aria-label="Toggle OHLC chart"
                    >
                      <CandlestickChartIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
                )}
              </Stack>
              <Typography
                variant="body2"
                color="text.secondary"
                sx={{ mb: 0.75 }}
              >
                {formatDateTime(
                  selectedCycle.started_at,
                  timezone,
                  settings.dateFormat
                )}{' '}
                →{' '}
                {formatDateTime(
                  selectedCycle.ended_at ?? detailData?.last_tick_timestamp,
                  timezone,
                  settings.dateFormat
                )}
              </Typography>
              <Typography
                variant="caption"
                color="text.secondary"
                sx={{ mb: 0.5, display: 'block', fontFamily: 'monospace' }}
              >
                Cycle ID: {selectedCycle.cycle_id}
              </Typography>
              <Typography
                variant="body2"
                color="text.secondary"
                sx={{ mb: 0.75 }}
              >
                {t('common:strategyVisualization.cycleList.opensAndCloses', {
                  opens: selectedCycle.open_count,
                  closes: selectedCycle.close_count,
                })}
                <Typography component="span" variant="body2" sx={{ ml: 1.5 }}>
                  {t('common:strategyVisualization.cycleList.openUnitsTotal', {
                    units: formatAppNumber(selectedCycle.open_units_total ?? 0),
                  })}
                </Typography>
                <Typography
                  component="span"
                  variant="body2"
                  sx={{ ml: 1.5, fontWeight: 600 }}
                  color={formatCyclePnl(selectedCycle, pnlCurrencyCode).color}
                >
                  PnL: {formatCyclePnl(selectedCycle, pnlCurrencyCode).total}
                </Typography>
              </Typography>
              {supportsGridVisualization && selectedCycle.grid_state ? (
                <Box sx={{ mb: 1 }}>
                  <StrategyGridIndicator
                    gridState={selectedCycleExtendedGridState}
                    showSlotBuildCounts={true}
                    slotBuildCounts={selectedCycleSlotBuildCounts}
                  />
                </Box>
              ) : null}

              {instrument && showOhlcChart ? (
                <Paper
                  variant="outlined"
                  sx={{
                    p: 1,
                    mb: 1,
                    bgcolor: alpha(theme.palette.primary.main, 0.03),
                  }}
                >
                  <StrategyGroupChart
                    key={selectedCycle.cycle_id}
                    instrument={instrument}
                    startTime={selectedCycle.started_at ?? ''}
                    endTime={selectedCycle.ended_at}
                    trades={selectedCycle.trades}
                    height={300}
                    taskId={taskId}
                    taskType={taskType}
                    executionRunId={executionRunId}
                    lastTickTimestamp={detailData?.last_tick_timestamp ?? null}
                    selectedTradeIds={selectedTradeIds}
                    onMarkerClick={handleMarkerClick}
                    timezone={timezone}
                  />
                </Paper>
              ) : null}

              <Stack
                direction="row"
                spacing={0.75}
                sx={{ mb: 0.5, alignItems: 'center', flexWrap: 'wrap' }}
              >
                <Typography variant="subtitle1">
                  {t('common:strategyVisualization.cycleList.trades')} (
                  {pagedTradeCount})
                </Typography>
                <Chip
                  size="small"
                  clickable
                  color={tradeSortOrder === 'asc' ? 'primary' : 'default'}
                  variant={tradeSortOrder === 'asc' ? 'filled' : 'outlined'}
                  label={t('common:strategyVisualization.cycleList.sortOldest')}
                  onClick={() => {
                    setTradeSortOrder('asc');
                    setTradePage(0);
                  }}
                />
                <Chip
                  size="small"
                  clickable
                  color={tradeSortOrder === 'desc' ? 'primary' : 'default'}
                  variant={tradeSortOrder === 'desc' ? 'filled' : 'outlined'}
                  label={t('common:strategyVisualization.cycleList.sortNewest')}
                  onClick={() => {
                    setTradeSortOrder('desc');
                    setTradePage(0);
                  }}
                />
                <Tooltip title="Select all">
                  <IconButton size="small" onClick={handleSelectAllTrades}>
                    <SelectAllIcon fontSize="small" />
                  </IconButton>
                </Tooltip>
                {selectedTradeIds.size > 0 ? (
                  <Tooltip title="Deselect all">
                    <IconButton
                      size="small"
                      onClick={handleResetTradeSelection}
                    >
                      <ClearIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
                ) : null}
                {selectedTradeIds.size > 0 ? (
                  <Typography variant="caption" color="text.secondary">
                    {selectedTradeIds.size}/{pagedTrades.length}
                  </Typography>
                ) : null}
              </Stack>
              <Divider sx={{ mb: 0.5 }} />
              {pagedTradesError ? (
                <Box sx={{ pb: 2 }}>
                  <Alert severity="error">{pagedTradesError.message}</Alert>
                </Box>
              ) : null}
              {isPagedTradesLoading ? (
                <Box sx={{ py: 4, display: 'flex', justifyContent: 'center' }}>
                  <CircularProgress size={24} />
                </Box>
              ) : null}
              {pagedTrades.map((trade, index) => {
                const isInitialEntry = trade.id === selectedCycle.cycle_id;
                const isSelected = selectedTradeIds.has(trade.id);
                // Task 1: Initial entry always shows L1, R0
                const displayLayer = isInitialEntry ? 1 : trade.layer_index;
                const displayRet = isInitialEntry ? 0 : trade.retracement_count;

                return (
                  <React.Fragment key={trade.id}>
                    <TradeRow
                      trade={trade}
                      isInitialEntry={isInitialEntry}
                      isSelected={isSelected}
                      displayLayer={displayLayer}
                      displayRet={displayRet}
                      timezone={timezone}
                      dateFormat={settings.dateFormat}
                      currencyCode={pnlCurrencyCode}
                      onToggleSelection={handleToggleTradeSelection}
                      onOpenLifecycle={handleOpenLifecycle}
                    />
                    {index < pagedTrades.length - 1 ? <Divider /> : null}
                  </React.Fragment>
                );
              })}
              <TablePagination
                component="div"
                count={pagedTradeCount}
                page={tradePage}
                onPageChange={(_e, newPage) => setTradePage(newPage)}
                rowsPerPage={tradeRowsPerPage}
                onRowsPerPageChange={(e) => {
                  setTradeRowsPerPage(parseInt(e.target.value, 10));
                  setTradePage(0);
                }}
                rowsPerPageOptions={[10, 25, 50, 100, 200, 500, 1000]}
              />
            </Box>
          ) : (
            <Box sx={{ p: 3 }}>
              <Alert severity="info">
                {t('common:strategyVisualization.cycleList.selectCycle')}
              </Alert>
            </Box>
          )}
        </Paper>
      </Box>

      {/* Task 3: Position lifecycle dialog */}
      <PositionLifecycleDialog
        open={lifecycleOpen}
        onClose={() => setLifecycleOpen(false)}
        taskId={String(taskId)}
        taskType={taskType}
        executionRunId={executionRunId}
        initialPositionId={lifecyclePositionId}
        timezone={timezone}
      />
    </Box>
  );
}

/** Individual trade row — extracted for clarity. */
function TradeRow({
  trade,
  isInitialEntry,
  isSelected,
  displayLayer,
  displayRet,
  timezone,
  dateFormat,
  currencyCode,
  onToggleSelection,
  onOpenLifecycle,
}: {
  trade: CycleTrade;
  isInitialEntry: boolean;
  isSelected: boolean;
  displayLayer: number | null | undefined;
  displayRet: number | null | undefined;
  timezone: string;
  dateFormat: DateTimeFormatOptions['dateFormat'];
  currencyCode: string | null;
  onToggleSelection: (id: string) => void;
  onOpenLifecycle: (positionId: string) => void;
}) {
  return (
    <Box
      sx={{
        py: 0.5,
        px: 0.5,
        cursor: 'pointer',
        borderRadius: 1,
        transition: 'background-color 120ms ease',
        ...(isSelected && {
          backgroundColor: 'rgba(245, 158, 11, 0.15)',
        }),
        '&:hover': {
          backgroundColor: isSelected
            ? 'rgba(245, 158, 11, 0.25)'
            : 'action.hover',
        },
      }}
      onClick={() => onToggleSelection(trade.id)}
    >
      <Stack
        direction="row"
        spacing={0.75}
        sx={{ alignItems: 'center', flexWrap: 'wrap' }}
      >
        <Chip
          size="small"
          label={
            trade.execution_method === 'open_position'
              ? 'OPEN'
              : trade.execution_method === 'rebuild_position'
                ? 'REBUILD'
                : trade.execution_method === 'close_position'
                  ? 'CLOSE'
                  : trade.execution_method.replace(/_/g, ' ').toUpperCase()
          }
          color={
            trade.execution_method === 'open_position'
              ? 'info'
              : trade.execution_method === 'rebuild_position'
                ? 'secondary'
                : trade.execution_method === 'close_position'
                  ? 'default'
                  : 'error'
          }
          variant={
            trade.execution_method === 'open_position' ||
            trade.execution_method === 'rebuild_position' ||
            trade.execution_method === 'close_position'
              ? 'outlined'
              : 'filled'
          }
        />
        {isInitialEntry ? (
          <Chip
            size="small"
            label="Initial"
            color="primary"
            variant="outlined"
            sx={{ fontSize: '0.7rem' }}
          />
        ) : null}
        <Chip
          size="small"
          label={trade.direction === 'buy' ? 'LONG' : 'SHORT'}
          color={trade.direction === 'buy' ? 'success' : 'error'}
          variant="outlined"
        />
        {trade.position_id ? (
          <Typography
            variant="caption"
            sx={{ fontFamily: 'monospace', color: 'text.secondary' }}
          >
            {trade.position_id.slice(0, 8)}
          </Typography>
        ) : null}
        <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
          {formatAppNumber(Number(trade.units))} @{' '}
          {formatAppNumber(Number(trade.price), {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
            useGrouping: false,
          })}
        </Typography>
        {displayLayer != null ? (
          <Typography variant="caption" color="text.secondary">
            L{displayLayer}
          </Typography>
        ) : null}
        {displayRet != null ? (
          <Typography variant="caption" color="text.secondary">
            R{displayRet}
          </Typography>
        ) : null}
        {trade.volatility != null ? (
          <Chip
            size="small"
            variant="outlined"
            label={`ATR ${formatAppNumber(Number(trade.volatility), {
              minimumFractionDigits: 5,
              maximumFractionDigits: 5,
              useGrouping: false,
            })}`}
            sx={{ fontSize: '0.7rem' }}
          />
        ) : null}
        {trade.margin_ratio != null ? (
          <Chip
            size="small"
            variant="outlined"
            label={`Margin ${formatAppPercent(
              Number(trade.margin_ratio) * 100,
              1
            )}`}
            sx={{ fontSize: '0.7rem' }}
          />
        ) : null}
        {/* Task 3: Lifecycle button for trades with position_id */}
        {trade.position_id ? (
          <Tooltip title="View position lifecycle">
            <IconButton
              size="small"
              onClick={(e) => {
                e.stopPropagation();
                onOpenLifecycle(trade.position_id!);
              }}
              sx={{ p: 0.25 }}
            >
              <HistoryIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        ) : null}
        {trade.pnl != null &&
        trade.execution_method !== 'open_position' &&
        trade.execution_method !== 'rebuild_position'
          ? (() => {
              const pnlMoney = trade.pnl_display_money ?? trade.pnl_money;
              const pnlValue = Number(pnlMoney?.amount ?? trade.pnl);
              if (!Number.isFinite(pnlValue)) return null;
              return (
                <Typography
                  variant="caption"
                  sx={{ fontWeight: 700, fontFamily: 'monospace' }}
                  color={pnlValue >= 0 ? 'success.main' : 'error.main'}
                >
                  {formatMoneyAmount(
                    pnlValue,
                    pnlMoney?.currency ?? currencyCode,
                    {
                      minimumFractionDigits: 0,
                      maximumFractionDigits: 0,
                      signed: true,
                    }
                  )}
                </Typography>
              );
            })()
          : null}
      </Stack>
      {trade.description ? (
        <Typography
          variant="caption"
          color="text.secondary"
          sx={{ display: 'block', mt: 0.25 }}
        >
          {trade.description}
        </Typography>
      ) : null}
      <Typography
        variant="caption"
        color="text.secondary"
        sx={{ display: 'block' }}
      >
        {formatDateTime(trade.timestamp, timezone, dateFormat)}
      </Typography>
    </Box>
  );
}

export default TaskStrategyTab;
