import { useMemo } from 'react';
import { Alert, Box, Divider, Grid, Link } from '@mui/material';
import { useTranslation } from 'react-i18next';
import { Link as RouterLink } from 'react-router-dom';
import { ExecutionHistoryTable } from '../../tasks/display/ExecutionHistoryTable';
import { ExecutionStatusSummary } from '../../tasks/detail/ExecutionStatusSummary';
import { TaskSettingsList } from '../../tasks/detail/TaskSettingsList';
import { buildTradingTaskSettingDefinitions } from '../../tasks/detail/taskSettingDefinitions';
import type { TaskSummary } from '../../../hooks/useTaskSummary';
import { getStrategyDisplayName } from '../../../hooks/useStrategies';
import type { Strategy } from '../../../services/api/strategies';
import { TaskType, type TaskStatus } from '../../../types/common';
import type { TradingTask } from '../../../types';
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
  const { user } = useAuth();
  const { formatDateTime } = useDateTimeFormatter({
    includeSeconds: true,
    includeTimezone: true,
  });
  const { separators } = useNumberFormatter();
  const isSuperuser = Boolean(user?.is_superuser);

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
