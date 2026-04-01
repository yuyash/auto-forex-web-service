import React, {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import {
  Alert,
  Box,
  Chip,
  CircularProgress,
  Divider,
  IconButton,
  Paper,
  Stack,
  Tooltip,
  Typography,
  alpha,
  useMediaQuery,
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import HistoryIcon from '@mui/icons-material/History';
import ClearIcon from '@mui/icons-material/Clear';
import RefreshIcon from '@mui/icons-material/Refresh';
import SelectAllIcon from '@mui/icons-material/SelectAll';
import { useTheme } from '@mui/material/styles';
import { useTranslation } from 'react-i18next';
import { useTaskStrategyEvents } from '../../../../hooks/useTaskStrategyEvents';
import { TaskType } from '../../../../types/common';
import type {
  StrategyCycle,
  CycleTrade,
} from '../../../../types/strategyVisualization';
import { StrategyGroupChart } from './StrategyGroupChart';
import { PositionLifecycleDialog } from '../PositionLifecycleDialog';

export interface TaskStrategyTabProps {
  taskId: string | number;
  taskType: TaskType;
  instrument?: string;
  executionRunId?: string;
  enableRealTimeUpdates?: boolean;
}

function formatDateTime(value?: string | null): string {
  if (!value) return '-';
  return new Date(value).toLocaleString();
}

function getStatusColor(status: string): 'success' | 'warning' | 'default' {
  if (status === 'completed') return 'success';
  if (status === 'active') return 'warning';
  return 'default';
}

export function TaskStrategyTab({
  taskId,
  taskType,
  instrument,
  executionRunId,
}: TaskStrategyTabProps) {
  const { t } = useTranslation(['common']);
  const theme = useTheme();
  const { data, isLoading, error, refresh } = useTaskStrategyEvents({
    taskId,
    taskType,
    executionRunId,
    enableRealTimeUpdates: true,
    refreshInterval: 5_000,
  });

  const cycles = useMemo<StrategyCycle[]>(() => data?.cycles ?? [], [data]);

  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('asc');
  const [statusFilter, setStatusFilter] = useState<
    'all' | 'active' | 'completed'
  >('all');
  const [selectedCycleId, setSelectedCycleId] = useState<string | null>(null);
  // Snapshot of the selected cycle — only updated on select or manual refresh
  const [detailSnapshot, setDetailSnapshot] = useState<StrategyCycle | null>(
    null
  );
  const [snapshotTickTimestamp, setSnapshotTickTimestamp] = useState<
    string | null
  >(null);
  const [sidebarWidth, setSidebarWidth] = useState(360);
  const isDragging = useRef(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const isMobile = useMediaQuery(theme.breakpoints.down('lg'));
  const [mobileShowDetail, setMobileShowDetail] = useState(false);

  // Task 2: Multi-select trades for chart marker highlighting
  const [selectedTradeIds, setSelectedTradeIds] = useState<Set<string>>(
    new Set()
  );

  // Task 3: Position lifecycle dialog state
  const [lifecycleOpen, setLifecycleOpen] = useState(false);
  const [lifecyclePositionId, setLifecyclePositionId] = useState('');

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

  const displayedCycles = useMemo(() => {
    let list = sortOrder === 'asc' ? cycles : [...cycles].reverse();
    if (statusFilter !== 'all') {
      list = list.filter((c) => c.status === statusFilter);
    }
    return list;
  }, [cycles, sortOrder, statusFilter]);

  const handleSelectCycle = useCallback(
    (id: string) => {
      setSelectedCycleId(id);
      setSelectedTradeIds(new Set());
      // Immediately snapshot from current data
      const cycle = (data?.cycles ?? []).find((c) => c.cycle_id === id) ?? null;
      setDetailSnapshot(cycle);
      setSnapshotTickTimestamp(data?.last_tick_timestamp ?? null);
      if (isMobile) setMobileShowDetail(true);
    },
    [isMobile, data]
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

  const selectedCycle = detailSnapshot;

  // Manual refresh: re-fetch data then update the snapshot
  const [detailRefreshSeq, setDetailRefreshSeq] = useState(0);
  const handleRefreshDetail = useCallback(async () => {
    await refresh();
    setDetailRefreshSeq((n) => n + 1);
  }, [refresh]);

  // Update snapshot when detailRefreshSeq changes (user triggered refresh)
  useEffect(() => {
    if (detailRefreshSeq > 0 && selectedCycleId && data) {
      const freshCycle =
        (data.cycles ?? []).find((c) => c.cycle_id === selectedCycleId) ?? null;
      if (freshCycle) {
        setDetailSnapshot(freshCycle);
        setSnapshotTickTimestamp(data.last_tick_timestamp ?? null);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [detailRefreshSeq]);

  const handleSelectAllTrades = useCallback(() => {
    if (!selectedCycle) return;
    setSelectedTradeIds(new Set(selectedCycle.trades.map((t) => t.id)));
  }, [selectedCycle]);

  const summary = data?.summary;

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

  if (!data || cycles.length === 0) {
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
        p: 3,
        display: 'flex',
        flexDirection: 'column',
        height: { lg: 'calc(100vh - 160px)' },
        overflow: 'hidden',
      }}
    >
      {summary ? (
        <Stack
          direction="row"
          spacing={1}
          sx={{ mb: 2, flexWrap: 'wrap', flexShrink: 0, alignItems: 'center' }}
        >
          <Chip
            label={t('common:strategyVisualization.chips.cycles', {
              count: summary.cycle_count,
            })}
          />
          <Chip
            label={t('common:strategyVisualization.chips.active', {
              count: summary.active_count,
            })}
          />
          <Chip
            label={t('common:strategyVisualization.chips.completed', {
              count: summary.completed_count,
            })}
          />
          <Chip
            label={t('common:strategyVisualization.chips.trades', {
              count: summary.total_trades,
            })}
          />
          <Tooltip title={t('common:actions.refresh')}>
            <IconButton
              size="small"
              onClick={() => void refresh()}
              aria-label={t('common:actions.refresh')}
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
              px: 1.5,
              py: 1,
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
                setStatusFilter((p) => (p === 'active' ? 'all' : 'active'))
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
                setStatusFilter((p) =>
                  p === 'completed' ? 'all' : 'completed'
                )
              }
            />
          </Box>
          <Divider />
          <Box
            sx={{
              p: 1.5,
              display: 'grid',
              gap: 1.25,
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
                    p: 1.5,
                    borderRadius: 2,
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
                    spacing={1}
                    sx={{ mb: 0.5, alignItems: 'center', flexWrap: 'wrap' }}
                  >
                    <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
                      {cycle.direction.toUpperCase()}
                    </Typography>
                    <Chip
                      size="small"
                      label={
                        cycle.status.charAt(0).toUpperCase() +
                        cycle.status.slice(1)
                      }
                      color={getStatusColor(cycle.status)}
                    />
                    <Chip
                      size="small"
                      variant="outlined"
                      label={t(
                        'common:strategyVisualization.cycleList.tradeCount',
                        { count: cycle.trade_count }
                      )}
                    />
                    {cycle.has_protection ? (
                      <Chip
                        size="small"
                        color="error"
                        variant="filled"
                        label={`⚠ ${cycle.protection_count ?? ''}`}
                        sx={{ fontSize: '0.7rem' }}
                      />
                    ) : null}
                  </Stack>
                  <Typography variant="body2" color="text.secondary">
                    {formatDateTime(cycle.started_at)}
                  </Typography>
                </Box>
              ))
            )}
          </Box>
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
          {selectedCycle ? (
            <Box sx={{ p: 2 }}>
              {isMobile ? (
                <Box
                  sx={{
                    position: 'sticky',
                    top: 0,
                    zIndex: 10,
                    bgcolor: 'background.paper',
                    pb: 1,
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
                spacing={1}
                sx={{ mb: 1, flexWrap: 'wrap', alignItems: 'center' }}
              >
                <Typography variant="h6">
                  {selectedCycle.direction.toUpperCase()}{' '}
                  {t('common:strategyVisualization.cycleList.cycle')}
                </Typography>
                <Chip
                  label={
                    selectedCycle.status.charAt(0).toUpperCase() +
                    selectedCycle.status.slice(1)
                  }
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
              </Stack>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                {formatDateTime(selectedCycle.started_at)} →{' '}
                {formatDateTime(
                  selectedCycle.ended_at ?? snapshotTickTimestamp
                )}
              </Typography>
              <Typography
                variant="caption"
                color="text.secondary"
                sx={{ mb: 1, display: 'block', fontFamily: 'monospace' }}
              >
                {selectedCycle.cycle_id}
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                {t('common:strategyVisualization.cycleList.opensAndCloses', {
                  opens: selectedCycle.open_count,
                  closes: selectedCycle.close_count,
                })}
              </Typography>

              {instrument ? (
                <Paper
                  variant="outlined"
                  sx={{
                    p: 2,
                    mb: 2,
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
                    lastTickTimestamp={snapshotTickTimestamp}
                    selectedTradeIds={selectedTradeIds}
                    onMarkerClick={handleMarkerClick}
                  />
                </Paper>
              ) : null}

              <Stack
                direction="row"
                spacing={1}
                sx={{ mb: 1, alignItems: 'center' }}
              >
                <Typography variant="subtitle1">
                  {t('common:strategyVisualization.cycleList.trades')}
                </Typography>
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
                    {selectedTradeIds.size}/{selectedCycle.trades.length}
                  </Typography>
                ) : null}
              </Stack>
              <Divider sx={{ mb: 1 }} />
              {selectedCycle.trades.map((trade, index) => {
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
                      onToggleSelection={handleToggleTradeSelection}
                      onOpenLifecycle={handleOpenLifecycle}
                    />
                    {index < selectedCycle.trades.length - 1 ? (
                      <Divider />
                    ) : null}
                  </React.Fragment>
                );
              })}
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
  onToggleSelection,
  onOpenLifecycle,
}: {
  trade: CycleTrade;
  isInitialEntry: boolean;
  isSelected: boolean;
  displayLayer: number | null | undefined;
  displayRet: number | null | undefined;
  onToggleSelection: (id: string) => void;
  onOpenLifecycle: (positionId: string) => void;
}) {
  return (
    <Box
      sx={{
        py: 1,
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
        spacing={1}
        sx={{ alignItems: 'center', flexWrap: 'wrap' }}
      >
        <Chip
          size="small"
          label={
            trade.execution_method === 'open_position'
              ? 'OPEN'
              : trade.execution_method === 'close_position'
                ? 'CLOSE'
                : trade.execution_method.replace(/_/g, ' ').toUpperCase()
          }
          color={
            trade.execution_method === 'open_position'
              ? 'info'
              : trade.execution_method === 'close_position'
                ? 'default'
                : 'error'
          }
          variant={
            trade.execution_method === 'open_position' ||
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
          label={trade.direction === 'buy' ? 'BUY' : 'SELL'}
          color={trade.direction === 'buy' ? 'success' : 'error'}
          variant="outlined"
        />
        <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
          {trade.units} @ {Number(trade.price).toFixed(2)}
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
            label={`ATR ${Number(trade.volatility).toFixed(5)}`}
            sx={{ fontSize: '0.7rem' }}
          />
        ) : null}
        {trade.margin_ratio != null ? (
          <Chip
            size="small"
            variant="outlined"
            label={`Margin ${(Number(trade.margin_ratio) * 100).toFixed(1)}%`}
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
      </Stack>
      {trade.description ? (
        <Typography
          variant="caption"
          color="text.secondary"
          sx={{ display: 'block', mt: 0.5 }}
        >
          {trade.description}
        </Typography>
      ) : null}
      <Typography
        variant="caption"
        color="text.secondary"
        sx={{ display: 'block' }}
      >
        {formatDateTime(trade.timestamp)}
      </Typography>
    </Box>
  );
}

export default TaskStrategyTab;
