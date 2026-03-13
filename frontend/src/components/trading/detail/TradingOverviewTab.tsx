import { Box, Divider, Grid, Link, Typography } from '@mui/material';
import { useTranslation } from 'react-i18next';
import { StatusBadge } from '../../tasks/display/StatusBadge';
import { ExecutionHistoryTable } from '../../tasks/display/ExecutionHistoryTable';
import type { TaskSummary } from '../../../hooks/useTaskSummary';
import { getStrategyDisplayName } from '../../../hooks/useStrategies';
import type { Strategy } from '../../../services/api/strategies';
import { TaskType, type TaskStatus } from '../../../types/common';
import type { TradingTask } from '../../../types';

interface TradingOverviewTabProps {
  taskId: string;
  task: TradingTask;
  summary: TaskSummary;
  currentStatus?: TaskStatus;
  strategies: Strategy[];
  pnlCurrency: string;
  onOpenConfiguration: () => void;
}

export function TradingOverviewTab({
  taskId,
  task,
  summary,
  currentStatus,
  strategies,
  pnlCurrency,
  onOpenConfiguration,
}: TradingOverviewTabProps) {
  const { t } = useTranslation(['trading', 'common']);

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
              <Typography variant="body1">{task.instrument}</Typography>
            </Box>
            <Box>
              <Typography variant="caption" color="text.secondary">
                {t('common:labels.pipSize')}
              </Typography>
              <Typography variant="body1">
                {task.pip_size ? parseFloat(task.pip_size) : task.pip_size}
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
              </Typography>
              <Link
                component="button"
                variant="body1"
                onClick={onOpenConfiguration}
                sx={{ textAlign: 'left', display: 'block' }}
              >
                {task.config_name}
              </Link>
            </Box>
            <Box>
              <Typography variant="caption" color="text.secondary">
                {t('common:labels.strategyType')}
              </Typography>
              <Typography variant="body1" sx={{ textTransform: 'capitalize' }}>
                {getStrategyDisplayName(strategies, task.strategy_type)}
              </Typography>
            </Box>
            <Box>
              <Typography variant="caption" color="text.secondary">
                {t('common:labels.oandaAccount')}
              </Typography>
              <Typography variant="body1">
                {task.account_name || 'N/A'}
              </Typography>
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
                {summary.pnl.realized.toFixed(2)} {pnlCurrency}
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
                {summary.pnl.unrealized.toFixed(2)} {pnlCurrency}
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
                      {summary.execution.currentBalanceDisplay.toFixed(0)}{' '}
                      {summary.execution.displayCurrency}
                      <Typography
                        component="span"
                        variant="body2"
                        color="text.secondary"
                        sx={{ ml: 1 }}
                      >
                        ({summary.execution.currentBalance.toFixed(2)}{' '}
                        {summary.execution.accountCurrency})
                      </Typography>
                    </>
                  ) : (
                    <>
                      {summary.execution.currentBalance.toFixed(2)}{' '}
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
                {summary.counts.totalTrades}
              </Typography>
            </Box>
            <Box>
              <Typography variant="caption" color="text.secondary">
                {t('trading:detail.openPositions')}
              </Typography>
              <Typography variant="body1">
                {summary.counts.openPositions}
              </Typography>
            </Box>
            <Box>
              <Typography variant="caption" color="text.secondary">
                {t('trading:detail.closedPositions')}
              </Typography>
              <Typography variant="body1">
                {summary.counts.closedPositions}
              </Typography>
            </Box>
            {summary.execution.ticksProcessed > 0 && (
              <Box>
                <Typography variant="caption" color="text.secondary">
                  {t('trading:detail.ticksProcessed')}
                </Typography>
                <Typography variant="body1">
                  {summary.execution.ticksProcessed.toLocaleString()}
                </Typography>
              </Box>
            )}
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
    </Box>
  );
}
