import React, { useCallback, useMemo, useRef, useState } from 'react';
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
  enableRealTimeUpdates = false,
}: TaskStrategyTabProps) {
  const { t } = useTranslation(['common']);
  const theme = useTheme();
  const { data, isLoading, error } = useTaskStrategyEvents({
    taskId,
    taskType,
    executionRunId,
    enableRealTimeUpdates,
  });

  const cycles = useMemo<StrategyCycle[]>(() => data?.cycles ?? [], [data]);
  const lastTickTimestamp = data?.last_tick_timestamp ?? null;

  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('asc');
  const [statusFilter, setStatusFilter] = useState<
    'all' | 'active' | 'completed'
  >('all');
  const [selectedCycleId, setSelectedCycleId] = useState<string | null>(null);
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

  const selectedCycle =
    displayedCycles.find((c) => c.cycle_id === selectedCycleId) ??
    displayedCycles[0] ??
    null;

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
          sx={{ mb: 2, flexWrap: 'wrap', flexShrink: 0 }}
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
          <Box sx={{ p: 2, flexShrink: 0 }}>
            <Typography variant="subtitle1">
              {t('common:strategyVisualization.cycleList.title')}
            </Typography>
            <Stack direction="row" spacing={1} sx={{ mt: 1.5 }}>
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
            </Stack>
            <Stack direction="row" spacing={1} sx={{ mt: 1 }}>
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
            </Stack>
          </Box>
          <Divider />
          <Box
            sx={{
              p: 1.5,
              display: 'grid',
              gap: 1.25,
              overflowY: 'auto',
              flexGrow: 1,
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
                <IconButton
                  onClick={() => setMobileShowDetail(false)}
                  size="small"
                  aria-label={t('common:strategyVisualization.cycleList.back')}
                  sx={{ mb: 1 }}
                >
                  <ArrowBackIcon />
                </IconButton>
              ) : null}
              <Stack
                direction="row"
                spacing={1}
                sx={{ mb: 1, flexWrap: 'wrap' }}
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
              </Stack>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                {formatDateTime(selectedCycle.started_at)} →{' '}
                {formatDateTime(selectedCycle.ended_at ?? lastTickTimestamp)}
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
                    lastTickTimestamp={lastTickTimestamp}
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
                const isOpen = trade.execution_method === 'open_position';
                // Task 1: Initial entry always shows L1, R0
                const displayLayer = isInitialEntry ? 1 : trade.layer_index;
                const displayRet = isInitialEntry ? 0 : trade.retracement_count;

                return (
                  <React.Fragment key={trade.id}>
                    <TradeRow
                      trade={trade}
                      isInitialEntry={isInitialEntry}
                      isSelected={isSelected}
                      isOpen={isOpen}
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
                {t('common:strategyVisualization.cycleList.noCyclesFound')}
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
  isOpen,
  displayLayer,
  displayRet,
  onToggleSelection,
  onOpenLifecycle,
}: {
  trade: CycleTrade;
  isInitialEntry: boolean;
  isSelected: boolean;
  isOpen: boolean;
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
        {/* Task 3: Lifecycle button for OPEN trades with position_id */}
        {isOpen && trade.position_id ? (
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
