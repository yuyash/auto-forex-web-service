/**
 * BacktestTaskDetail Component
 *
 * Main detail view for backtest tasks using task-based API endpoints.
 * Displays task info and tab navigation for Events, Logs, Trades, and Trend.
 *
 */

import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  Box,
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
import { TaskEventsTable } from '../tasks/detail/TaskEventsTable';
import { TaskLogsTable } from '../tasks/detail/TaskLogsTable';
import { TaskPositionsTable } from '../tasks/detail/TaskPositionsTable';
import { TaskTradesTable } from '../tasks/detail/TaskTradesTable';
import { TaskTrendPanel } from '../tasks/detail/TaskTrendPanel';
import { TaskOrdersTable } from '../tasks/detail/TaskOrdersTable';
import { useTaskSummary } from '../../hooks/useTaskSummary';
import { TaskStatus, TaskType } from '../../types/common';
import type { BacktestTask } from '../../types';
import { DeleteTaskDialog } from '../tasks/actions/DeleteTaskDialog';
import { BacktestStopDialog } from '../tasks/actions/BacktestStopDialog';
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
import { BacktestOverviewTab } from './detail/BacktestOverviewTab';

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
  const deleteTask = useDeleteBacktestTask();
  const startTask = useStartBacktestTask();
  const restartTask = useRerunBacktestTask();
  const resumeTask = useResumeBacktestTask();
  const pauseTask = usePauseBacktestTask();
  const stopTask = useStopBacktestTask();
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
  const { user } = useAuth();
  const timezone = user?.timezone || 'UTC';

  // Tab configuration with localStorage persistence
  const defaultTabs: TabItem[] = [
    { id: 'overview', label: t('backtest:tabs.overview'), visible: true },
    { id: 'strategy', label: t('backtest:tabs.strategy'), visible: true },
    { id: 'trend', label: t('backtest:tabs.trend'), visible: true },
    { id: 'positions', label: t('backtest:tabs.positions'), visible: true },
    { id: 'trades', label: t('backtest:tabs.trades'), visible: true },
    { id: 'orders', label: t('backtest:tabs.orders'), visible: true },
    { id: 'events', label: t('backtest:tabs.events'), visible: true },
    { id: 'logs', label: t('backtest:tabs.logs'), visible: true },
  ];
  const {
    tabs: allTabs,
    visibleTabs,
    updateTabs,
    resetToDefaults,
  } = useTabConfig('backtest_detail', defaultTabs);

  // Get tab from URL, default to 'overview'
  const tabParam = searchParams.get('tab') || 'overview';
  const filteredVisibleTabs = isMobile
    ? visibleTabs.filter((t) => t.id !== 'trend')
    : visibleTabs;
  const visibleTabIds = filteredVisibleTabs.map((t) => t.id);

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

  const overviewSummary = useTaskSummary(
    taskId,
    TaskType.BACKTEST,
    task?.execution_id,
    {
      polling: shouldPollTaskStatus(currentStatus),
      interval: statusPollingIntervalMs,
    }
  );

  const { summary: s } = overviewSummary;
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
    setSearchParams({ tab: tabName });
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
  const activeExecutionId = detailTask.execution_id;
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
        completedLabel={t('backtest:detail.completed')}
        editLabel={t('common:actions.edit')}
        deleteLabel={t('common:actions.delete')}
        onStart={async (id) => {
          const updatedTask = await startTask.mutate(id);
          applyOptimisticStatus(updatedTask.status, [
            TaskStatus.STARTING,
            TaskStatus.RUNNING,
            TaskStatus.FAILED,
          ]);
          await refreshTask();
        }}
        onStop={async () => {
          setStopDialogOpen(true);
        }}
        onRestart={async (id) => {
          const updatedTask = await restartTask.mutate(id);
          applyOptimisticStatus(updatedTask.status, [
            TaskStatus.STARTING,
            TaskStatus.RUNNING,
            TaskStatus.FAILED,
          ]);
          await refreshTask();
        }}
        onResume={async (id) => {
          const updatedTask = await resumeTask.mutate(id);
          applyOptimisticStatus(updatedTask.status, [
            TaskStatus.RUNNING,
            TaskStatus.PAUSED,
            TaskStatus.FAILED,
          ]);
          await refreshTask();
        }}
        onPause={async (id) => {
          const updatedTask = await pauseTask.mutate(id);
          applyOptimisticStatus(updatedTask.status, [
            TaskStatus.PAUSED,
            TaskStatus.RUNNING,
            TaskStatus.FAILED,
          ]);
          await refreshTask();
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
          visibleTabs={filteredVisibleTabs}
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
              currentStatus={currentStatus}
              strategies={strategies}
              pnlCurrency={pnlCurrency}
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
              enableRealTimeUpdates={shouldEnableRealtimeTaskUpdates(
                currentStatus
              )}
            />
          </LazyTabPanel>
        )}

        {/* Trend Tab */}
        {visibleTabIds.includes('trend') && (
          <LazyTabPanel
            value={activeTabIndex}
            index={visibleTabIds.indexOf('trend')}
          >
            <TaskTrendPanel
              key={`backtest-trend-${activeExecutionId ?? 'none'}`}
              taskId={taskId}
              taskType={TaskType.BACKTEST}
              instrument={detailTask.instrument}
              executionRunId={activeExecutionId}
              startTime={detailTask.start_time}
              endTime={detailTask.end_time}
              latestExecution={detailTask.latest_execution}
              summary={s}
              currentTick={polledTick ?? null}
              enableRealTimeUpdates={shouldEnableRealtimeTaskUpdates(
                currentStatus
              )}
              pipSize={
                detailTask.pip_size ? parseFloat(detailTask.pip_size) : null
              }
              configId={detailTask.config_id}
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
              enableRealTimeUpdates={shouldEnableRealtimeTaskUpdates(
                currentStatus
              )}
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
              enableRealTimeUpdates={shouldEnableRealtimeTaskUpdates(
                currentStatus
              )}
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
              enableRealTimeUpdates={shouldEnableRealtimeTaskUpdates(
                currentStatus
              )}
            />
          </LazyTabPanel>
        )}

        {/* Events Tab */}
        {visibleTabIds.includes('events') && (
          <LazyTabPanel
            value={activeTabIndex}
            index={visibleTabIds.indexOf('events')}
          >
            <TaskEventsTable
              taskId={taskId}
              taskType={TaskType.BACKTEST}
              executionRunId={activeExecutionId}
              enableRealTimeUpdates={shouldEnableRealtimeTaskUpdates(
                currentStatus
              )}
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
              enableRealTimeUpdates={shouldEnableRealtimeTaskUpdates(
                currentStatus
              )}
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
    </Container>
  );
};

export default BacktestTaskDetail;
