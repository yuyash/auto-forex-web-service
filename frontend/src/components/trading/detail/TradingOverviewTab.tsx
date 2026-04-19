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
