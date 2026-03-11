/**
 * BacktestTaskDetail Component
 *
 * Main detail view for backtest tasks using task-based API endpoints.
 * Displays task info and tab navigation for Events, Logs, Trades, and Trend.
 *
 */

import React, { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  Box,
  Container,
  Paper,
  Typography,
  Tabs,
  Tab,
  Breadcrumbs,
  Link,
  CircularProgress,
  Alert,
  Grid,
  Divider,
  IconButton,
  Tooltip,
} from '@mui/material';
import {
  Edit as EditIcon,
  Delete as DeleteIcon,
  Settings as SettingsIcon,
} from '@mui/icons-material';
import { useBacktestTask } from '../../hooks/useBacktestTasks';
import { useTaskPolling } from '../../hooks/useTaskPolling';
import {
  useStrategies,
  getStrategyDisplayName,
} from '../../hooks/useStrategies';
import { TaskControlButtons } from '../common/TaskControlButtons';
import { TaskEventsTable } from '../tasks/detail/TaskEventsTable';
import { StatusBadge } from '../tasks/display/StatusBadge';
import { ExecutionHistoryTable } from '../tasks/display/ExecutionHistoryTable';
import { TaskLogsTable } from '../tasks/detail/TaskLogsTable';
import { TaskPositionsTable } from '../tasks/detail/TaskPositionsTable';
import { TaskTradesTable } from '../tasks/detail/TaskTradesTable';
import { TaskTrendPanel } from '../tasks/detail/TaskTrendPanel';
import { TaskOrdersTable } from '../tasks/detail/TaskOrdersTable';
import { useTaskSummary } from '../../hooks/useTaskSummary';
import { TaskStatus, TaskType } from '../../types/common';
import { DeleteTaskDialog } from '../tasks/actions/DeleteTaskDialog';
import { useDeleteBacktestTask } from '../../hooks/useBacktestTaskMutations';
import { invalidateBacktestTasksCache } from '../../hooks/useBacktestTasks';
import { LazyTabPanel } from '../common/LazyTabPanel';
import { TabConfigDialog } from '../common/TabConfigDialog';
import { useTabConfig, type TabItem } from '../../hooks/useTabConfig';

function a11yProps(index: number) {
  return {
    id: `task-tab-${index}`,
    'aria-controls': `task-tabpanel-${index}`,
  };
}

export const BacktestTaskDetail: React.FC = () => {
  const { t } = useTranslation(['backtest', 'common']);
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const taskId = id || '';
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [tabConfigOpen, setTabConfigOpen] = useState(false);
  const deleteTask = useDeleteBacktestTask();

  // Tab configuration with localStorage persistence
  const defaultTabs: TabItem[] = [
    { id: 'overview', label: t('backtest:tabs.overview'), visible: true },
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
  const visibleTabIds = visibleTabs.map((t) => t.id);

  const {
    data: task,
    isLoading,
    error,
    refetch,
  } = useBacktestTask(taskId || undefined);
  const { strategies } = useStrategies();

  const isTaskRunning = task?.status === TaskStatus.RUNNING;

  const overviewSummary = useTaskSummary(
    taskId,
    TaskType.BACKTEST,
    task?.execution_id,
    {
      polling: isTaskRunning,
      interval: 3000,
    }
  );

  const { summary: s } = overviewSummary;
  const polledTick = s.tick.timestamp
    ? {
        timestamp: s.tick.timestamp,
        price: s.tick.mid != null ? String(s.tick.mid) : null,
      }
    : null;

  // Use HTTP polling for task status updates
  const {
    status: polledStatus,
    startPolling,
    isPolling,
  } = useTaskPolling(taskId, 'backtest', {
    enabled: !!taskId,
    pollStatus: true,
    interval: 3000,
  });

  // Update the displayed status from the lightweight status poller.
  // We intentionally do NOT call refetch() on status transitions because
  // the burst of concurrent API calls (task detail + positions + events +
  // trades + summary + metrics) triggers 429 rate-limiting, which causes
  // useBacktestTask to set error state → the component tree unmounts
  // (including TaskTrendPanel) → on recovery the chart remounts and
  // fitContent() scrolls to the last candle.
  //
  // The polledStatus is already used for the status badge and
  // enableRealTimeUpdates, so the UI stays in sync without refetching.
  const prevStatusRef = useRef<string | undefined>(undefined);
  useEffect(() => {
    if (polledStatus) {
      prevStatusRef.current = polledStatus.status;
    }
  }, [polledStatus]);

  // Derive tab value from URL parameter (use this for rendering)
  const activeTabIndex = Math.max(0, visibleTabIds.indexOf(tabParam));

  const handleTabChange = (_event: React.SyntheticEvent, newValue: number) => {
    const tabName = visibleTabIds[newValue] || 'overview';
    setSearchParams({ tab: tabName });
  };

  const handleBack = () => {
    navigate('/backtest-tasks');
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

  const pnlCurrency = task.instrument?.includes('_')
    ? task.instrument.split('_')[1]
    : 'N/A';

  return (
    <Container
      maxWidth={false}
      sx={{
        py: 4,
        display: 'flex',
        flexDirection: 'column',
        flex: 1,
        minHeight: 0,
        overflow: 'auto',
      }}
    >
      {/* Breadcrumbs */}
      <Breadcrumbs sx={{ mb: 2 }}>
        <Link
          component="button"
          variant="body1"
          onClick={handleBack}
          sx={{ cursor: 'pointer', textDecoration: 'none' }}
        >
          {t('backtest:pages.title')}
        </Link>
        <Typography color="text.primary">{task.name}</Typography>
      </Breadcrumbs>

      {/* Header */}
      <Paper sx={{ p: 2, pb: 1, mb: 2 }}>
        <Box
          sx={{
            display: 'flex',
            alignItems: 'flex-start',
            gap: 2,
            flexWrap: 'wrap',
          }}
        >
          <Box sx={{ flex: 1, minWidth: 0 }}>
            <Box
              sx={{
                display: 'flex',
                alignItems: 'center',
                gap: 1,
                p: '4px',
                mb: '4px',
                flexWrap: 'wrap',
              }}
            >
              <Typography
                variant="h4"
                component="h1"
                sx={{
                  fontSize: { xs: '1.5rem', sm: '2.125rem' },
                  wordBreak: 'break-word',
                }}
              >
                {task.name}
              </Typography>
              <StatusBadge status={polledStatus?.status || task.status} />
            </Box>

            <Typography
              variant="body2"
              color="text.secondary"
              sx={{ pl: '4px' }}
            >
              {getStrategyDisplayName(strategies, task.strategy_type)}
            </Typography>

            {task.description && (
              <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                {task.description}
              </Typography>
            )}

            {/* Current Price */}
            {s.tick.mid != null && (
              <Box
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 1,
                  mt: 1,
                  pl: '4px',
                }}
              >
                <Typography
                  variant="body2"
                  color="text.secondary"
                  component="span"
                >
                  {task.instrument}:
                </Typography>
                <Typography
                  variant="body2"
                  component="span"
                  sx={{ fontWeight: 600, fontFamily: 'monospace' }}
                >
                  {s.tick.mid.toFixed(
                    task.pip_size
                      ? String(task.pip_size).split('.')[1]?.length || 5
                      : 5
                  )}
                </Typography>
                {s.tick.bid != null && s.tick.ask != null && (
                  <Typography
                    variant="caption"
                    color="text.secondary"
                    component="span"
                    sx={{ fontFamily: 'monospace' }}
                  >
                    (B: {s.tick.bid.toFixed(5)} / A: {s.tick.ask.toFixed(5)})
                  </Typography>
                )}
              </Box>
            )}

            {/* Progress Percentage */}
            {(polledStatus?.status || task.status) === TaskStatus.RUNNING && (
              <Typography
                variant="body2"
                color="text.secondary"
                sx={{ mt: 2, fontWeight: 600 }}
              >
                {Math.round(Math.min(Math.max(s.task.progress, 0), 100))}%{' '}
                {t('backtest:detail.completed')}
              </Typography>
            )}
          </Box>

          <Box sx={{ display: 'flex', gap: 1 }}>
            <TaskControlButtons
              taskId={taskId}
              status={polledStatus?.status || task.status}
              onStart={async (id) => {
                const { backtestTasksApi } = await import(
                  '../../services/api/backtestTasks'
                );
                await backtestTasksApi.start(id);
                refetch();
                if (!isPolling) startPolling();
              }}
              onStop={async (id) => {
                const { backtestTasksApi } = await import(
                  '../../services/api/backtestTasks'
                );
                await backtestTasksApi.stop(id);
                // Do NOT call refetch() here — the status poller will detect
                // the STOPPING→STOPPED transition and trigger refetch
                // automatically.  Calling refetch() immediately floods the
                // backend with concurrent requests (task detail + positions +
                // events + trades + summary + metrics) which triggers 429
                // rate-limiting.  The 429 errors cause useBacktestTask to set
                // error state, which unmounts the entire component tree
                // (including TaskTrendPanel), destroying the chart.  When the
                // next successful response arrives the tree remounts and
                // fitContent() scrolls the chart to the last candle.
              }}
              onRestart={async (id) => {
                const { backtestTasksApi } = await import(
                  '../../services/api/backtestTasks'
                );
                await backtestTasksApi.restart(id);
                refetch();
                if (!isPolling) {
                  startPolling();
                }
              }}
              onResume={async (id) => {
                const { backtestTasksApi } = await import(
                  '../../services/api/backtestTasks'
                );
                await backtestTasksApi.resume(id);
                refetch();
                if (!isPolling) {
                  startPolling();
                }
              }}
              onPause={async (id) => {
                const { backtestTasksApi } = await import(
                  '../../services/api/backtestTasks'
                );
                await backtestTasksApi.pause(id);
                refetch();
              }}
            />
            <Box sx={{ display: 'flex' }}>
              <Tooltip title={t('common:actions.edit')}>
                <span>
                  <IconButton
                    onClick={() => navigate(`/backtest-tasks/${taskId}/edit`)}
                    disabled={
                      (polledStatus?.status || task.status) ===
                        TaskStatus.RUNNING ||
                      (polledStatus?.status || task.status) ===
                        TaskStatus.PAUSED
                    }
                    aria-label={t('common:actions.edit')}
                  >
                    <EditIcon />
                  </IconButton>
                </span>
              </Tooltip>
              <Tooltip title={t('common:actions.delete')}>
                <span>
                  <IconButton
                    onClick={() => setDeleteDialogOpen(true)}
                    disabled={
                      (polledStatus?.status || task.status) ===
                        TaskStatus.RUNNING ||
                      (polledStatus?.status || task.status) ===
                        TaskStatus.PAUSED
                    }
                    color="error"
                    aria-label={t('common:actions.delete')}
                  >
                    <DeleteIcon />
                  </IconButton>
                </span>
              </Tooltip>
            </Box>
          </Box>
        </Box>
      </Paper>

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
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            borderBottom: 1,
            borderColor: 'divider',
            flexShrink: 0,
          }}
        >
          <Tabs
            value={activeTabIndex}
            onChange={handleTabChange}
            aria-label="task detail tabs"
            variant="scrollable"
            scrollButtons="auto"
            allowScrollButtonsMobile
            sx={{ flex: 1 }}
          >
            {visibleTabs.map((tab, idx) => (
              <Tab key={tab.id} label={tab.label} {...a11yProps(idx)} />
            ))}
          </Tabs>
          <Tooltip title={t('common:tabConfig.configureTabs')}>
            <IconButton
              onClick={() => setTabConfigOpen(true)}
              size="small"
              sx={{ mr: 1 }}
              aria-label={t('common:tabConfig.configureTabs')}
            >
              <SettingsIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </Box>

        {/* Overview Tab — always rendered when visible */}
        {visibleTabIds.includes('overview') && (
          <LazyTabPanel
            value={activeTabIndex}
            index={visibleTabIds.indexOf('overview')}
          >
            <Box sx={{ p: 3 }}>
              <Grid container spacing={3}>
                <Grid size={{ xs: 12, md: 6 }}>
                  <Typography variant="h6" gutterBottom>
                    {t('backtest:detail.taskInformation')}
                  </Typography>
                  <Box
                    sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}
                  >
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
                        <Typography variant="body1">
                          {task.description}
                        </Typography>
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
                        {task.pip_size
                          ? parseFloat(task.pip_size)
                          : task.pip_size}
                      </Typography>
                    </Box>

                    <Box>
                      <Typography variant="caption" color="text.secondary">
                        {t('common:labels.status')}
                      </Typography>
                      <Box sx={{ mt: 0.5 }}>
                        <StatusBadge
                          status={polledStatus?.status || task.status}
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
                  <Box
                    sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}
                  >
                    <Box>
                      <Typography variant="caption" color="text.secondary">
                        {t('common:labels.strategyConfiguration')}
                      </Typography>
                      <Link
                        component="button"
                        variant="body1"
                        onClick={() =>
                          navigate(`/configurations/${task.config_id}`)
                        }
                        sx={{ textAlign: 'left', display: 'block' }}
                      >
                        {task.config_name}
                      </Link>
                    </Box>

                    <Box>
                      <Typography variant="caption" color="text.secondary">
                        {t('common:labels.strategyType')}
                      </Typography>
                      <Typography
                        variant="body1"
                        sx={{ textTransform: 'capitalize' }}
                      >
                        {getStrategyDisplayName(strategies, task.strategy_type)}
                      </Typography>
                    </Box>

                    <Box>
                      <Typography variant="caption" color="text.secondary">
                        {t('backtest:detail.dataSource')}
                      </Typography>
                      <Typography
                        variant="body1"
                        sx={{ textTransform: 'capitalize' }}
                      >
                        {task.data_source}
                      </Typography>
                    </Box>

                    <Box>
                      <Typography variant="caption" color="text.secondary">
                        {t('backtest:detail.initialBalance')}
                      </Typography>
                      <Typography variant="body1">
                        ${parseFloat(task.initial_balance).toFixed(2)}
                      </Typography>
                    </Box>

                    <Box>
                      <Typography variant="caption" color="text.secondary">
                        {t('backtest:detail.commissionPerTrade')}
                      </Typography>
                      <Typography variant="body1">
                        ${parseFloat(task.commission_per_trade).toFixed(2)}
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
                        {new Date(task.start_time).toLocaleString()}
                      </Typography>
                    </Box>
                    <Box>
                      <Typography variant="caption" color="text.secondary">
                        {t('backtest:detail.endTime')}
                      </Typography>
                      <Typography variant="body1">
                        {new Date(task.end_time).toLocaleString()}
                      </Typography>
                    </Box>
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
                          s.pnl.realized >= 0 ? 'success.main' : 'error.main'
                        }
                      >
                        {s.pnl.realized >= 0 ? '+' : ''}
                        {s.pnl.realized.toFixed(2)} {pnlCurrency}
                      </Typography>
                    </Box>
                    <Box>
                      <Typography variant="caption" color="text.secondary">
                        {t('backtest:detail.unrealizedPnl')} ({pnlCurrency})
                      </Typography>
                      <Typography
                        variant="body1"
                        color={
                          s.pnl.unrealized >= 0 ? 'success.main' : 'error.main'
                        }
                      >
                        {s.pnl.unrealized >= 0 ? '+' : ''}
                        {s.pnl.unrealized.toFixed(2)} {pnlCurrency}
                      </Typography>
                    </Box>
                    {s.execution.currentBalance != null && (
                      <Box>
                        <Typography variant="caption" color="text.secondary">
                          {t('backtest:detail.currentBalance')}
                        </Typography>
                        <Typography variant="body1">
                          {s.execution.currentBalanceDisplay != null &&
                          s.execution.displayCurrency &&
                          s.execution.displayCurrency !==
                            s.execution.accountCurrency ? (
                            <>
                              {s.execution.currentBalanceDisplay.toFixed(0)}{' '}
                              {s.execution.displayCurrency}
                              <Typography
                                component="span"
                                variant="body2"
                                color="text.secondary"
                                sx={{ ml: 1 }}
                              >
                                ({s.execution.currentBalance.toFixed(2)}{' '}
                                {s.execution.accountCurrency})
                              </Typography>
                            </>
                          ) : (
                            <>
                              {s.execution.currentBalance.toFixed(2)}{' '}
                              {s.execution.accountCurrency || pnlCurrency}
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
                        {s.counts.totalTrades}
                      </Typography>
                    </Box>
                    <Box>
                      <Typography variant="caption" color="text.secondary">
                        {t('backtest:detail.openPositions')}
                      </Typography>
                      <Typography variant="body1">
                        {s.counts.openPositions}
                      </Typography>
                    </Box>
                    <Box>
                      <Typography variant="caption" color="text.secondary">
                        {t('backtest:detail.closedPositions')}
                      </Typography>
                      <Typography variant="body1">
                        {s.counts.closedPositions}
                      </Typography>
                    </Box>
                    {s.execution.ticksProcessed > 0 && (
                      <Box>
                        <Typography variant="caption" color="text.secondary">
                          {t('backtest:detail.ticksProcessed')}
                        </Typography>
                        <Typography variant="body1">
                          {s.execution.ticksProcessed.toLocaleString()}
                        </Typography>
                      </Box>
                    )}
                  </Box>
                </Grid>

                <Grid size={{ xs: 12 }}>
                  <Divider sx={{ my: 2 }} />
                  <ExecutionHistoryTable
                    taskId={taskId}
                    taskType={TaskType.BACKTEST}
                  />
                </Grid>
              </Grid>
            </Box>
          </LazyTabPanel>
        )}

        {/* Trend Tab */}
        {visibleTabIds.includes('trend') && (
          <LazyTabPanel
            value={activeTabIndex}
            index={visibleTabIds.indexOf('trend')}
          >
            <TaskTrendPanel
              taskId={taskId}
              taskType={TaskType.BACKTEST}
              instrument={task.instrument}
              executionRunId={task.execution_id}
              startTime={task.start_time}
              endTime={task.end_time}
              latestExecution={task.latest_execution}
              currentTick={polledTick ?? null}
              enableRealTimeUpdates={
                (polledStatus?.status || task.status) === TaskStatus.RUNNING
              }
              pipSize={task.pip_size ? parseFloat(task.pip_size) : null}
              configId={task.config_id}
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
              executionRunId={task.execution_id}
              enableRealTimeUpdates={
                (polledStatus?.status || task.status) === TaskStatus.RUNNING
              }
              currentPrice={
                polledTick?.price != null ? parseFloat(polledTick.price) : null
              }
              pipSize={task.pip_size ? parseFloat(task.pip_size) : null}
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
              executionRunId={task.execution_id}
              enableRealTimeUpdates={
                (polledStatus?.status || task.status) === TaskStatus.RUNNING
              }
              pipSize={task.pip_size ? parseFloat(task.pip_size) : null}
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
              executionRunId={task.execution_id}
              enableRealTimeUpdates={
                (polledStatus?.status || task.status) === TaskStatus.RUNNING
              }
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
              executionRunId={task.execution_id}
              enableRealTimeUpdates={
                (polledStatus?.status || task.status) === TaskStatus.RUNNING
              }
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
              executionRunId={task.execution_id}
              enableRealTimeUpdates={
                (polledStatus?.status || task.status) === TaskStatus.RUNNING
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
            invalidateBacktestTasksCache();
            navigate('/backtest-tasks', { state: { deleted: true } });
          } catch {
            // Error handled by mutation hook
          }
        }}
        isLoading={deleteTask.isLoading}
        hasExecutionHistory={true}
      />
    </Container>
  );
};

export default BacktestTaskDetail;
