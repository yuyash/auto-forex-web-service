import { useMemo } from 'react';
import { Alert, Box, Divider, Grid, Link, Typography } from '@mui/material';
import { useTranslation } from 'react-i18next';
import { Link as RouterLink } from 'react-router-dom';
import { ExecutionHistoryTable } from '../../tasks/display/ExecutionHistoryTable';
import { LatestMetricsSummary } from '../../tasks/detail/LatestMetricsSummary';
import { StrategySnapshotSummary } from '../../tasks/detail/StrategySnapshotSummary';
import { TaskSettingsList } from '../../tasks/detail/TaskSettingsList';
import { buildTradingTaskSettingDefinitions } from '../../tasks/detail/taskSettingDefinitions';
import type { TaskSummary } from '../../../hooks/useTaskSummary';
import { getStrategyDisplayName } from '../../../hooks/useStrategies';
import type { Strategy } from '../../../services/api/strategies';
import { TaskType, type TaskStatus } from '../../../types/common';
import type { TradingTask } from '../../../types';
import type { StrategySnapshotResponse } from '../../../types/strategyVisualization';
import type { MetricPoint } from '../../../utils/fetchMetrics';
import { formatAppNumber, formatAppPercent } from '../../../utils/numberFormat';

interface TradingOverviewTabProps {
  taskId: string;
  task: TradingTask;
  summary: TaskSummary;
  currentStatus?: TaskStatus;
  strategies: Strategy[];
  pnlCurrency: string;
  latestMetrics?: MetricPoint | null;
  strategySnapshot?: StrategySnapshotResponse | null;
  strategySnapshotLoading?: boolean;
  strategySnapshotError?: Error | null;
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

export function TradingOverviewTab({
  taskId,
  task,
  summary,
  strategies,
  pnlCurrency,
  latestMetrics,
  strategySnapshot,
  strategySnapshotLoading,
  strategySnapshotError,
  isViewingHistorical = false,
  historicalStrategyConfig,
  historicalTaskConfig,
  onOpenConfiguration,
}: TradingOverviewTabProps) {
  const { t } = useTranslation(['trading', 'common']);

  // When viewing a historical execution, prefer snapshot values
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
      buildTradingTaskSettingDefinitions(t).map((definition) => {
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
      onOpenConfiguration,
      strategies,
      t,
      task.config_id,
      task.config_name,
      task.strategy_type,
    ]
  );
  const recoveryBlockers = summary.execution.recoveryBlockers ?? [];
  const recoveryWarnings = summary.execution.recoveryWarnings ?? [];

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
          {recoveryBlockers.length > 0 ? (
            <Alert severity="error" sx={{ mb: 2 }}>
              {recoveryBlockers[0]}
            </Alert>
          ) : null}
          {recoveryWarnings.length > 0 ? (
            <Alert severity="warning" sx={{ mb: 2 }}>
              {recoveryWarnings[0]}
            </Alert>
          ) : null}
          <Divider sx={{ my: 2 }} />
          <Typography variant="h6" gutterBottom>
            {t('trading:detail.results')}
          </Typography>
          <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
            <Box>
              <Typography variant="caption" color="text.secondary">
                {t('trading:detail.realizedPnl')} ({pnlCurrency})
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
                {t('trading:detail.unrealizedPnl')} ({pnlCurrency})
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
                  {t('trading:detail.currentBalance')}
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
                {t('trading:detail.totalTradesCount')}
              </Typography>
              <Typography variant="body1">
                {formatAppNumber(summary.counts.totalTrades)}
              </Typography>
            </Box>
            <Box>
              <Typography variant="caption" color="text.secondary">
                {t('trading:detail.openPositions')}
              </Typography>
              <Typography variant="body1">
                {formatAppNumber(summary.counts.openPositions)}
              </Typography>
            </Box>
            <Box>
              <Typography variant="caption" color="text.secondary">
                {t('trading:detail.closedPositions')}
              </Typography>
              <Typography variant="body1">
                {formatAppNumber(summary.counts.closedPositions)}
              </Typography>
            </Box>
            <Box>
              <Typography variant="caption" color="text.secondary">
                {t('trading:detail.openLongUnits')}
              </Typography>
              <Typography variant="body1">
                {formatAppNumber(summary.counts.openLongUnits ?? 0)}
              </Typography>
            </Box>
            <Box>
              <Typography variant="caption" color="text.secondary">
                {t('trading:detail.openShortUnits')}
              </Typography>
              <Typography variant="body1">
                {formatAppNumber(summary.counts.openShortUnits ?? 0)}
              </Typography>
            </Box>
            {summary.execution.ticksProcessed > 0 && (
              <Box>
                <Typography variant="caption" color="text.secondary">
                  {t('trading:detail.ticksProcessed')}
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
            {summary.execution.resumeCursorTimestamp && (
              <Box>
                <Typography variant="caption" color="text.secondary">
                  Resume Cursor
                </Typography>
                <Typography variant="body1">
                  {new Date(
                    summary.execution.resumeCursorTimestamp
                  ).toLocaleString()}
                </Typography>
              </Box>
            )}
            {summary.execution.reconciledAt && (
              <Box>
                <Typography variant="caption" color="text.secondary">
                  Broker Reconciled
                </Typography>
                <Typography variant="body1">
                  {new Date(summary.execution.reconciledAt).toLocaleString()}
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
            taskType={TaskType.TRADING}
            instrument={task.instrument}
          />
        </Grid>
      </Grid>
    </Box>
  );
}
