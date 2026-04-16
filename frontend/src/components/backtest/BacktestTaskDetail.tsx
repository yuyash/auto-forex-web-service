/**
 * BacktestTaskDetail Component
 *
 * Main detail view for backtest tasks using task-based API endpoints.
 * Displays task info and tab navigation for Events, Logs, Trades, and Trend.
 *
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
import { useBacktestTask } from '../../hooks/useBacktestTasks';
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
import type { BacktestTask } from '../../types';
import { DeleteTaskDialog } from '../tasks/actions/DeleteTaskDialog';
import { BacktestStopDialog } from '../tasks/actions/BacktestStopDialog';
import { TaskActionConfirmDialog } from '../tasks/actions/TaskActionConfirmDialog';
import { useTaskActionDialog } from '../../hooks/useTaskActionDialog';
import {
  useDeleteBacktestTask,
  usePauseBacktestTask,
  useResumeBacktestTask,
  useRerunBacktestTask,
  useStartBacktestTask,
  useStopBacktestTask,
} from '../../hooks/useBacktestTaskMutations';
import { LazyTabPanel } from '../common/LazyTabPanel';
import { TabConfigDialog } from '../common/TabConfigDialog';
import { useTabConfig, type TabItem } from '../../hooks/useTabConfig';
import { useOptimisticTaskStatus } from '../../hooks/useOptimisticTaskStatus';
import { TaskDetailHeader } from '../tasks/detail/TaskDetailHeader';
import { TaskDetailTabs } from '../tasks/detail/TaskDetailTabs';
import { TaskStrategyTab } from '../tasks/detail/strategy/TaskStrategyTab';
import { TaskMetricsTab } from '../tasks/detail/TaskMetricsTab';
import { BacktestOverviewTab } from './detail/BacktestOverviewTab';
import { useTaskMetrics } from '../../hooks/useTaskMetrics';
import { computeAutoInterval } from '../../utils/autoGranularity';
import { useToast } from '../common';
import { formatTaskActionError } from '../../utils/taskActionError';
import { useTaskExecution } from '../../hooks/useTaskExecutions';

export const BacktestTaskDetail: React.FC = () => {
  const { t } = useTranslation(['backtest', 'common']);
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const taskId = id || '';
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [stopDialogOpen, setStopDialogOpen] = useState(false);
  const [isStopping, setIsStopping] = useState(false);
  const [tabConfigOpen, setTabConfigOpen] = useState(false);
  const { pendingAction, requestConfirm, cancelAction } = useTaskActionDialog();
  const deleteTask = useDeleteBacktestTask();
  const startTask = useStartBacktestTask();
  const restartTask = useRerunBacktestTask();
  const resumeTask = useResumeBacktestTask();
  const pauseTask = usePauseBacktestTask();
  const stopTask = useStopBacktestTask();
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
  const { showError } = useToast();
  const { user } = useAuth();
  const timezone = user?.timezone || 'UTC';
  const language = user?.language;

  // Tab configuration with localStorage persistence
  const defaultTabs: TabItem[] = [
    { id: 'overview', label: t('backtest:tabs.overview'), visible: true },
    { id: 'strategy', label: t('backtest:tabs.strategy'), visible: true },
    { id: 'positions', label: t('backtest:tabs.positions'), visible: true },
    { id: 'trades', label: t('backtest:tabs.trades'), visible: true },
    { id: 'orders', label: t('backtest:tabs.orders'), visible: true },
    { id: 'logs', label: t('backtest:tabs.logs'), visible: true },
    { id: 'metrics', label: t('backtest:tabs.metrics'), visible: true },
  ];
  const {
    tabs: allTabs,
    visibleTabs,
    updateTabs,
    resetToDefaults,
  } = useTabConfig('backtest_detail', defaultTabs);

  // Get tab from URL, default to 'overview'
  const tabParam = searchParams.get('tab') || 'overview';
  const visibleTabIds = visibleTabs.map((t) => t.id);

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
  } = useBacktestTask(taskId || undefined, {
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

  // Fetch execution detail (includes config snapshot) for historical runs
  const { data: executionDetail } = useTaskExecution(
    taskId,
    effectiveExecutionId ?? '',
    TaskType.BACKTEST
  );
  const historicalStrategyConfig = isViewingHistorical
    ? (executionDetail?.strategy_config ?? null)
    : null;

  const overviewSummary = useTaskSummary(
    taskId,
    TaskType.BACKTEST,
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
    // Auto: compute from task time range or since/until
    const start = metricsSince
      ? new Date(metricsSince).getTime() / 1000
      : task?.start_time
        ? new Date(task.start_time).getTime() / 1000
        : 0;
    const end = metricsUntil
      ? new Date(metricsUntil).getTime() / 1000
      : task?.end_time
        ? new Date(task.end_time).getTime() / 1000
        : 0;
    if (start && end && end > start) {
      return computeAutoInterval(end - start);
    }
    return 1;
  }, [metricsInterval, metricsSince, metricsUntil, task]);

  const metricsResult = useTaskMetrics({
    taskId,
    taskType: TaskType.BACKTEST,
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

  // Derive tab value from URL parameter (use this for rendering)
  const activeTabIndex = Math.max(0, visibleTabIds.indexOf(tabParam));

  const handleTabChange = (_event: React.SyntheticEvent, newValue: number) => {
    const tabName = visibleTabIds[newValue] || 'overview';
    const next: Record<string, string> = { tab: tabName };
    const exec = searchParams.get('execution');
    if (exec) next.execution = exec;
    setSearchParams(next);
  };

  const handleBack = () => {
    navigate('/backtest-tasks');
  };

  const handleStopConfirm = async () => {
    setIsStopping(true);
    try {
      await stopTask.mutate(taskId);
      applyOptimisticStatus(TaskStatus.STOPPING, [
        TaskStatus.STOPPING,
        TaskStatus.STOPPED,
        TaskStatus.COMPLETED,
        TaskStatus.FAILED,
      ]);
      await refreshTask();
      setStopDialogOpen(false);
    } finally {
      setIsStopping(false);
    }
  };

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

  const detailTask = task as BacktestTask;
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
      {/* Breadcrumbs */}
      <Breadcrumbs sx={{ mb: { xs: 1, sm: 2 } }}>
        <Link
          component="button"
          variant="body1"
          onClick={handleBack}
          sx={{ cursor: 'pointer', textDecoration: 'none' }}
        >
          {t('backtest:pages.title')}
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
          {t('backtest:detail.viewingHistoricalExecution')}
        </Alert>
      )}

      <TaskDetailHeader
        taskId={taskId}
        taskName={detailTask.name}
        taskDescription={detailTask.description}
        taskStatus={detailTask.status}
        currentStatus={
          isViewingHistorical
            ? (executionDetail?.status as TaskStatus)
            : currentStatus
        }
        taskType="backtest"
        strategyName={getStrategyDisplayName(
          strategies,
          detailTask.strategy_type
        )}
        instrument={detailTask.instrument}
        pipSize={detailTask.pip_size}
        tick={
          isViewingHistorical
            ? { timestamp: null, bid: null, ask: null, mid: null }
            : s.tick
        }
        timezone={timezone}
        isMobile={isMobile}
        progress={
          isViewingHistorical
            ? (executionDetail?.progress ?? 0)
            : s.task.progress
        }
        currentAtr={isViewingHistorical ? null : s.execution.currentAtr}
        completedLabel={t('backtest:detail.completed')}
        editLabel={t('common:actions.edit')}
        deleteLabel={t('common:actions.delete')}
        isViewingHistorical={isViewingHistorical}
        onStart={async (id) => {
          requestConfirm('start', id);
        }}
        onStop={async () => {
          setStopDialogOpen(true);
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
        onEdit={() => navigate(`/backtest-tasks/${taskId}/edit`)}
        onDelete={() => setDeleteDialogOpen(true)}
      />

      {/* Tabs */}
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

        {/* Overview Tab — always rendered when visible */}
        {visibleTabIds.includes('overview') && (
          <LazyTabPanel
            value={activeTabIndex}
            index={visibleTabIds.indexOf('overview')}
          >
            <BacktestOverviewTab
              taskId={taskId}
              task={detailTask}
              summary={s}
              currentStatus={
                isViewingHistorical
                  ? (executionDetail?.status as TaskStatus)
                  : currentStatus
              }
              strategies={strategies}
              pnlCurrency={pnlCurrency}
              latestMetrics={metricsResult.latest}
              timezone={timezone}
              language={language}
              isViewingHistorical={isViewingHistorical}
              historicalStrategyConfig={historicalStrategyConfig}
              historicalTaskConfig={
                isViewingHistorical ? executionDetail?.task_config : null
              }
              executionId={effectiveExecutionId}
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
              taskType={TaskType.BACKTEST}
              instrument={detailTask.instrument}
              executionRunId={activeExecutionId}
              enableRealTimeUpdates={enableRealtime}
              timezone={timezone}
            />
          </LazyTabPanel>
        )}

        {/* Positions Tab */}
        {visibleTabIds.includes('positions') && (
          <LazyTabPanel
            value={activeTabIndex}
            index={visibleTabIds.indexOf('positions')}
          >
            <TaskPositionsTable
              taskId={taskId}
              taskType={TaskType.BACKTEST}
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

        {/* Trades Tab */}
        {visibleTabIds.includes('trades') && (
          <LazyTabPanel
            value={activeTabIndex}
            index={visibleTabIds.indexOf('trades')}
          >
            <TaskTradesTable
              taskId={taskId}
              taskType={TaskType.BACKTEST}
              executionRunId={activeExecutionId}
              enableRealTimeUpdates={enableRealtime}
              pipSize={
                detailTask.pip_size ? parseFloat(detailTask.pip_size) : null
              }
            />
          </LazyTabPanel>
        )}

        {/* Orders Tab */}
        {visibleTabIds.includes('orders') && (
          <LazyTabPanel
            value={activeTabIndex}
            index={visibleTabIds.indexOf('orders')}
          >
            <TaskOrdersTable
              taskId={taskId}
              taskType={TaskType.BACKTEST}
              executionRunId={activeExecutionId}
              enableRealTimeUpdates={enableRealtime}
            />
          </LazyTabPanel>
        )}

        {/* Logs Tab */}
        {visibleTabIds.includes('logs') && (
          <LazyTabPanel
            value={activeTabIndex}
            index={visibleTabIds.indexOf('logs')}
          >
            <TaskLogsTable
              taskId={taskId}
              taskType={TaskType.BACKTEST}
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
              startTime={task?.start_time}
              endTime={task?.end_time}
              currentTickTimestamp={polledTick?.timestamp}
              currentTickPrice={
                polledTick?.price != null ? parseFloat(polledTick.price) : null
              }
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
            navigate('/backtest-tasks', { state: { deleted: true } });
          } catch {
            // Error handled by mutation hook
          }
        }}
        isLoading={deleteTask.isLoading}
        hasExecutionHistory={true}
      />
      <BacktestStopDialog
        open={stopDialogOpen}
        taskName={task.name}
        isLoading={isStopping}
        onCancel={() => setStopDialogOpen(false)}
        onConfirm={handleStopConfirm}
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
            } catch (error) {
              showError(formatTaskActionError(error, 'Failed to update task'));
              cancelAction();
            }
          }}
        />
      )}
    </Container>
  );
};

export default BacktestTaskDetail;
