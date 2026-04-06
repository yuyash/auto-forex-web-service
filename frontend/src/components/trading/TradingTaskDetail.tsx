/**
 * TradingTaskDetail Component
 *
 * Main detail view for trading tasks using task-based API endpoints.
 * Mirrors BacktestTaskDetail's structure for consistency.
 */

import React, { useState, useEffect, useMemo } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  Box,
  Button,
  Container,
  Paper,
  Typography,
  Breadcrumbs,
  Link,
  CircularProgress,
  Alert,
  useMediaQuery,
  useTheme,
} from '@mui/material';
import { useTradingTask } from '../../hooks/useTradingTasks';
import {
  shouldEnableRealtimeTaskUpdates,
  shouldPollTaskStatus,
} from '../../hooks/taskResourceQueries';
import {
  useStrategies,
  getStrategyDisplayName,
} from '../../hooks/useStrategies';
import { useAuth } from '../../contexts/AuthContext';
import { TaskLogsTable } from '../tasks/detail/TaskLogsTable';
import { TaskPositionsTable } from '../tasks/detail/TaskPositionsTable';
import { TaskTradesTable } from '../tasks/detail/TaskTradesTable';
import { TaskOrdersTable } from '../tasks/detail/TaskOrdersTable';
import { useTaskSummary } from '../../hooks/useTaskSummary';
import { TaskStatus, TaskType } from '../../types/common';
import type { TradingTask } from '../../types';
import { DeleteTaskDialog } from '../tasks/actions/DeleteTaskDialog';
import { TaskActionConfirmDialog } from '../tasks/actions/TaskActionConfirmDialog';
import { useTaskActionDialog } from '../../hooks/useTaskActionDialog';
import {
  useDeleteTradingTask,
  usePauseTradingTask,
  useRestartTradingTask,
  useResumeTradingTask,
  useStartTradingTask,
  useStopTradingTask,
} from '../../hooks/useTradingTaskMutations';
import { LazyTabPanel } from '../common/LazyTabPanel';
import { TabConfigDialog } from '../common/TabConfigDialog';
import { useTabConfig, type TabItem } from '../../hooks/useTabConfig';
import { useOptimisticTaskStatus } from '../../hooks/useOptimisticTaskStatus';
import { TaskDetailHeader } from '../tasks/detail/TaskDetailHeader';
import { TaskDetailTabs } from '../tasks/detail/TaskDetailTabs';
import { TaskStrategyTab } from '../tasks/detail/strategy/TaskStrategyTab';
import { TaskMetricsTab } from '../tasks/detail/TaskMetricsTab';
import { TradingOverviewTab } from './detail/TradingOverviewTab';
import { useTaskMetrics } from '../../hooks/useTaskMetrics';
import { computeAutoInterval } from '../../utils/autoGranularity';

export const TradingTaskDetail: React.FC = () => {
  const { t } = useTranslation(['trading', 'common']);
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const taskId = id || '';
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [tabConfigOpen, setTabConfigOpen] = useState(false);
  const { pendingAction, requestConfirm, cancelAction } = useTaskActionDialog();
  const deleteTask = useDeleteTradingTask();
  const startTask = useStartTradingTask();
  const stopTask = useStopTradingTask();
  const restartTask = useRestartTradingTask();
  const resumeTask = useResumeTradingTask();
  const pauseTask = usePauseTradingTask();
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
  const { user } = useAuth();
  const timezone = user?.timezone || 'UTC';

  const defaultTabs: TabItem[] = [
    { id: 'overview', label: t('trading:tabs.overview'), visible: true },
    { id: 'strategy', label: t('trading:tabs.strategy'), visible: true },
    { id: 'positions', label: t('trading:tabs.positions'), visible: true },
    { id: 'trades', label: t('trading:tabs.trades'), visible: true },
    { id: 'orders', label: t('trading:tabs.orders'), visible: true },
    { id: 'logs', label: t('trading:tabs.logs'), visible: true },
    { id: 'metrics', label: t('trading:tabs.metrics'), visible: true },
  ];
  const {
    tabs: allTabs,
    visibleTabs,
    updateTabs,
    resetToDefaults,
  } = useTabConfig('trading_detail', defaultTabs);
  const tabParam = searchParams.get('tab') || 'overview';
  const visibleTabIds = visibleTabs.map((tab) => tab.id);

  const {
    optimisticStatus,
    statusPollingIntervalMs,
    applyOptimisticStatus,
    clearOptimisticStatus,
  } = useOptimisticTaskStatus();
  const {
    data: task,
    isLoading,
    error,
    refresh: refreshTask,
  } = useTradingTask(taskId, {
    enablePolling: true,
    pollingInterval: statusPollingIntervalMs,
  });
  const { strategies } = useStrategies();
  const actualStatus = task?.status;
  const currentStatus = optimisticStatus?.status ?? actualStatus;

  useEffect(() => {
    if (!optimisticStatus || !actualStatus) {
      return;
    }

    if (optimisticStatus.settleOn.includes(actualStatus)) {
      clearOptimisticStatus();
    }
  }, [actualStatus, clearOptimisticStatus, optimisticStatus]);

  const selectedExecutionId = searchParams.get('execution');
  const effectiveExecutionId = selectedExecutionId || task?.execution_id;
  const isViewingHistorical =
    selectedExecutionId != null &&
    task?.execution_id != null &&
    selectedExecutionId !== task.execution_id;

  const overviewSummary = useTaskSummary(
    taskId,
    TaskType.TRADING,
    effectiveExecutionId,
    {
      polling: !isViewingHistorical && shouldPollTaskStatus(currentStatus),
      interval: statusPollingIntervalMs,
    }
  );
  const { summary: s } = overviewSummary;

  const [metricsInterval, setMetricsInterval] = useState(0);
  const [metricsSince, setMetricsSince] = useState('');
  const [metricsUntil, setMetricsUntil] = useState('');

  const effectiveMetricsInterval = useMemo(() => {
    if (metricsInterval !== 0) return metricsInterval;
    // Auto: compute from since/until or task started_at to now
    const start = metricsSince
      ? new Date(metricsSince).getTime() / 1000
      : task?.started_at
        ? new Date(task.started_at).getTime() / 1000
        : task?.created_at
          ? new Date(task.created_at).getTime() / 1000
          : 0;
    const end = metricsUntil
      ? new Date(metricsUntil).getTime() / 1000
      : task?.completed_at
        ? new Date(task.completed_at).getTime() / 1000
        : task?.started_at
          ? new Date(task.started_at).getTime() / 1000
          : 0;
    if (start && end > start) {
      return computeAutoInterval(end - start);
    }
    return 1;
  }, [metricsInterval, metricsSince, metricsUntil, task]);

  const metricsResult = useTaskMetrics({
    taskId,
    taskType: TaskType.TRADING,
    executionRunId: effectiveExecutionId,
    interval: effectiveMetricsInterval,
    since: metricsSince ? new Date(metricsSince).toISOString() : undefined,
    until: metricsUntil ? new Date(metricsUntil).toISOString() : undefined,
    enabled: !!taskId,
    pollingInterval:
      !isViewingHistorical && shouldPollTaskStatus(currentStatus) ? 30000 : 0,
  });

  const polledTick = s.tick.timestamp
    ? {
        timestamp: s.tick.timestamp,
        price: s.tick.mid != null ? String(s.tick.mid) : null,
      }
    : null;

  const activeTabIndex = Math.max(0, visibleTabIds.indexOf(tabParam));
  const handleTabChange = (_event: React.SyntheticEvent, newValue: number) => {
    const next: Record<string, string> = {
      tab: visibleTabIds[newValue] || 'overview',
    };
    const exec = searchParams.get('execution');
    if (exec) next.execution = exec;
    setSearchParams(next);
  };
  const handleBack = () => navigate('/trading-tasks');

  if (isLoading) {
    return (
      <Container maxWidth={false} sx={{ py: 4 }}>
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            minHeight: '400px',
          }}
        >
          <CircularProgress />
        </Box>
      </Container>
    );
  }
  if (error || !task) {
    return (
      <Container maxWidth={false} sx={{ py: 4 }}>
        <Alert severity="error">
          {error?.message || t('common:errors.taskNotFound')}
        </Alert>
      </Container>
    );
  }
  const detailTask = task as TradingTask;
  const activeExecutionId = effectiveExecutionId;
  const enableRealtime =
    !isViewingHistorical && shouldEnableRealtimeTaskUpdates(currentStatus);
  const pnlCurrency = detailTask.instrument?.includes('_')
    ? detailTask.instrument.split('_')[1]
    : 'N/A';

  return (
    <Container
      maxWidth={false}
      sx={{
        py: { xs: 2, sm: 4 },
        px: { xs: 1, sm: 3 },
        display: 'flex',
        flexDirection: 'column',
        flex: 1,
        minHeight: 0,
        overflow: 'auto',
      }}
    >
      <Breadcrumbs sx={{ mb: { xs: 1, sm: 2 } }}>
        <Link
          component="button"
          variant="body1"
          onClick={handleBack}
          sx={{ cursor: 'pointer', textDecoration: 'none' }}
        >
          {t('trading:pages.title')}
        </Link>
        <Typography
          color="text.primary"
          noWrap
          sx={{ maxWidth: { xs: 160, sm: 'none' } }}
        >
          {task.name}
        </Typography>
      </Breadcrumbs>

      {isViewingHistorical && (
        <Alert
          severity="info"
          sx={{ mb: 2 }}
          action={
            <Button
              color="inherit"
              size="small"
              onClick={() => {
                const tab = searchParams.get('tab') || 'overview';
                setSearchParams({ tab });
              }}
            >
              {t('common:actions.backToCurrent')}
            </Button>
          }
        >
          {t('trading:detail.viewingHistoricalExecution')}
        </Alert>
      )}

      <TaskDetailHeader
        taskId={taskId}
        taskName={detailTask.name}
        taskDescription={detailTask.description}
        taskStatus={detailTask.status}
        currentStatus={currentStatus}
        strategyName={getStrategyDisplayName(
          strategies,
          detailTask.strategy_type
        )}
        instrument={detailTask.instrument}
        pipSize={detailTask.pip_size}
        tick={s.tick}
        timezone={timezone}
        isMobile={isMobile}
        progress={s.task.progress}
        currentAtr={s.execution.currentAtr}
        completedLabel={t('trading:detail.completed')}
        editLabel={t('common:actions.edit')}
        deleteLabel={t('common:actions.delete')}
        onStart={async (id) => {
          requestConfirm('start', id);
        }}
        onStop={async (id) => {
          await stopTask.mutate({ id });
          applyOptimisticStatus(TaskStatus.STOPPING, [
            TaskStatus.STOPPING,
            TaskStatus.STOPPED,
            TaskStatus.COMPLETED,
            TaskStatus.FAILED,
          ]);
          await refreshTask();
        }}
        onRestart={async (id) => {
          requestConfirm('restart', id);
        }}
        onResume={async (id) => {
          requestConfirm('resume', id);
        }}
        onPause={async (id) => {
          requestConfirm('pause', id);
        }}
        onEdit={() => navigate(`/trading-tasks/${taskId}/edit`)}
        onDelete={() => setDeleteDialogOpen(true)}
      />

      <Paper
        sx={{
          mb: 1,
          display: 'flex',
          flexDirection: 'column',
          flex: 1,
          minHeight: 0,
          overflow: 'hidden',
        }}
      >
        <TaskDetailTabs
          activeTabIndex={activeTabIndex}
          visibleTabs={visibleTabs}
          onTabChange={handleTabChange}
          onConfigureTabs={() => setTabConfigOpen(true)}
          configureTabsLabel={t('common:tabConfig.configureTabs')}
        />

        {visibleTabIds.includes('overview') && (
          <LazyTabPanel
            value={activeTabIndex}
            index={visibleTabIds.indexOf('overview')}
          >
            <TradingOverviewTab
              taskId={taskId}
              task={detailTask}
              summary={s}
              currentStatus={currentStatus}
              strategies={strategies}
              pnlCurrency={pnlCurrency}
              latestMetrics={metricsResult.latest}
              onOpenConfiguration={() =>
                navigate(`/configurations/${detailTask.config_id}`)
              }
            />
          </LazyTabPanel>
        )}

        {visibleTabIds.includes('strategy') && (
          <LazyTabPanel
            value={activeTabIndex}
            index={visibleTabIds.indexOf('strategy')}
          >
            <TaskStrategyTab
              taskId={taskId}
              taskType={TaskType.TRADING}
              instrument={detailTask.instrument}
              executionRunId={activeExecutionId}
              enableRealTimeUpdates={enableRealtime}
            />
          </LazyTabPanel>
        )}

        {visibleTabIds.includes('positions') && (
          <LazyTabPanel
            value={activeTabIndex}
            index={visibleTabIds.indexOf('positions')}
          >
            <TaskPositionsTable
              taskId={taskId}
              taskType={TaskType.TRADING}
              executionRunId={activeExecutionId}
              enableRealTimeUpdates={enableRealtime}
              currentPrice={
                polledTick?.price != null ? parseFloat(polledTick.price) : null
              }
              pipSize={
                detailTask.pip_size ? parseFloat(detailTask.pip_size) : null
              }
            />
          </LazyTabPanel>
        )}
        {visibleTabIds.includes('trades') && (
          <LazyTabPanel
            value={activeTabIndex}
            index={visibleTabIds.indexOf('trades')}
          >
            <TaskTradesTable
              taskId={taskId}
              taskType={TaskType.TRADING}
              executionRunId={activeExecutionId}
              enableRealTimeUpdates={enableRealtime}
              pipSize={
                detailTask.pip_size ? parseFloat(detailTask.pip_size) : null
              }
            />
          </LazyTabPanel>
        )}
        {visibleTabIds.includes('orders') && (
          <LazyTabPanel
            value={activeTabIndex}
            index={visibleTabIds.indexOf('orders')}
          >
            <TaskOrdersTable
              taskId={taskId}
              taskType={TaskType.TRADING}
              executionRunId={activeExecutionId}
              enableRealTimeUpdates={enableRealtime}
            />
          </LazyTabPanel>
        )}
        {visibleTabIds.includes('logs') && (
          <LazyTabPanel
            value={activeTabIndex}
            index={visibleTabIds.indexOf('logs')}
          >
            <TaskLogsTable
              taskId={taskId}
              taskType={TaskType.TRADING}
              executionRunId={activeExecutionId}
              enableRealTimeUpdates={enableRealtime}
            />
          </LazyTabPanel>
        )}

        {/* Metrics Tab */}
        {visibleTabIds.includes('metrics') && (
          <LazyTabPanel
            value={activeTabIndex}
            index={visibleTabIds.indexOf('metrics')}
          >
            <TaskMetricsTab
              data={metricsResult.data}
              isLoading={metricsResult.isLoading}
              error={metricsResult.error}
              currency={s.execution.accountCurrency || 'USD'}
              interval={metricsInterval}
              since={metricsSince}
              until={metricsUntil}
              onIntervalChange={setMetricsInterval}
              onSinceChange={setMetricsSince}
              onUntilChange={setMetricsUntil}
              onRefresh={metricsResult.refresh}
              instrument={detailTask.instrument}
              startTime={detailTask.started_at}
              endTime={detailTask.completed_at}
            />
          </LazyTabPanel>
        )}
      </Paper>
      <TabConfigDialog
        open={tabConfigOpen}
        tabs={allTabs}
        onClose={() => setTabConfigOpen(false)}
        onSave={updateTabs}
        onReset={resetToDefaults}
      />
      <DeleteTaskDialog
        open={deleteDialogOpen}
        taskName={task.name}
        taskStatus={task.status}
        onCancel={() => setDeleteDialogOpen(false)}
        onConfirm={async () => {
          try {
            await deleteTask.mutate(taskId);
            setDeleteDialogOpen(false);
            navigate('/trading-tasks', { state: { deleted: true } });
          } catch {
            /* handled */
          }
        }}
        isLoading={deleteTask.isLoading}
        hasExecutionHistory={true}
      />
      {pendingAction && (
        <TaskActionConfirmDialog
          open={true}
          action={pendingAction.type}
          taskName={task.name}
          onCancel={cancelAction}
          isLoading={
            startTask.isLoading ||
            pauseTask.isLoading ||
            resumeTask.isLoading ||
            restartTask.isLoading
          }
          onConfirm={async () => {
            const { type, taskId: actionTaskId } = pendingAction;
            try {
              if (type === 'start') {
                const updatedTask = await startTask.mutate(actionTaskId);
                applyOptimisticStatus(updatedTask.status, [
                  TaskStatus.STARTING,
                  TaskStatus.RUNNING,
                  TaskStatus.FAILED,
                ]);
              } else if (type === 'pause') {
                const updatedTask = await pauseTask.mutate(actionTaskId);
                applyOptimisticStatus(updatedTask.status, [
                  TaskStatus.PAUSED,
                  TaskStatus.RUNNING,
                  TaskStatus.FAILED,
                ]);
              } else if (type === 'resume') {
                const updatedTask = await resumeTask.mutate(actionTaskId);
                applyOptimisticStatus(updatedTask.status, [
                  TaskStatus.RUNNING,
                  TaskStatus.PAUSED,
                  TaskStatus.FAILED,
                ]);
              } else if (type === 'restart') {
                const updatedTask = await restartTask.mutate(actionTaskId);
                applyOptimisticStatus(updatedTask.status, [
                  TaskStatus.STARTING,
                  TaskStatus.RUNNING,
                  TaskStatus.FAILED,
                ]);
              }
              cancelAction();
              await refreshTask();
            } catch {
              cancelAction();
            }
          }}
        />
      )}
    </Container>
  );
};

export default TradingTaskDetail;
