/**
 * TradingTaskDetail Component
 *
 * Main detail view for trading tasks using task-based API endpoints.
 * Mirrors BacktestTaskDetail's structure for consistency.
 */

import React, { useState, useEffect, useRef } from 'react';
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
import { useTradingTask } from '../../hooks/useTradingTasks';
import { useTaskPolling } from '../../hooks/useTaskPolling';
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
import type { TradingTask } from '../../types';
import { DeleteTaskDialog } from '../tasks/actions/DeleteTaskDialog';
import { useDeleteTradingTask } from '../../hooks/useTradingTaskMutations';
import { invalidateTradingTasksCache } from '../../hooks/useTradingTasks';
import { LazyTabPanel } from '../common/LazyTabPanel';
import { TabConfigDialog } from '../common/TabConfigDialog';
import { useTabConfig, type TabItem } from '../../hooks/useTabConfig';
import { useOptimisticTaskStatus } from '../../hooks/useOptimisticTaskStatus';
import { TaskDetailHeader } from '../tasks/detail/TaskDetailHeader';
import { TaskDetailTabs } from '../tasks/detail/TaskDetailTabs';
import { TradingOverviewTab } from './detail/TradingOverviewTab';

export const TradingTaskDetail: React.FC = () => {
  const { t } = useTranslation(['trading', 'common']);
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const taskId = id || '';
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [tabConfigOpen, setTabConfigOpen] = useState(false);
  const deleteTask = useDeleteTradingTask();
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
  const { user } = useAuth();
  const timezone = user?.timezone || 'UTC';

  const defaultTabs: TabItem[] = [
    { id: 'overview', label: t('trading:tabs.overview'), visible: true },
    { id: 'trend', label: t('trading:tabs.trend'), visible: true },
    { id: 'positions', label: t('trading:tabs.positions'), visible: true },
    { id: 'trades', label: t('trading:tabs.trades'), visible: true },
    { id: 'orders', label: t('trading:tabs.orders'), visible: true },
    { id: 'events', label: t('trading:tabs.events'), visible: true },
    { id: 'logs', label: t('trading:tabs.logs'), visible: true },
  ];
  const {
    tabs: allTabs,
    visibleTabs,
    updateTabs,
    resetToDefaults,
  } = useTabConfig('trading_detail', defaultTabs);
  const tabParam = searchParams.get('tab') || 'overview';
  const visibleTabIds = visibleTabs.map((tab) => tab.id);

  const { data: task, isLoading, error } = useTradingTask(taskId);
  const { strategies } = useStrategies();
  const {
    optimisticStatus,
    statusPollingIntervalMs,
    applyOptimisticStatus,
    clearOptimisticStatus,
  } = useOptimisticTaskStatus();
  const {
    status: polledStatus,
    details: polledDetails,
    startPolling,
    refetch: refetchPolledTask,
  } = useTaskPolling(taskId, 'trading', {
    enabled: !!taskId,
    pollStatus: true,
    pollDetails: true,
    interval: statusPollingIntervalMs,
  });
  const liveTask = polledDetails?.task ?? task;
  const actualStatus = polledStatus?.status ?? liveTask?.status;
  const currentStatus = optimisticStatus?.status ?? actualStatus;
  const triggerPolledRefetch = () => {
    if (typeof refetchPolledTask === 'function') {
      refetchPolledTask();
    }
  };

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
    TaskType.TRADING,
    polledDetails?.task?.execution_id ?? task?.execution_id,
    {
      polling:
        currentStatus === TaskStatus.STARTING ||
        currentStatus === TaskStatus.RUNNING,
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

  // Do NOT call refetch() on status transitions to avoid 429 rate-limiting.
  const prevStatusRef = useRef<string | undefined>(undefined);
  useEffect(() => {
    if (polledStatus) {
      prevStatusRef.current = polledStatus.status;
    }
  }, [polledStatus]);
  const activeTabIndex = Math.max(0, visibleTabIds.indexOf(tabParam));
  const handleTabChange = (_event: React.SyntheticEvent, newValue: number) => {
    setSearchParams({ tab: visibleTabIds[newValue] || 'overview' });
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
  const detailTask = (liveTask ?? task) as TradingTask;
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
        completedLabel={t('trading:detail.completed')}
        editLabel={t('common:actions.edit')}
        deleteLabel={t('common:actions.delete')}
        onStart={async (id) => {
          const { tradingTasksApi } = await import(
            '../../services/api/tradingTasks'
          );
          const updatedTask = await tradingTasksApi.start(id);
          applyOptimisticStatus(updatedTask.status, [
            TaskStatus.STARTING,
            TaskStatus.RUNNING,
            TaskStatus.FAILED,
          ]);
          startPolling();
          triggerPolledRefetch();
        }}
        onStop={async (id) => {
          const { tradingTasksApi } = await import(
            '../../services/api/tradingTasks'
          );
          await tradingTasksApi.stop(id);
          applyOptimisticStatus(TaskStatus.STOPPING, [
            TaskStatus.STOPPING,
            TaskStatus.STOPPED,
            TaskStatus.COMPLETED,
            TaskStatus.FAILED,
          ]);
          startPolling();
          triggerPolledRefetch();
        }}
        onRestart={async (id) => {
          const { tradingTasksApi } = await import(
            '../../services/api/tradingTasks'
          );
          const updatedTask = await tradingTasksApi.restart(id);
          applyOptimisticStatus(updatedTask.status, [
            TaskStatus.STARTING,
            TaskStatus.RUNNING,
            TaskStatus.FAILED,
          ]);
          startPolling();
          triggerPolledRefetch();
        }}
        onResume={async (id) => {
          const { tradingTasksApi } = await import(
            '../../services/api/tradingTasks'
          );
          const updatedTask = await tradingTasksApi.resume(id);
          applyOptimisticStatus(updatedTask.status, [
            TaskStatus.RUNNING,
            TaskStatus.PAUSED,
            TaskStatus.FAILED,
          ]);
          startPolling();
          triggerPolledRefetch();
        }}
        onPause={async (id) => {
          const { tradingTasksApi } = await import(
            '../../services/api/tradingTasks'
          );
          const updatedTask = await tradingTasksApi.pause(id);
          applyOptimisticStatus(updatedTask.status, [
            TaskStatus.PAUSED,
            TaskStatus.RUNNING,
            TaskStatus.FAILED,
          ]);
          startPolling();
          triggerPolledRefetch();
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
              onOpenConfiguration={() =>
                navigate(`/configurations/${detailTask.config_id}`)
              }
            />
          </LazyTabPanel>
        )}

        {visibleTabIds.includes('trend') && (
          <LazyTabPanel
            value={activeTabIndex}
            index={visibleTabIds.indexOf('trend')}
          >
            <TaskTrendPanel
              key={`trading-trend-${activeExecutionId ?? 'none'}`}
              taskId={taskId}
              taskType={TaskType.TRADING}
              instrument={detailTask.instrument}
              executionRunId={activeExecutionId}
              latestExecution={detailTask.latest_execution}
              currentTick={polledTick ?? null}
              enableRealTimeUpdates={
                currentStatus === TaskStatus.STARTING ||
                currentStatus === TaskStatus.RUNNING
              }
              pipSize={
                detailTask.pip_size ? parseFloat(detailTask.pip_size) : null
              }
              configId={detailTask.config_id}
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
              enableRealTimeUpdates={
                currentStatus === TaskStatus.STARTING ||
                currentStatus === TaskStatus.RUNNING
              }
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
              enableRealTimeUpdates={
                currentStatus === TaskStatus.STARTING ||
                currentStatus === TaskStatus.RUNNING
              }
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
              enableRealTimeUpdates={
                currentStatus === TaskStatus.STARTING ||
                currentStatus === TaskStatus.RUNNING
              }
            />
          </LazyTabPanel>
        )}
        {visibleTabIds.includes('events') && (
          <LazyTabPanel
            value={activeTabIndex}
            index={visibleTabIds.indexOf('events')}
          >
            <TaskEventsTable
              taskId={taskId}
              taskType={TaskType.TRADING}
              executionRunId={activeExecutionId}
              enableRealTimeUpdates={
                currentStatus === TaskStatus.STARTING ||
                currentStatus === TaskStatus.RUNNING
              }
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
              enableRealTimeUpdates={
                currentStatus === TaskStatus.STARTING ||
                currentStatus === TaskStatus.RUNNING
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
            invalidateTradingTasksCache();
            navigate('/trading-tasks', { state: { deleted: true } });
          } catch {
            /* handled */
          }
        }}
        isLoading={deleteTask.isLoading}
        hasExecutionHistory={true}
      />
    </Container>
  );
};

export default TradingTaskDetail;
