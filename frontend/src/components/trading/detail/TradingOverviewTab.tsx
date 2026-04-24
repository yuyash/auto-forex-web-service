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
import { Link as RouterLink } from 'react-router-dom';
import { StatusBadge } from '../../tasks/display/StatusBadge';
import { ExecutionHistoryTable } from '../../tasks/display/ExecutionHistoryTable';
import { LatestMetricsSummary } from '../../tasks/detail/LatestMetricsSummary';
import {
  TaskSettingsList,
  type TaskSettingDefinition,
} from '../../tasks/detail/TaskSettingsList';
import { formatBoolean } from '../../tasks/detail/taskSettingsFormat';
import type { TaskSummary } from '../../../hooks/useTaskSummary';
import { getStrategyDisplayName } from '../../../hooks/useStrategies';
import type { Strategy } from '../../../services/api/strategies';
import { TaskType, type TaskStatus } from '../../../types/common';
import type { TradingTask } from '../../../types';
import type { MetricPoint } from '../../../utils/fetchMetrics';
import { formatAppNumber, formatAppPercent } from '../../../utils/numberFormat';
import {
  buildParameterLabelMap,
  resolveParameterLabel,
} from '../../../utils/strategySchemaLabels';
import { isParameterVisible } from '../../../utils/strategySchemaDependsOn';
import type { ConfigProperty } from '../../../types/strategy';

interface TradingOverviewTabProps {
  taskId: string;
  task: TradingTask;
  summary: TaskSummary;
  currentStatus?: TaskStatus;
  strategies: Strategy[];
  pnlCurrency: string;
  latestMetrics?: MetricPoint | null;
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
  currentStatus,
  strategies,
  pnlCurrency,
  latestMetrics,
  isViewingHistorical = false,
  historicalStrategyConfig,
  historicalTaskConfig,
  executionId,
  onOpenConfiguration,
}: TradingOverviewTabProps) {
  const { t, i18n } = useTranslation(['trading', 'common']);
  const [showSnapshotParams, setShowSnapshotParams] = useState(false);

  // Build localized parameter label map from strategy JSON schema
  const paramLabelMap = useMemo(() => {
    const strategyType =
      historicalStrategyConfig?.strategy_type || task.strategy_type;
    return buildParameterLabelMap(strategies, strategyType, i18n.language);
  }, [strategies, historicalStrategyConfig, task.strategy_type, i18n.language]);

  // Resolve the JSON schema's `properties` map for the historical
  // strategy so we can filter snapshot parameters by `dependsOn`.
  const snapshotSchemaProperties = useMemo<
    Record<string, ConfigProperty> | undefined
  >(() => {
    const strategyType =
      historicalStrategyConfig?.strategy_type || task.strategy_type;
    const strategy = strategies.find((s) => s.id === strategyType);
    const schema = strategy?.config_schema as
      | { properties?: Record<string, ConfigProperty> }
      | undefined;
    return schema?.properties;
  }, [strategies, historicalStrategyConfig, task.strategy_type]);

  // When viewing a historical execution, prefer snapshot values
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
  const taskSettings = useMemo(
    (): Array<TaskSettingDefinition<Record<string, unknown>>> => [
      { key: 'name', label: t('common:labels.name') },
      { key: 'description', label: t('common:labels.description') },
      { key: 'config_name', label: t('common:labels.strategyConfiguration') },
      { key: 'strategy_type', label: t('common:labels.strategyType') },
      { key: 'instrument', label: t('common:labels.instrument') },
      { key: 'pip_size', label: t('common:labels.pipSize') },
      { key: 'account_name', label: t('trading:detail.account', 'Account') },
      {
        key: 'account_type',
        label: t('trading:detail.accountType', 'Account type'),
      },
      {
        key: 'sell_on_stop',
        label: t('common:labels.sellOnStop'),
        format: formatBoolean,
      },
      {
        key: 'dry_run',
        label: t('trading:form.dryRun', 'Dry run'),
        format: formatBoolean,
      },
      {
        key: 'hedging_enabled',
        label: t('common:labels.hedgingEnabled', 'Hedging enabled'),
        format: formatBoolean,
      },
      {
        key: 'api_retry_max_attempts',
        label: t('trading:form.apiRetryMaxAttempts', 'API retry attempts'),
      },
      {
        key: 'api_retry_backoff_base_seconds',
        label: t(
          'trading:form.apiRetryBackoffBaseSeconds',
          'API retry base backoff'
        ),
      },
      {
        key: 'api_retry_backoff_max_seconds',
        label: t(
          'trading:form.apiRetryBackoffMaxSeconds',
          'API retry max backoff'
        ),
      },
      {
        key: 'drain_duration_hours',
        label: t('trading:form.drainDurationHours', 'Drain duration (hours)'),
      },
      {
        key: 'market_idle_pre_close_minutes',
        label: t(
          'trading:form.marketIdlePreCloseMinutes',
          'Market pre-close idle (minutes)'
        ),
      },
      {
        key: 'market_idle_resume_delay_minutes',
        label: t(
          'trading:form.marketIdleResumeDelayMinutes',
          'Market resume delay (minutes)'
        ),
      },
      { key: 'debug_options', label: t('common:debug.title') },
    ],
    [t]
  );

  return (
    <Box sx={{ p: { xs: 1.5, sm: 3 } }}>
      <Grid container spacing={{ xs: 2, sm: 3 }}>
        <Grid size={{ xs: 12, md: 6 }}>
          <Typography variant="h6" gutterBottom>
            {t('trading:detail.taskInformation')}
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
                  ? parseFloat(String(effectivePipSize))
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
            {(() => {
              const effectiveStatus = String(
                currentStatus || task.status || ''
              ).toLowerCase();
              const terminalStatuses = [
                'stopped',
                'completed',
                'failed',
                'paused',
              ];
              if (!terminalStatuses.includes(effectiveStatus)) return null;
              const stopReason =
                summary.task.stopReason ||
                summary.task.errorMessage ||
                (effectiveStatus === 'completed'
                  ? t('trading:detail.stopReasonCompleted')
                  : effectiveStatus === 'stopped'
                    ? t('trading:detail.stopReasonNormal')
                    : effectiveStatus === 'paused'
                      ? t('trading:detail.stopReasonPaused')
                      : t('trading:detail.stopReasonFailedFallback'));
              const isError = effectiveStatus === 'failed';
              return (
                <Box>
                  <Typography variant="caption" color="text.secondary">
                    {t('trading:detail.stopReason')}
                  </Typography>
                  <Typography
                    variant="body2"
                    color={isError ? 'error.main' : 'text.primary'}
                    sx={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}
                  >
                    {stopReason}
                  </Typography>
                </Box>
              );
            })()}
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
                  {t('trading:detail.executionId')}
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
                {t('common:labels.oandaAccount')}
              </Typography>
              <Link
                component={RouterLink}
                to={`/oanda-accounts/${task.account_id}`}
                variant="body1"
                sx={{ display: 'block' }}
              >
                {task.account_name || 'N/A'}
              </Link>
            </Box>
            <Box>
              <Typography variant="caption" color="text.secondary">
                {t('common:labels.sellOnStop')}
              </Typography>
              <Typography variant="body1">
                {task.sell_on_stop
                  ? t('common:labels.yes')
                  : t('common:labels.no')}
              </Typography>
            </Box>
            <Box>
              <Typography variant="caption" color="text.secondary">
                {t('common:labels.dryRun')}
              </Typography>
              <Typography variant="body1">
                {task.dry_run ? t('common:labels.yes') : t('common:labels.no')}
              </Typography>
            </Box>
          </Box>
        </Grid>
        <Grid size={{ xs: 12 }}>
          <Divider sx={{ my: 2 }} />
          <TaskSettingsList
            title={t('common:labels.taskSettings', 'Task settings')}
            task={task as unknown as Record<string, unknown>}
            snapshot={historicalTaskConfig}
            definitions={taskSettings}
          />
        </Grid>

        <Grid size={{ xs: 12 }}>
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
            <LatestMetricsSummary
              latest={latestMetrics ?? null}
              pnlCurrency={pnlCurrency}
              summary={summary}
            />
          </Box>
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
            {Object.entries(historicalStrategyConfig.parameters || {})
              .filter(([key]) =>
                isParameterVisible(
                  key,
                  historicalStrategyConfig.parameters || {},
                  snapshotSchemaProperties
                )
              )
              .map(([key, value]) => (
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
              ))}
          </DialogContent>
        </Dialog>
      )}
    </Box>
  );
}
