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
import type { StrategyVisualizationStep } from '../../../../types/strategyVisualization';

interface TaskStrategyTabProps {
  taskId: string | number;
  taskType: TaskType;
  executionRunId?: string;
  enableRealTimeUpdates?: boolean;
}

interface ParentRunGroup {
  group_id: string;
  root_entry_id?: number | null;
  started_at?: string | null;
  ended_at?: string | null;
  status: string;
  root_direction?: string | null;
  root_basket?: string | null;
  checks?: Record<string, unknown>;
  steps: StrategyVisualizationStep[];
}

interface DisplayRun {
  id: string;
  parentGroupId: string;
  runType: 'trend' | 'counter';
  displayLabel: string;
  status: string;
  startedAt?: string | null;
  endedAt?: string | null;
  rootEntryId?: number | null;
  rootDirection?: string | null;
  steps: StrategyVisualizationStep[];
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
  step: StrategyVisualizationStep
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
  step: StrategyVisualizationStep,
  themeMode: 'light' | 'dark'
): string {
  if (step.validation_status === 'fail') {
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

function isTrendStep(step: StrategyVisualizationStep): boolean {
  return step.basket === 'trend' || step.kind === 'trend_tp';
}

function isCounterStep(step: StrategyVisualizationStep): boolean {
  return step.basket === 'counter' || step.kind === 'counter_tp';
}

function buildDisplayRunStatus(
  steps: StrategyVisualizationStep[],
  parentStatus: string
): string {
  const hasProtection = steps.some((step) =>
    ['shrink', 'rebalance', 'lock_hedge_neutralize'].includes(step.kind)
  );
  if (hasProtection || parentStatus === 'intervened') {
    return 'intervened';
  }

  const opened = new Set(
    steps
      .filter(
        (step) => step.event_type === 'open_position' && step.entry_id != null
      )
      .map((step) => Number(step.entry_id))
  );
  const closed = new Set(
    steps
      .filter(
        (step) => step.event_type === 'close_position' && step.entry_id != null
      )
      .map((step) => Number(step.entry_id))
  );
  const hasOpenLeft = Array.from(opened).some(
    (entryId) => !closed.has(entryId)
  );
  return hasOpenLeft ? 'active' : 'completed';
}

function buildDisplayRuns(
  groups: ParentRunGroup[],
  t: (key: string, options?: Record<string, unknown>) => string
): DisplayRun[] {
  const runs: Omit<DisplayRun, 'displayLabel'>[] = [];

  for (const group of groups) {
    const trendSteps = group.steps.filter(isTrendStep);

    // Build a single trend run per group (one Initial entry → one trend cycle)
    if (trendSteps.length > 0) {
      runs.push({
        id: `${group.group_id}:trend:1`,
        parentGroupId: group.group_id,
        runType: 'trend',
        status: buildDisplayRunStatus(trendSteps, group.status),
        startedAt: trendSteps[0]?.timestamp ?? null,
        endedAt: trendSteps[trendSteps.length - 1]?.timestamp ?? null,
        rootEntryId: group.root_entry_id,
        rootDirection: group.root_direction,
        steps: trendSteps,
      });
    }

    // Build counter runs — do NOT include the root trend step.
    // Split into sub-runs when all open counter entries have been closed.
    const counterSteps = group.steps.filter(isCounterStep);
    if (counterSteps.length > 0) {
      let currentCounterSteps: StrategyVisualizationStep[] = [];
      const openCounterEntries = new Set<number>();
      let counterRunIndex = 0;
      for (const step of counterSteps) {
        currentCounterSteps.push(step);
        if (step.event_type === 'open_position' && step.entry_id != null) {
          openCounterEntries.add(Number(step.entry_id));
        }
        if (step.event_type === 'close_position' && step.entry_id != null) {
          openCounterEntries.delete(Number(step.entry_id));
        }
        if (openCounterEntries.size === 0 && currentCounterSteps.length > 0) {
          counterRunIndex += 1;
          runs.push({
            id: `${group.group_id}:counter:${counterRunIndex}`,
            parentGroupId: group.group_id,
            runType: 'counter',
            status: buildDisplayRunStatus(currentCounterSteps, group.status),
            startedAt: currentCounterSteps[0]?.timestamp ?? null,
            endedAt:
              currentCounterSteps[currentCounterSteps.length - 1]?.timestamp ??
              null,
            rootEntryId: group.root_entry_id,
            rootDirection: group.root_direction,
            steps: currentCounterSteps,
          });
          currentCounterSteps = [];
          openCounterEntries.clear();
        }
      }
      if (currentCounterSteps.length > 0) {
        counterRunIndex += 1;
        runs.push({
          id: `${group.group_id}:counter:${counterRunIndex}`,
          parentGroupId: group.group_id,
          runType: 'counter',
          status: buildDisplayRunStatus(currentCounterSteps, group.status),
          startedAt: currentCounterSteps[0]?.timestamp ?? null,
          endedAt:
            currentCounterSteps[currentCounterSteps.length - 1]?.timestamp ??
            null,
          rootEntryId: group.root_entry_id,
          rootDirection: group.root_direction,
          steps: currentCounterSteps,
        });
      }
    }
  }

  const oldestFirst = [...runs].sort((a, b) => {
    const aTime = a.startedAt ? new Date(a.startedAt).getTime() : 0;
    const bTime = b.startedAt ? new Date(b.startedAt).getTime() : 0;
    return aTime - bTime;
  });

  return oldestFirst.map((run, index) => ({
    ...run,
    displayLabel: t(`common:strategyVisualization.${run.runType}RunLabel`, {
      number: index + 1,
    }),
  }));
}

function StrategyRunMiniChart({
  steps,
  compact = false,
  t,
}: {
  steps: StrategyVisualizationStep[];
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
  step: StrategyVisualizationStep;
  t: (key: string, options?: Record<string, unknown>) => string;
}) {
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
          price: formatValue(step.price ?? step.entry_price),
          exit: formatValue(step.actual_exit_price ?? step.exit_price),
        })}
      </Typography>
    </Box>
  );
}

export function TaskStrategyTab({
  taskId,
  taskType,
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

  const parentGroups = useMemo<ParentRunGroup[]>(() => {
    if (data?.view_model.kind !== 'snowball_runs') return [];
    return [...data.view_model.groups].sort((a, b) => {
      const aTime = a.started_at ? new Date(a.started_at).getTime() : 0;
      const bTime = b.started_at ? new Date(b.started_at).getTime() : 0;
      return aTime - bTime;
    });
  }, [data]);

  const displayRuns = useMemo(
    () => buildDisplayRuns(parentGroups, t),
    [parentGroups, t]
  );

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

  const displayedRuns = useMemo(() => {
    let runs = sortOrder === 'asc' ? displayRuns : [...displayRuns].reverse();
    if (runTypeFilter !== 'all') {
      runs = runs.filter((run) => run.runType === runTypeFilter);
    }
    return runs;
  }, [displayRuns, sortOrder, runTypeFilter]);

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

  const selectedRun =
    displayedRuns.find((run) => run.id === selectedRunId) ??
    displayedRuns[0] ??
    null;

  const summary = useMemo(
    () => ({
      totalRuns: displayRuns.length,
      activeRuns: displayRuns.filter((run) => run.status === 'active').length,
      completedRuns: displayRuns.filter((run) => run.status === 'completed')
        .length,
      intervenedRuns: displayRuns.filter((run) => run.status === 'intervened')
        .length,
      counterRuns: displayRuns.filter((run) => run.runType === 'counter')
        .length,
    }),
    [displayRuns]
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
            {displayedRuns.map((run) => (
              <Box
                key={run.id}
                role="button"
                tabIndex={0}
                onClick={() => handleSelectRun(run.id)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault();
                    handleSelectRun(run.id);
                  }
                }}
                sx={{
                  p: 1.5,
                  borderRadius: 2,
                  border: '1px solid',
                  borderColor:
                    run.id === selectedRun?.id ? 'primary.main' : 'divider',
                  bgcolor:
                    run.id === selectedRun?.id
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
                    {run.displayLabel}
                  </Typography>
                  <Chip
                    size="small"
                    label={localizeLabel(run.status, t)}
                    color={getStatusColor(run.status)}
                  />
                  <Chip
                    size="small"
                    variant="outlined"
                    label={t(
                      `common:strategyVisualization.${run.runType}RunType`
                    )}
                  />
                </Stack>
                <Typography variant="body2" color="text.secondary">
                  {formatDateTime(run.startedAt)}
                </Typography>
                <Typography
                  variant="caption"
                  color="text.secondary"
                  sx={{ display: 'block', mt: 0.5 }}
                >
                  {`group_id: ${run.parentGroupId}`}
                  {' | '}
                  {t('common:strategyVisualization.runMeta', {
                    rootEntryId: formatValue(run.rootEntryId),
                    stepCount: run.steps.length,
                  })}
                </Typography>
              </Box>
            ))}
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

        {/* Detail panel — on mobile, shown only when a run is selected */}
        <Paper
          variant="outlined"
          sx={{
            minWidth: 0,
            display: isMobile && !mobileShowDetail ? 'none' : 'block',
          }}
        >
          {selectedRun ? (
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
                <Typography variant="h6">{selectedRun.displayLabel}</Typography>
                <Chip
                  label={localizeLabel(selectedRun.status, t)}
                  size="small"
                  color={getStatusColor(selectedRun.status)}
                />
                <Chip
                  label={t(
                    `common:strategyVisualization.${selectedRun.runType}RunType`
                  )}
                  size="small"
                  variant="outlined"
                />
                {selectedRun.rootDirection ? (
                  <Chip
                    label={localizeLabel(selectedRun.rootDirection, t)}
                    size="small"
                    variant="outlined"
                  />
                ) : null}
              </Stack>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                {`${formatDateTime(selectedRun.startedAt)} -> ${formatDateTime(selectedRun.endedAt)}`}
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                {t('common:strategyVisualization.selectedRunHelp', {
                  rootEntryId: formatValue(selectedRun.rootEntryId),
                })}{' '}
                {t(
                  `common:strategyVisualization.${selectedRun.runType}RunSelectedHelp`
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
                      minWidth: Math.max(selectedRun.steps.length * 80, 300),
                    }}
                  >
                    <StrategyRunMiniChart steps={selectedRun.steps} t={t} />
                  </Box>
                </Box>
              </Paper>

              <Typography variant="subtitle1" sx={{ mb: 1 }}>
                {t('common:strategyVisualization.timeline')}
              </Typography>
              <Divider sx={{ mb: 1 }} />
              {selectedRun.steps.map((step, index) => (
                <React.Fragment key={`${selectedRun.id}-${index}`}>
                  <StepRow step={step} t={t} />
                  {index < selectedRun.steps.length - 1 ? <Divider /> : null}
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
