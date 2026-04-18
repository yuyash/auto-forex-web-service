import { useState, useMemo } from 'react';
import {
  Box,
  Chip,
  Dialog,
  DialogContent,
  DialogTitle,
  Divider,
  Grid,
  IconButton,
  Link,
  Typography,
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import { useTranslation } from 'react-i18next';
import { StatusBadge } from '../../tasks/display/StatusBadge';
import { ExecutionHistoryTable } from '../../tasks/display/ExecutionHistoryTable';
import { LatestMetricsSummary } from '../../tasks/detail/LatestMetricsSummary';
import type { TaskSummary } from '../../../hooks/useTaskSummary';
import { getStrategyDisplayName } from '../../../hooks/useStrategies';
import type { Strategy } from '../../../services/api/strategies';
import { TaskType, type TaskStatus } from '../../../types/common';
import type { BacktestTask } from '../../../types';
import type { MetricPoint } from '../../../utils/fetchMetrics';
import { formatAppNumber, formatAppPercent } from '../../../utils/numberFormat';
import { formatDateTimeInTimezone } from '../../../utils/timezone';
import {
  buildParameterLabelMap,
  resolveParameterLabel,
} from '../../../utils/strategySchemaLabels';

interface BacktestOverviewTabProps {
  taskId: string;
  task: BacktestTask;
  summary: TaskSummary;
  currentStatus?: TaskStatus;
  strategies: Strategy[];
  pnlCurrency: string;
  latestMetrics?: MetricPoint | null;
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
  currentStatus,
  strategies,
  pnlCurrency,
  latestMetrics,
  timezone,
  language,
  isViewingHistorical = false,
  historicalStrategyConfig,
  historicalTaskConfig,
  executionId,
  onOpenConfiguration,
}: BacktestOverviewTabProps) {
  const { t, i18n } = useTranslation(['backtest', 'common']);
  const [showSnapshotParams, setShowSnapshotParams] = useState(false);

  // Build localized parameter label map from strategy JSON schema
  const paramLabelMap = useMemo(() => {
    const strategyType =
      historicalStrategyConfig?.strategy_type || task.strategy_type;
    return buildParameterLabelMap(strategies, strategyType, i18n.language);
  }, [strategies, historicalStrategyConfig, task.strategy_type, i18n.language]);

  // When viewing a historical execution, prefer snapshot values for task settings
  const effectiveStartTime =
    (isViewingHistorical && historicalTaskConfig?.start_time) ||
    task.start_time;
  const effectiveEndTime =
    (isViewingHistorical && historicalTaskConfig?.end_time) || task.end_time;
  const effectiveInitialBalance =
    (isViewingHistorical && historicalTaskConfig?.initial_balance) ||
    task.initial_balance;
  const effectiveCommission =
    (isViewingHistorical && historicalTaskConfig?.commission_per_trade) ||
    task.commission_per_trade;
  const effectiveInstrument =
    (isViewingHistorical && historicalTaskConfig?.instrument) ||
    task.instrument;
  const effectivePipSize =
    (isViewingHistorical && historicalTaskConfig?.pip_size) || task.pip_size;
  const latestMarginRatioRaw = latestMetrics?.metrics.margin_ratio;
  const latestMarginRatio =
    latestMarginRatioRaw != null && latestMarginRatioRaw !== ''
      ? Number(latestMarginRatioRaw)
      : null;
  const displayedMarginRatio = Number.isFinite(latestMarginRatio)
    ? latestMarginRatio
    : summary.execution.marginRatio;

  const tracemallocEnabled = Boolean(task.debug_options?.tracemalloc);

  return (
    <Box sx={{ p: { xs: 1.5, sm: 3 } }}>
      <Grid container spacing={{ xs: 2, sm: 3 }}>
        <Grid size={{ xs: 12, md: 6 }}>
          <Typography variant="h6" gutterBottom>
            {t('backtest:detail.taskInformation')}
          </Typography>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            <Box>
              <Typography variant="caption" color="text.secondary">
                {t('common:labels.name')}
              </Typography>
              <Typography variant="body1">{task.name}</Typography>
            </Box>

            {task.description && (
              <Box>
                <Typography variant="caption" color="text.secondary">
                  {t('common:labels.description')}
                </Typography>
                <Typography variant="body1">{task.description}</Typography>
              </Box>
            )}

            <Box>
              <Typography variant="caption" color="text.secondary">
                {t('common:labels.instrument')}
              </Typography>
              <Typography variant="body1">{effectiveInstrument}</Typography>
            </Box>

            <Box>
              <Typography variant="caption" color="text.secondary">
                {t('common:labels.pipSize')}
              </Typography>
              <Typography variant="body1">
                {effectivePipSize
                  ? parseFloat(effectivePipSize)
                  : effectivePipSize}
              </Typography>
            </Box>

            <Box>
              <Typography variant="caption" color="text.secondary">
                {t('common:labels.status')}
              </Typography>
              <Box sx={{ mt: 0.5 }}>
                <StatusBadge
                  status={currentStatus || task.status}
                  showIcon={false}
                />
              </Box>
            </Box>
            <Box>
              <Typography variant="caption" color="text.secondary">
                {t('common:labels.taskId')}
              </Typography>
              <Typography
                variant="body2"
                sx={{ fontFamily: 'monospace', wordBreak: 'break-all' }}
              >
                {taskId}
              </Typography>
            </Box>
            {(executionId || task.execution_id) && (
              <Box>
                <Typography variant="caption" color="text.secondary">
                  {t('backtest:detail.executionId')}
                </Typography>
                <Typography
                  variant="body2"
                  sx={{ fontFamily: 'monospace', wordBreak: 'break-all' }}
                >
                  {executionId || task.execution_id}
                </Typography>
              </Box>
            )}
            {tracemallocEnabled && (
              <Box>
                <Typography variant="caption" color="text.secondary">
                  {t('common:debug.title')}
                </Typography>
                <Box sx={{ mt: 0.5 }}>
                  <Chip
                    size="small"
                    label={t('common:debug.tracemalloc')}
                    color="warning"
                    variant="filled"
                  />
                </Box>
              </Box>
            )}
          </Box>
        </Grid>

        <Grid size={{ xs: 12, md: 6 }}>
          <Typography variant="h6" gutterBottom>
            {t('common:labels.configuration')}
          </Typography>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            <Box>
              <Typography variant="caption" color="text.secondary">
                {t('common:labels.strategyConfiguration')}
                {isViewingHistorical && historicalStrategyConfig && (
                  <Chip
                    size="small"
                    label={t('common:labels.snapshot')}
                    color="info"
                    variant="outlined"
                    sx={{ ml: 1, height: 18, fontSize: '0.65rem' }}
                  />
                )}
              </Typography>
              {isViewingHistorical && historicalStrategyConfig ? (
                <Link
                  component="button"
                  variant="body1"
                  onClick={() => setShowSnapshotParams(true)}
                  sx={{ textAlign: 'left', display: 'block' }}
                >
                  {historicalStrategyConfig.name}
                </Link>
              ) : (
                <Link
                  component="button"
                  variant="body1"
                  onClick={onOpenConfiguration}
                  sx={{ textAlign: 'left', display: 'block' }}
                >
                  {task.config_name}
                </Link>
              )}
            </Box>

            <Box>
              <Typography variant="caption" color="text.secondary">
                {t('common:labels.strategyType')}
              </Typography>
              <Typography variant="body1" sx={{ textTransform: 'capitalize' }}>
                {isViewingHistorical && historicalStrategyConfig
                  ? getStrategyDisplayName(
                      strategies,
                      historicalStrategyConfig.strategy_type
                    )
                  : getStrategyDisplayName(strategies, task.strategy_type)}
              </Typography>
            </Box>

            <Box>
              <Typography variant="caption" color="text.secondary">
                {t('backtest:detail.dataSource')}
              </Typography>
              <Typography variant="body1" sx={{ textTransform: 'capitalize' }}>
                {task.data_source}
              </Typography>
            </Box>

            <Box>
              <Typography variant="caption" color="text.secondary">
                {t('backtest:detail.initialBalance')}
              </Typography>
              <Typography variant="body1">
                $
                {formatAppNumber(parseFloat(String(effectiveInitialBalance)), {
                  minimumFractionDigits: 2,
                  maximumFractionDigits: 2,
                })}
              </Typography>
            </Box>

            <Box>
              <Typography variant="caption" color="text.secondary">
                {t('backtest:detail.commissionPerTrade')}
              </Typography>
              <Typography variant="body1">
                $
                {formatAppNumber(parseFloat(String(effectiveCommission)), {
                  minimumFractionDigits: 2,
                  maximumFractionDigits: 2,
                })}
              </Typography>
            </Box>
          </Box>
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
            />
          </Box>
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

      {/* Snapshot parameters dialog */}
      {historicalStrategyConfig && (
        <Dialog
          open={showSnapshotParams}
          onClose={() => setShowSnapshotParams(false)}
          maxWidth="sm"
          fullWidth
        >
          <DialogTitle
            sx={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
            }}
          >
            {historicalStrategyConfig.name}
            <IconButton
              size="small"
              onClick={() => setShowSnapshotParams(false)}
            >
              <CloseIcon fontSize="small" />
            </IconButton>
          </DialogTitle>
          <DialogContent dividers>
            <Typography
              variant="caption"
              color="text.secondary"
              sx={{ mb: 2, display: 'block' }}
            >
              {t('common:labels.strategyType')}:{' '}
              {historicalStrategyConfig.strategy_type}
            </Typography>
            {Object.entries(historicalStrategyConfig.parameters || {}).map(
              ([key, value]) => (
                <Box
                  key={key}
                  sx={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    py: 0.5,
                    borderBottom: '1px solid',
                    borderColor: 'divider',
                  }}
                >
                  <Typography variant="body2" color="text.secondary">
                    {resolveParameterLabel(paramLabelMap, key)}
                  </Typography>
                  <Typography
                    variant="body2"
                    fontWeight={500}
                    sx={{ fontFamily: 'monospace' }}
                  >
                    {typeof value === 'boolean'
                      ? value
                        ? 'true'
                        : 'false'
                      : String(value ?? '-')}
                  </Typography>
                </Box>
              )
            )}
          </DialogContent>
        </Dialog>
      )}
    </Box>
  );
}
