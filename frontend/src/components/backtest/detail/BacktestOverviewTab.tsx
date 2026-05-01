import { useMemo } from 'react';
import { Box, Divider, Grid, Link, Typography } from '@mui/material';
import { useTranslation } from 'react-i18next';
import { Link as RouterLink } from 'react-router-dom';
import { ExecutionHistoryTable } from '../../tasks/display/ExecutionHistoryTable';
import { LatestMetricsSummary } from '../../tasks/detail/LatestMetricsSummary';
import { StrategySnapshotSummary } from '../../tasks/detail/StrategySnapshotSummary';
import { TaskSettingsList } from '../../tasks/detail/TaskSettingsList';
import { buildBacktestTaskSettingDefinitions } from '../../tasks/detail/taskSettingDefinitions';
import type { TaskSummary } from '../../../hooks/useTaskSummary';
import { getStrategyDisplayName } from '../../../hooks/useStrategies';
import type { Strategy } from '../../../services/api/strategies';
import { TaskType, type TaskStatus } from '../../../types/common';
import type { BacktestTask } from '../../../types';
import type { StrategySnapshotResponse } from '../../../types/strategyVisualization';
import type { MetricPoint } from '../../../utils/fetchMetrics';
import { formatAppNumber, formatAppPercent } from '../../../utils/numberFormat';
import { formatDateTimeInTimezone } from '../../../utils/timezone';

const BACKTEST_PERIOD_SETTING_KEYS = new Set([
  'start_time',
  'end_time',
  'tick_granularity',
  'tick_window_value_mode',
  'max_tick_gap_hours',
]);

interface BacktestOverviewTabProps {
  taskId: string;
  task: BacktestTask;
  summary: TaskSummary;
  currentStatus?: TaskStatus;
  strategies: Strategy[];
  pnlCurrency: string;
  latestMetrics?: MetricPoint | null;
  strategySnapshot?: StrategySnapshotResponse | null;
  strategySnapshotLoading?: boolean;
  strategySnapshotError?: Error | null;
  timezone: string;
  language?: string;
  isViewingHistorical?: boolean;
  historicalStrategyConfig?: {
    id: string;
    name: string;
    strategy_type: string;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    parameters: Record<string, any>;
  } | null;
  executionId?: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  historicalTaskConfig?: Record<string, any> | null;
  onOpenConfiguration: () => void;
}

export function BacktestOverviewTab({
  taskId,
  task,
  summary,
  strategies,
  pnlCurrency,
  latestMetrics,
  strategySnapshot,
  strategySnapshotLoading,
  strategySnapshotError,
  timezone,
  language,
  isViewingHistorical = false,
  historicalStrategyConfig,
  historicalTaskConfig,
  onOpenConfiguration,
}: BacktestOverviewTabProps) {
  const { t } = useTranslation(['backtest', 'common']);

  // When viewing a historical execution, prefer snapshot values for task settings
  const effectiveStartTime =
    (isViewingHistorical && historicalTaskConfig?.start_time) ||
    task.start_time;
  const effectiveEndTime =
    (isViewingHistorical && historicalTaskConfig?.end_time) || task.end_time;
  const effectiveInstrument =
    (isViewingHistorical && historicalTaskConfig?.instrument) ||
    task.instrument;
  const latestMarginRatioRaw = latestMetrics?.metrics.margin_ratio;
  const latestMarginRatio =
    latestMarginRatioRaw != null && latestMarginRatioRaw !== ''
      ? Number(latestMarginRatioRaw)
      : null;
  const displayedMarginRatio = Number.isFinite(latestMarginRatio)
    ? latestMarginRatio
    : summary.execution.marginRatio;

  const taskSettings = useMemo(
    () =>
      buildBacktestTaskSettingDefinitions(t, timezone, language)
        .filter(
          (definition) => !BACKTEST_PERIOD_SETTING_KEYS.has(definition.key)
        )
        .map((definition) => {
          if (definition.key === 'config_name') {
            return {
              ...definition,
              render: () => {
                const label =
                  (isViewingHistorical && historicalStrategyConfig?.name) ||
                  task.config_name;
                const targetId =
                  (isViewingHistorical && historicalStrategyConfig?.id) ||
                  task.config_id;

                if (targetId) {
                  return (
                    <Link
                      component={RouterLink}
                      to={`/configurations/${targetId}`}
                      variant="body1"
                      sx={{ display: 'inline-block', maxWidth: '100%' }}
                    >
                      {label}
                    </Link>
                  );
                }

                return (
                  <Link
                    component="button"
                    variant="body1"
                    onClick={onOpenConfiguration}
                    sx={{ textAlign: 'left' }}
                  >
                    {label}
                  </Link>
                );
              },
            };
          }

          if (definition.key === 'strategy_type') {
            return {
              ...definition,
              render: () =>
                getStrategyDisplayName(
                  strategies,
                  (isViewingHistorical &&
                    historicalStrategyConfig?.strategy_type) ||
                    task.strategy_type
                ),
            };
          }

          return definition;
        }),
    [
      historicalStrategyConfig?.id,
      historicalStrategyConfig?.name,
      historicalStrategyConfig?.strategy_type,
      isViewingHistorical,
      language,
      onOpenConfiguration,
      strategies,
      t,
      task.config_id,
      task.config_name,
      task.strategy_type,
      timezone,
    ]
  );

  return (
    <Box sx={{ p: { xs: 1.5, sm: 3 } }}>
      <Grid container spacing={{ xs: 2, sm: 3 }}>
        <Grid size={{ xs: 12 }}>
          <TaskSettingsList
            title={t('common:labels.taskInformation')}
            task={task as unknown as Record<string, unknown>}
            snapshot={historicalTaskConfig}
            definitions={taskSettings}
          />
        </Grid>

        <Grid size={{ xs: 12 }}>
          <Divider sx={{ my: 2 }} />
          <Typography variant="h6" gutterBottom>
            {t('backtest:detail.backtestPeriod')}
          </Typography>
          <Box sx={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
            <Box>
              <Typography variant="caption" color="text.secondary">
                {t('backtest:detail.startTime')}
              </Typography>
              <Typography variant="body1">
                {formatDateTimeInTimezone(
                  effectiveStartTime,
                  timezone,
                  language,
                  {
                    includeTimezone: true,
                  }
                )}
              </Typography>
            </Box>
            <Box>
              <Typography variant="caption" color="text.secondary">
                {t('backtest:detail.endTime')}
              </Typography>
              <Typography variant="body1">
                {formatDateTimeInTimezone(
                  effectiveEndTime,
                  timezone,
                  language,
                  {
                    includeTimezone: true,
                  }
                )}
              </Typography>
            </Box>
            <Box>
              <Typography variant="caption" color="text.secondary">
                {t('backtest:detail.tickGranularity')}
              </Typography>
              <Typography variant="body1">
                {t(
                  `backtest:form.tickGranularityOptions.${task.tick_granularity}`,
                  task.tick_granularity
                )}
              </Typography>
            </Box>
            {task.tick_granularity !== 'tick' && (
              <Box>
                <Typography variant="caption" color="text.secondary">
                  {t('backtest:detail.tickWindowValueMode')}
                </Typography>
                <Typography variant="body1">
                  {t(
                    `backtest:form.tickWindowValueModeOptions.${task.tick_window_value_mode}`,
                    task.tick_window_value_mode
                  )}
                </Typography>
              </Box>
            )}
            <Box>
              <Typography variant="caption" color="text.secondary">
                {t(
                  'backtest:form.maxTickGapHours',
                  'Max tick gap before fail (hours)'
                )}
              </Typography>
              <Typography variant="body1">
                {task.max_tick_gap_hours ?? 120}
              </Typography>
            </Box>
          </Box>
        </Grid>

        <Grid size={{ xs: 12 }}>
          <Divider sx={{ my: 2 }} />
          <Typography variant="h6" gutterBottom>
            {t('backtest:detail.results')}
          </Typography>
          <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
            <Box>
              <Typography variant="caption" color="text.secondary">
                {t('backtest:detail.realizedPnl')} ({pnlCurrency})
              </Typography>
              <Typography
                variant="body1"
                color={
                  summary.pnl.realized >= 0 ? 'success.main' : 'error.main'
                }
              >
                {summary.pnl.realized >= 0 ? '+' : ''}
                {formatAppNumber(summary.pnl.realized, {
                  minimumFractionDigits: 2,
                  maximumFractionDigits: 2,
                })}{' '}
                {pnlCurrency}
              </Typography>
            </Box>
            <Box>
              <Typography variant="caption" color="text.secondary">
                {t('backtest:detail.unrealizedPnl')} ({pnlCurrency})
              </Typography>
              <Typography
                variant="body1"
                color={
                  summary.pnl.unrealized >= 0 ? 'success.main' : 'error.main'
                }
              >
                {summary.pnl.unrealized >= 0 ? '+' : ''}
                {formatAppNumber(summary.pnl.unrealized, {
                  minimumFractionDigits: 2,
                  maximumFractionDigits: 2,
                })}{' '}
                {pnlCurrency}
              </Typography>
            </Box>
            {summary.execution.currentBalance != null && (
              <Box>
                <Typography variant="caption" color="text.secondary">
                  {t('backtest:detail.currentBalance')}
                </Typography>
                <Typography variant="body1">
                  {summary.execution.currentBalanceDisplay != null &&
                  summary.execution.displayCurrency &&
                  summary.execution.displayCurrency !==
                    summary.execution.accountCurrency ? (
                    <>
                      {formatAppNumber(
                        summary.execution.currentBalanceDisplay,
                        {
                          maximumFractionDigits: 0,
                        }
                      )}{' '}
                      {summary.execution.displayCurrency}
                      <Typography
                        component="span"
                        variant="body2"
                        color="text.secondary"
                        sx={{ ml: 1 }}
                      >
                        (
                        {formatAppNumber(summary.execution.currentBalance, {
                          minimumFractionDigits: 2,
                          maximumFractionDigits: 2,
                        })}{' '}
                        {summary.execution.accountCurrency})
                      </Typography>
                    </>
                  ) : (
                    <>
                      {formatAppNumber(summary.execution.currentBalance, {
                        minimumFractionDigits: 2,
                        maximumFractionDigits: 2,
                      })}{' '}
                      {summary.execution.accountCurrency || pnlCurrency}
                    </>
                  )}
                </Typography>
              </Box>
            )}
            <Box>
              <Typography variant="caption" color="text.secondary">
                {t('backtest:detail.totalTradesCount')}
              </Typography>
              <Typography variant="body1">
                {formatAppNumber(summary.counts.totalTrades)}
              </Typography>
            </Box>
            <Box>
              <Typography variant="caption" color="text.secondary">
                {t('backtest:detail.openPositions')}
              </Typography>
              <Typography variant="body1">
                {formatAppNumber(summary.counts.openPositions)}
              </Typography>
            </Box>
            <Box>
              <Typography variant="caption" color="text.secondary">
                {t('backtest:detail.closedPositions')}
              </Typography>
              <Typography variant="body1">
                {formatAppNumber(summary.counts.closedPositions)}
              </Typography>
            </Box>
            <Box>
              <Typography variant="caption" color="text.secondary">
                {t('backtest:detail.openLongUnits')}
              </Typography>
              <Typography variant="body1">
                {formatAppNumber(summary.counts.openLongUnits ?? 0)}
              </Typography>
            </Box>
            <Box>
              <Typography variant="caption" color="text.secondary">
                {t('backtest:detail.openShortUnits')}
              </Typography>
              <Typography variant="body1">
                {formatAppNumber(summary.counts.openShortUnits ?? 0)}
              </Typography>
            </Box>
            {summary.execution.ticksProcessed > 0 && (
              <Box>
                <Typography variant="caption" color="text.secondary">
                  {t('backtest:detail.ticksProcessed')}
                </Typography>
                <Typography variant="body1">
                  {formatAppNumber(summary.execution.ticksProcessed)}
                </Typography>
              </Box>
            )}
            {displayedMarginRatio != null && (
              <Box>
                <Typography variant="caption" color="text.secondary">
                  {t('common:labels.marginRatio')}
                </Typography>
                <Typography variant="body1">
                  {formatAppPercent(displayedMarginRatio * 100, 1)}
                </Typography>
              </Box>
            )}
            {summary.execution.currentAtr != null && (
              <Box>
                <Typography variant="caption" color="text.secondary">
                  {t('common:labels.currentAtr')}
                </Typography>
                <Typography variant="body1">
                  {formatAppNumber(summary.execution.currentAtr, {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2,
                  })}
                </Typography>
              </Box>
            )}
            <LatestMetricsSummary
              latest={latestMetrics ?? null}
              pnlCurrency={pnlCurrency}
              summary={summary}
            />
          </Box>
        </Grid>

        <Grid size={{ xs: 12 }}>
          <StrategySnapshotSummary
            snapshot={strategySnapshot ?? null}
            isLoading={strategySnapshotLoading}
            error={strategySnapshotError}
          />
        </Grid>

        <Grid size={{ xs: 12 }}>
          <Divider sx={{ my: 2 }} />
          <ExecutionHistoryTable
            taskId={taskId}
            taskType={TaskType.BACKTEST}
            instrument={effectiveInstrument}
          />
        </Grid>
      </Grid>
    </Box>
  );
}
