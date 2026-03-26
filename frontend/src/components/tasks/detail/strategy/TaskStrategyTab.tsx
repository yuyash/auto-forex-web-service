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
  Typography,
  alpha,
  useMediaQuery,
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import { useTheme } from '@mui/material/styles';
import { useTranslation } from 'react-i18next';
import { useTaskStrategyEvents } from '../../../../hooks/useTaskStrategyEvents';
import { TaskType } from '../../../../types/common';
import type { StrategyCycle } from '../../../../types/strategyVisualization';
import { StrategyGroupChart } from './StrategyGroupChart';

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
      if (isMobile) setMobileShowDetail(true);
    },
    [isMobile]
  );

  const selectedCycle =
    displayedCycles.find((c) => c.cycle_id === selectedCycleId) ??
    displayedCycles[0] ??
    null;

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
    <Box sx={{ p: 3 }}>
      {summary ? (
        <Stack direction="row" spacing={1} sx={{ mb: 2, flexWrap: 'wrap' }}>
          <Chip label={`Cycles: ${summary.cycle_count}`} />
          <Chip label={`Active: ${summary.active_count}`} />
          <Chip label={`Completed: ${summary.completed_count}`} />
          <Chip label={`Trades: ${summary.total_trades}`} />
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
          alignItems: 'start',
          maxHeight: { lg: 'calc(100vh - 200px)' },
        }}
      >
        {/* Sidebar */}
        <Paper
          variant="outlined"
          sx={{
            display: isMobile && mobileShowDetail ? 'none' : 'flex',
            flexDirection: 'column',
            maxHeight: { lg: 'calc(100vh - 200px)' },
            overflowY: { lg: 'auto' },
          }}
        >
          <Box sx={{ p: 2, flexShrink: 0 }}>
            <Typography variant="subtitle1">Cycles</Typography>
            <Stack direction="row" spacing={1} sx={{ mt: 1.5 }}>
              <Chip
                size="small"
                clickable
                color={sortOrder === 'asc' ? 'primary' : 'default'}
                variant={sortOrder === 'asc' ? 'filled' : 'outlined'}
                label="Oldest"
                onClick={() => setSortOrder('asc')}
              />
              <Chip
                size="small"
                clickable
                color={sortOrder === 'desc' ? 'primary' : 'default'}
                variant={sortOrder === 'desc' ? 'filled' : 'outlined'}
                label="Newest"
                onClick={() => setSortOrder('desc')}
              />
            </Stack>
            <Stack direction="row" spacing={1} sx={{ mt: 1 }}>
              <Chip
                size="small"
                clickable
                color={statusFilter === 'active' ? 'primary' : 'default'}
                variant={statusFilter === 'active' ? 'filled' : 'outlined'}
                label="Active"
                onClick={() =>
                  setStatusFilter((p) => (p === 'active' ? 'all' : 'active'))
                }
              />
              <Chip
                size="small"
                clickable
                color={statusFilter === 'completed' ? 'primary' : 'default'}
                variant={statusFilter === 'completed' ? 'filled' : 'outlined'}
                label="Completed"
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
                <Alert severity="info">No cycles found</Alert>
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
                      label={cycle.status}
                      color={getStatusColor(cycle.status)}
                    />
                    <Chip
                      size="small"
                      variant="outlined"
                      label={`${cycle.trade_count} trades`}
                    />
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
            maxHeight: { lg: 'calc(100vh - 200px)' },
            overflowY: { lg: 'auto' },
          }}
        >
          {selectedCycle ? (
            <Box sx={{ p: 2 }}>
              {isMobile ? (
                <IconButton
                  onClick={() => setMobileShowDetail(false)}
                  size="small"
                  aria-label="Back"
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
                  {selectedCycle.direction.toUpperCase()} Cycle
                </Typography>
                <Chip
                  label={selectedCycle.status}
                  size="small"
                  color={getStatusColor(selectedCycle.status)}
                />
              </Stack>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                {formatDateTime(selectedCycle.started_at)} →{' '}
                {formatDateTime(selectedCycle.ended_at)}
              </Typography>
              <Typography
                variant="caption"
                color="text.secondary"
                sx={{ mb: 1, display: 'block', fontFamily: 'monospace' }}
              >
                {selectedCycle.cycle_id}
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                {selectedCycle.open_count} opens, {selectedCycle.close_count}{' '}
                closes
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
                  />
                </Paper>
              ) : null}

              <Typography variant="subtitle1" sx={{ mb: 1 }}>
                Trades
              </Typography>
              <Divider sx={{ mb: 1 }} />
              {selectedCycle.trades.map((trade, index) => (
                <React.Fragment key={trade.id}>
                  <Box sx={{ py: 1, px: 0.5 }}>
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
                            : 'CLOSE'
                        }
                        color={
                          trade.execution_method === 'open_position'
                            ? 'info'
                            : 'default'
                        }
                        variant="outlined"
                      />
                      <Chip
                        size="small"
                        label={trade.direction === 'buy' ? 'BUY' : 'SELL'}
                        color={trade.direction === 'buy' ? 'success' : 'error'}
                        variant="outlined"
                      />
                      <Typography
                        variant="body2"
                        sx={{ fontFamily: 'monospace' }}
                      >
                        {trade.units} @ {Number(trade.price).toFixed(2)}
                      </Typography>
                      {trade.layer_index != null ? (
                        <Typography variant="caption" color="text.secondary">
                          L{trade.layer_index}
                        </Typography>
                      ) : null}
                      {trade.retracement_count != null ? (
                        <Typography variant="caption" color="text.secondary">
                          R{trade.retracement_count}
                        </Typography>
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
                  {index < selectedCycle.trades.length - 1 ? <Divider /> : null}
                </React.Fragment>
              ))}
            </Box>
          ) : (
            <Box sx={{ p: 3 }}>
              <Alert severity="info">No cycles found</Alert>
            </Box>
          )}
        </Paper>
      </Box>
    </Box>
  );
}

export default TaskStrategyTab;
