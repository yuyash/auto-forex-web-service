import { useMemo, useState } from 'react';
import { Alert, Box, Divider, Grid, Link } from '@mui/material';
import { useTranslation } from 'react-i18next';
import { Link as RouterLink } from 'react-router-dom';
import { ExecutionHistoryTable } from '../../tasks/display/ExecutionHistoryTable';
import { ExecutionStatusSummary } from '../../tasks/detail/ExecutionStatusSummary';
import { HistoricalStrategyConfigDialog } from '../../tasks/detail/HistoricalStrategyConfigDialog';
import { TaskSettingsList } from '../../tasks/detail/TaskSettingsList';
import { buildTradingTaskSettingDefinitions } from '../../tasks/detail/taskSettingDefinitions';
import type { TaskSummary } from '../../../hooks/useTaskSummary';
import { getStrategyDisplayName } from '../../../hooks/useStrategies';
import type { Strategy } from '../../../services/api/strategies';
import { TaskType, type TaskStatus } from '../../../types/common';
import type { TradingTask } from '../../../types';
import type { TaskExecution } from '../../../types/execution';
import type { StrategySnapshotResponse } from '../../../types/strategyVisualization';
import type { MetricPoint } from '../../../utils/fetchMetrics';
import { useAuth } from '../../../contexts/AuthContext';
import { useDateTimeFormatter } from '../../../hooks/useDateTimeFormatter';
import { useNumberFormatter } from '../../../hooks/useNumberFormatter';

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
  onRefreshExecutionStatus?: () => void | Promise<unknown>;
  executionStatusRefreshing?: boolean;
  isViewingHistorical?: boolean;
  historicalStrategyConfig?: TaskExecution['strategy_config'];
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
  onRefreshExecutionStatus,
  executionStatusRefreshing = false,
  isViewingHistorical = false,
  historicalStrategyConfig,
  historicalTaskConfig,
  onOpenConfiguration,
}: TradingOverviewTabProps) {
  const { t } = useTranslation(['trading', 'common']);
  const { user } = useAuth();
  const { formatDateTime } = useDateTimeFormatter({
    includeSeconds: true,
    includeTimezone: true,
  });
  const { separators } = useNumberFormatter();
  const isSuperuser = Boolean(user?.is_superuser);
  const [historicalConfigOpen, setHistoricalConfigOpen] = useState(false);

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
      buildTradingTaskSettingDefinitions(t, {
        includeDebugOptions: isSuperuser,
        numberSeparators: separators,
      }).map((definition) => {
        if (definition.key === 'config_name') {
          return {
            ...definition,
            render: () => {
              const label =
                (isViewingHistorical &&
                  (historicalStrategyConfig?.current?.name ??
                    historicalStrategyConfig?.name)) ||
                task.config_name;

              if (isViewingHistorical) {
                if (!historicalStrategyConfig) {
                  return label;
                }

                return (
                  <Link
                    component="button"
                    type="button"
                    variant="body1"
                    aria-haspopup="dialog"
                    onClick={() => setHistoricalConfigOpen(true)}
                    sx={{
                      display: 'inline-block',
                      maxWidth: '100%',
                      textAlign: 'left',
                    }}
                  >
                    {label}
                  </Link>
                );
              }

              if (task.config_id) {
                return (
                  <Link
                    component={RouterLink}
                    to={`/configurations/${task.config_id}`}
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
                  (historicalStrategyConfig?.current?.strategy_type ??
                    historicalStrategyConfig?.strategy_type)) ||
                  task.strategy_type
              ),
          };
        }

        return definition;
      }),
    [
      historicalStrategyConfig,
      isSuperuser,
      isViewingHistorical,
      onOpenConfiguration,
      separators,
      strategies,
      t,
      task.config_id,
      task.config_name,
      task.strategy_type,
    ]
  );
  const recoveryBlockers = summary.execution.recoveryBlockers ?? [];
  const recoveryWarnings = summary.execution.recoveryWarnings ?? [];
  const executionStatusExtraItems = [
    ...(summary.execution.resumeCursorTimestamp
      ? [
          {
            id: 'resume_cursor',
            label: t('trading:detail.resumeCursor'),
            value: formatDateTime(summary.execution.resumeCursorTimestamp),
          },
        ]
      : []),
    ...(summary.execution.reconciledAt
      ? [
          {
            id: 'broker_reconciled',
            label: t('trading:detail.brokerReconciled'),
            value: formatDateTime(summary.execution.reconciledAt),
          },
        ]
      : []),
  ];

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
          <ExecutionStatusSummary
            taskNamespace="trading"
            summary={summary}
            latestMetrics={latestMetrics ?? null}
            pnlCurrency={pnlCurrency}
            displayedMarginRatio={displayedMarginRatio}
            snapshot={strategySnapshot ?? null}
            isSnapshotLoading={strategySnapshotLoading}
            snapshotError={strategySnapshotError}
            extraItems={executionStatusExtraItems}
            onRefresh={onRefreshExecutionStatus}
            isRefreshing={executionStatusRefreshing}
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
      <HistoricalStrategyConfigDialog
        open={historicalConfigOpen}
        onClose={() => setHistoricalConfigOpen(false)}
        config={historicalStrategyConfig}
        strategies={strategies}
      />
    </Box>
  );
}
