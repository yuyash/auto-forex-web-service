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
import type {
  DisplayCycle,
  DisplayCycleStep,
  StrategyVisualizationStep,
} from '../../../../types/strategyVisualization';
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

function formatValue(value: string | number | null | undefined): string {
  return value == null || value === '' ? '-' : String(value);
}

function toDisplayLabel(value: string | null | undefined): string {
  if (!value) return '-';
  return value
    .split('_')
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

function localizeLabel(
  value: string | null | undefined,
  t: (key: string, options?: Record<string, unknown>) => string
): string {
  if (!value) return '-';
  const translated = t(`common:strategyVisualization.labels.${value}`);
  if (translated !== `common:strategyVisualization.labels.${value}`) {
    return translated;
  }
  return toDisplayLabel(value);
}

function getLayerRetracementLabel(
  step: StrategyVisualizationStep | DisplayCycleStep
): string | null {
  const layer = step.layer_number;
  const retracement = step.retracement_count;
  if (layer != null || retracement != null) {
    return `L${formatValue(layer)} / R${formatValue(retracement)}`;
  }

  const sourceText = step.description ?? '';
  const match = sourceText.match(/L(\d+)\s*\/\s*R(\d+)/i);
  if (match) {
    return `L${match[1]} / R${match[2]}`;
  }

  return null;
}

function getStatusColor(status: string): 'success' | 'warning' | 'default' {
  if (status === 'completed') return 'success';
  if (status === 'intervened') return 'warning';
  return 'default';
}

function getStepTone(
  step: StrategyVisualizationStep | DisplayCycleStep,
  themeMode: 'light' | 'dark'
): string {
  const validationStatus =
    'validation_status' in step ? step.validation_status : undefined;
  if (validationStatus === 'fail') {
    return themeMode === 'dark' ? '#f87171' : '#dc2626';
  }
  if (step.kind.includes('trend_tp')) {
    return themeMode === 'dark' ? '#34d399' : '#059669';
  }
  if (step.basket === 'counter') {
    return themeMode === 'dark' ? '#fbbf24' : '#d97706';
  }
  if (
    step.kind.includes('shrink') ||
    step.kind.includes('rebalance') ||
    step.kind.includes('lock')
  ) {
    return themeMode === 'dark' ? '#c084fc' : '#7c3aed';
  }
  return themeMode === 'dark' ? '#60a5fa' : '#2563eb';
}

/**
 * Convert backend display_cycles into labelled cycles for rendering.
 * Assigns sequential display labels based on sorted order.
 */
function labelDisplayCycles(
  cycles: DisplayCycle[],
  t: (key: string, options?: Record<string, unknown>) => string
): DisplayCycle[] {
  // cycles from the API are already sorted by started_at ascending
  return cycles.map((cycle, index) => ({
    ...cycle,
    displayLabel: t(
      `common:strategyVisualization.${cycle.cycle_type}RunLabel`,
      { number: index + 1 }
    ),
  }));
}

function StrategyRunMiniChart({
  steps,
  compact = false,
  t,
}: {
  steps: (StrategyVisualizationStep | DisplayCycleStep)[];
  compact?: boolean;
  t: (key: string, options?: Record<string, unknown>) => string;
}) {
  const theme = useTheme();
  const count = Math.max(steps.length, 1);

  return (
    <Box
      sx={{
        position: 'relative',
        pt: compact ? 0.5 : 2,
        pb: compact ? 0.5 : 1,
      }}
    >
      <Box
        sx={{
          position: 'absolute',
          left: compact ? 10 : 14,
          right: compact ? 10 : 14,
          top: compact ? 12 : 20,
          height: 2,
          bgcolor: 'divider',
        }}
      />
      <Box
        sx={{
          display: 'grid',
          gridTemplateColumns: `repeat(${count}, minmax(0, 1fr))`,
          gap: compact ? 0.75 : 1,
          alignItems: 'start',
        }}
      >
        {steps.map((step, index) => {
          const layerRetracementLabel = getLayerRetracementLabel(step);
          return (
            <Box
              key={`${step.event_type}-${step.timestamp}-${index}`}
              sx={{
                minWidth: 0,
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                gap: compact ? 0.5 : 0.75,
              }}
            >
              <Box
                sx={{
                  width: compact ? 10 : 14,
                  height: compact ? 10 : 14,
                  borderRadius: '50%',
                  bgcolor: getStepTone(step, theme.palette.mode),
                  border: `2px solid ${theme.palette.background.paper}`,
                  boxShadow: `0 0 0 1px ${alpha(theme.palette.text.primary, 0.14)}`,
                  zIndex: 1,
                }}
              />
              {!compact ? (
                <>
                  {layerRetracementLabel ? (
                    <Typography
                      variant="caption"
                      color="text.secondary"
                      sx={{ textAlign: 'center', lineHeight: 1.1 }}
                    >
                      {layerRetracementLabel}
                    </Typography>
                  ) : null}
                  <Typography
                    variant="caption"
                    sx={{
                      fontWeight: 700,
                      textAlign: 'center',
                      lineHeight: 1.2,
                    }}
                  >
                    {localizeLabel(step.kind, t)}
                  </Typography>
                  <Typography
                    variant="caption"
                    color="text.secondary"
                    sx={{ textAlign: 'center', lineHeight: 1.2 }}
                  >
                    {formatDateTime(step.timestamp)}
                  </Typography>
                </>
              ) : null}
            </Box>
          );
        })}
      </Box>
    </Box>
  );
}

function StepRow({
  step,
  t,
}: {
  step: StrategyVisualizationStep | DisplayCycleStep;
  t: (key: string, options?: Record<string, unknown>) => string;
}) {
  const price =
    'price' in step
      ? ((step as StrategyVisualizationStep).price ?? step.entry_price)
      : step.entry_price;
  return (
    <Box
      sx={{
        py: 1.25,
        display: 'grid',
        gridTemplateColumns: { xs: '1fr', md: '170px 1fr 240px' },
        gap: 1.5,
      }}
    >
      <Typography variant="body2" color="text.secondary">
        {formatDateTime(step.timestamp)}
      </Typography>
      <Box>
        <Stack direction="row" spacing={1} sx={{ mb: 0.5, flexWrap: 'wrap' }}>
          <Chip size="small" label={localizeLabel(step.kind, t)} />
          {step.basket ? (
            <Chip
              size="small"
              variant="outlined"
              label={localizeLabel(step.basket, t)}
            />
          ) : null}
          {step.validation_status ? (
            <Chip
              size="small"
              color={
                step.validation_status === 'pass'
                  ? 'success'
                  : step.validation_status === 'fail'
                    ? 'error'
                    : 'warning'
              }
              label={localizeLabel(step.validation_status, t)}
            />
          ) : null}
        </Stack>
        <Typography variant="body2">
          {step.description || localizeLabel(step.event_type, t)}
        </Typography>
      </Box>
      <Typography variant="body2" color="text.secondary">
        {t('common:strategyVisualization.stepPriceLine', {
          price: formatValue(price),
          exit: formatValue(step.actual_exit_price ?? step.exit_price),
        })}
      </Typography>
    </Box>
  );
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

  // Use display_cycles from the API response directly (backend handles splitting)
  const displayCycles = useMemo<DisplayCycle[]>(() => {
    if (data?.view_model.kind !== 'snowball_runs') return [];
    const raw = data.view_model.display_cycles ?? [];
    return labelDisplayCycles(raw, t);
  }, [data, t]);

  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('asc');
  const [runTypeFilter, setRunTypeFilter] = useState<
    'all' | 'trend' | 'counter'
  >('all');
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
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
    let cycles =
      sortOrder === 'asc' ? displayCycles : [...displayCycles].reverse();
    if (runTypeFilter !== 'all') {
      cycles = cycles.filter((c) => c.cycle_type === runTypeFilter);
    }
    return cycles;
  }, [displayCycles, sortOrder, runTypeFilter]);

  const handleSelectRun = useCallback(
    (id: string) => {
      setSelectedRunId(id);
      if (isMobile) {
        setMobileShowDetail(true);
      }
    },
    [isMobile]
  );

  const handleBackToList = useCallback(() => {
    setMobileShowDetail(false);
  }, []);

  const selectedCycle =
    displayedCycles.find((c) => c.cycle_id === selectedRunId) ??
    displayedCycles[0] ??
    null;

  const summary = useMemo(
    () => ({
      totalRuns: displayCycles.length,
      activeRuns: displayCycles.filter((c) => c.status === 'active').length,
      completedRuns: displayCycles.filter((c) => c.status === 'completed')
        .length,
      intervenedRuns: displayCycles.filter((c) => c.status === 'intervened')
        .length,
      trendRuns: displayCycles.filter((c) => c.cycle_type === 'trend').length,
      counterRuns: displayCycles.filter((c) => c.cycle_type === 'counter')
        .length,
    }),
    [displayCycles]
  );

  const getUnavailableMessage = () => {
    if (!data?.message) {
      return t('common:strategyVisualization.unavailable');
    }
    if (data.message.includes('has not been executed yet')) {
      return t('common:strategyVisualization.notExecutedYet');
    }
    if (data.message.includes('before the visualization schema update')) {
      return t('common:strategyVisualization.preSchemaUnavailable');
    }
    if (data.message.includes('not implemented for this strategy yet')) {
      return t('common:strategyVisualization.unsupported');
    }
    return t('common:strategyVisualization.unavailable');
  };

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

  if (!data) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="info">
          {t('common:strategyVisualization.noData')}
        </Alert>
      </Box>
    );
  }

  if (!data.supported || data.view_model.kind === 'unsupported') {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="info">{getUnavailableMessage()}</Alert>
      </Box>
    );
  }

  return (
    <Box sx={{ p: 3 }}>
      <Stack direction="row" spacing={1} sx={{ mb: 2, flexWrap: 'wrap' }}>
        <Chip
          label={`${t('common:strategyVisualization.summary.totalRuns')}: ${summary.totalRuns}`}
        />
        <Chip
          label={`${t('common:strategyVisualization.summary.activeRuns')}: ${summary.activeRuns}`}
        />
        <Chip
          label={`${t('common:strategyVisualization.summary.completedRuns')}: ${summary.completedRuns}`}
        />
        <Chip
          label={`${t('common:strategyVisualization.summary.intervenedRuns')}: ${summary.intervenedRuns}`}
        />
        <Chip
          label={`${t('common:strategyVisualization.summary.trendRuns')}: ${summary.trendRuns}`}
        />
        <Chip
          label={`${t('common:strategyVisualization.summary.counterRuns')}: ${summary.counterRuns}`}
        />
      </Stack>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        {t('common:strategyVisualization.summary.runTypeHelp')}
      </Typography>

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
        }}
      >
        {/* Sidebar — hidden on mobile when detail is shown */}
        <Paper
          variant="outlined"
          sx={{
            display: isMobile && mobileShowDetail ? 'none' : 'flex',
            flexDirection: 'column',
            maxHeight: { lg: 'calc(100vh - 200px)' },
            position: { lg: 'sticky' },
            top: { lg: 16 },
          }}
        >
          <Box sx={{ p: 2, flexShrink: 0 }}>
            <Typography variant="subtitle1">{t('common:strategy')}</Typography>
            <Typography variant="body2" color="text.secondary">
              {t('common:strategyVisualization.runTypeHelp')}
            </Typography>
            <Stack direction="row" spacing={1} sx={{ mt: 1.5 }}>
              <Chip
                size="small"
                clickable
                color={sortOrder === 'asc' ? 'primary' : 'default'}
                variant={sortOrder === 'asc' ? 'filled' : 'outlined'}
                label={t('common:strategyVisualization.sortOldest')}
                onClick={() => setSortOrder('asc')}
              />
              <Chip
                size="small"
                clickable
                color={sortOrder === 'desc' ? 'primary' : 'default'}
                variant={sortOrder === 'desc' ? 'filled' : 'outlined'}
                label={t('common:strategyVisualization.sortNewest')}
                onClick={() => setSortOrder('desc')}
              />
            </Stack>
            <Stack direction="row" spacing={1} sx={{ mt: 1 }}>
              <Chip
                size="small"
                clickable
                color={runTypeFilter === 'trend' ? 'primary' : 'default'}
                variant={runTypeFilter === 'trend' ? 'filled' : 'outlined'}
                label={t('common:strategyVisualization.filterTrendOnly')}
                onClick={() =>
                  setRunTypeFilter((prev) =>
                    prev === 'trend' ? 'all' : 'trend'
                  )
                }
              />
              <Chip
                size="small"
                clickable
                color={runTypeFilter === 'counter' ? 'primary' : 'default'}
                variant={runTypeFilter === 'counter' ? 'filled' : 'outlined'}
                label={t('common:strategyVisualization.filterCounterOnly')}
                onClick={() =>
                  setRunTypeFilter((prev) =>
                    prev === 'counter' ? 'all' : 'counter'
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
                  {t('common:strategyVisualization.noGroupedRuns')}
                </Alert>
              </Box>
            ) : (
              displayedCycles.map((cycle) => (
                <Box
                  key={cycle.cycle_id}
                  role="button"
                  tabIndex={0}
                  onClick={() => handleSelectRun(cycle.cycle_id)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' || event.key === ' ') {
                      event.preventDefault();
                      handleSelectRun(cycle.cycle_id);
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
                    sx={{ mb: 1, alignItems: 'center', flexWrap: 'wrap' }}
                  >
                    <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
                      {cycle.display_label}
                    </Typography>
                    <Chip
                      size="small"
                      label={localizeLabel(cycle.status, t)}
                      color={getStatusColor(cycle.status)}
                    />
                    <Chip
                      size="small"
                      variant="outlined"
                      label={t(
                        `common:strategyVisualization.${cycle.cycle_type}RunType`
                      )}
                    />
                  </Stack>
                  <Typography variant="body2" color="text.secondary">
                    {formatDateTime(cycle.started_at)}
                  </Typography>
                  <Typography
                    variant="caption"
                    color="text.secondary"
                    sx={{ display: 'block', mt: 0.5 }}
                  >
                    {`group_id: ${cycle.parent_group_id}`}
                    {' | '}
                    {t('common:strategyVisualization.runMeta', {
                      rootEntryId: formatValue(cycle.root_entry_id),
                      stepCount: cycle.steps.length,
                    })}
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
            position: 'sticky',
            top: 16,
            alignSelf: 'stretch',
            maxHeight: 'calc(100vh - 200px)',
            '&:hover > div, &:active > div': {
              bgcolor: 'primary.main',
            },
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

        {/* Detail panel — on mobile, shown only when a cycle is selected */}
        <Paper
          variant="outlined"
          sx={{
            minWidth: 0,
            display: isMobile && !mobileShowDetail ? 'none' : 'block',
          }}
        >
          {selectedCycle ? (
            <Box sx={{ p: 2 }}>
              {isMobile ? (
                <IconButton
                  onClick={handleBackToList}
                  size="small"
                  aria-label={t('common:actions.back')}
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
                  {selectedCycle.display_label}
                </Typography>
                <Chip
                  label={localizeLabel(selectedCycle.status, t)}
                  size="small"
                  color={getStatusColor(selectedCycle.status)}
                />
                <Chip
                  label={t(
                    `common:strategyVisualization.${selectedCycle.cycle_type}RunType`
                  )}
                  size="small"
                  variant="outlined"
                />
                {selectedCycle.root_direction ? (
                  <Chip
                    label={localizeLabel(selectedCycle.root_direction, t)}
                    size="small"
                    variant="outlined"
                  />
                ) : null}
              </Stack>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                {`${formatDateTime(selectedCycle.started_at)} -> ${formatDateTime(selectedCycle.ended_at)}`}
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                {t('common:strategyVisualization.selectedRunHelp', {
                  rootEntryId: formatValue(selectedCycle.root_entry_id),
                })}{' '}
                {t(
                  `common:strategyVisualization.${selectedCycle.cycle_type}RunSelectedHelp`
                )}
              </Typography>

              <Paper
                variant="outlined"
                sx={{
                  p: 2,
                  mb: 2,
                  bgcolor: alpha(theme.palette.primary.main, 0.03),
                }}
              >
                <Typography variant="subtitle1" sx={{ mb: 1 }}>
                  {t('common:strategyVisualization.flowChart')}
                </Typography>
                <Typography
                  variant="body2"
                  color="text.secondary"
                  sx={{ mb: 1.5 }}
                >
                  {t('common:strategyVisualization.singleRunFlowChartHelp')}
                </Typography>
                <Box sx={{ overflowX: 'auto' }}>
                  <Box
                    sx={{
                      minWidth: Math.max(selectedCycle.steps.length * 80, 300),
                    }}
                  >
                    <StrategyRunMiniChart steps={selectedCycle.steps} t={t} />
                  </Box>
                </Box>
              </Paper>

              {instrument ? (
                <Paper
                  variant="outlined"
                  sx={{
                    p: 2,
                    mb: 2,
                    bgcolor: alpha(theme.palette.primary.main, 0.03),
                  }}
                >
                  <Typography variant="subtitle1" sx={{ mb: 1 }}>
                    {t('common:strategyVisualization.ohlcChart')}
                  </Typography>
                  <StrategyGroupChart
                    instrument={instrument}
                    startTime={selectedCycle.started_at ?? ''}
                    endTime={selectedCycle.ended_at}
                    steps={selectedCycle.steps}
                    height={300}
                  />
                </Paper>
              ) : null}

              <Typography variant="subtitle1" sx={{ mb: 1 }}>
                {t('common:strategyVisualization.timeline')}
              </Typography>
              <Divider sx={{ mb: 1 }} />
              {selectedCycle.steps.map((step, index) => (
                <React.Fragment key={`${selectedCycle.cycle_id}-${index}`}>
                  <StepRow step={step} t={t} />
                  {index < selectedCycle.steps.length - 1 ? <Divider /> : null}
                </React.Fragment>
              ))}
            </Box>
          ) : (
            <Box sx={{ p: 3 }}>
              <Alert severity="info">
                {t('common:strategyVisualization.noGroupedRuns')}
              </Alert>
            </Box>
          )}
        </Paper>
      </Box>
    </Box>
  );
}

export default TaskStrategyTab;
