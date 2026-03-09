/**
 * TradingTaskDetail Component
 *
 * Main detail view for trading tasks using task-based API endpoints.
 * Displays task info and tab navigation for Events, Logs, Trades, and Replay.
 *
 */

import React, { useState } from 'react';
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
import { Edit as EditIcon, Delete as DeleteIcon } from '@mui/icons-material';
import { useTradingTask } from '../../hooks/useTradingTasks';
import { useTaskSummary } from '../../hooks/useTaskSummary';
import {
  useStrategies,
  getStrategyDisplayName,
} from '../../hooks/useStrategies';
import { TaskControlButtons } from '../common/TaskControlButtons';
import { TaskEventsTable } from '../tasks/detail/TaskEventsTable';
import { StatusBadge } from '../tasks/display/StatusBadge';
import { TaskLogsTable } from '../tasks/detail/TaskLogsTable';
import { TaskPositionsTable } from '../tasks/detail/TaskPositionsTable';
import { TaskTradesTable } from '../tasks/detail/TaskTradesTable';
import { TaskTrendPanel } from '../tasks/detail/TaskTrendPanel';
import { TaskOrdersTable } from '../tasks/detail/TaskOrdersTable';
import { TaskStatus, TaskType } from '../../types/common';
import { DeleteTaskDialog } from '../tasks/actions/DeleteTaskDialog';
import { useDeleteTradingTask } from '../../hooks/useTradingTaskMutations';
import { invalidateTradingTasksCache } from '../../hooks/useTradingTasks';
import { LazyTabPanel } from '../common/LazyTabPanel';

function a11yProps(index: number) {
  return {
    id: `task-tab-${index}`,
    'aria-controls': `task-tabpanel-${index}`,
  };
}

export const TradingTaskDetail: React.FC = () => {
  const { t } = useTranslation(['trading', 'common']);
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const taskId = id || '';
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const deleteTask = useDeleteTradingTask();

  // Get tab from URL, default to 'overview'
  const tabParam = searchParams.get('tab') || 'overview';
  const tabMap: Record<string, number> = {
    overview: 0,
    positions: 1,
    trades: 2,
    replay: 3,
    events: 4,
    logs: 5,
    orders: 6,
    equity: 3,
  };
  const tabNames = [
    'overview',
    'positions',
    'trades',
    'replay',
    'events',
    'logs',
    'orders',
  ];
  const [tabValue, setTabValue] = useState(tabMap[tabParam] || 0);

  const { data: task, isLoading, error, refetch } = useTradingTask(taskId);
  const { strategies } = useStrategies();

  const overviewSummary = useTaskSummary(taskId, TaskType.TRADING);

  // Use summary tick data for running tasks
  const { summary: s } = overviewSummary;
  const currentTick = s.tick.timestamp
    ? {
        timestamp: s.tick.timestamp,
        price: s.tick.mid != null ? String(s.tick.mid) : null,
      }
    : null;

  // Derive tab value from URL parameter (use this for rendering)
  const currentTabValue =
    tabMap[tabParam] !== undefined ? tabMap[tabParam] : tabValue;

  const handleTabChange = (_event: React.SyntheticEvent, newValue: number) => {
    setTabValue(newValue);
    // Update URL with tab name
    const tabName = tabNames[newValue];
    setSearchParams({ tab: tabName });
  };

  const handleBack = () => {
    navigate('/trading-tasks');
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
    <Container maxWidth={false} sx={{ py: 4 }}>
      {/* Breadcrumbs */}
      <Breadcrumbs sx={{ mb: 2 }}>
        <Link
          component="button"
          variant="body1"
          onClick={handleBack}
          sx={{ cursor: 'pointer', textDecoration: 'none' }}
        >
          {t('trading:pages.title')}
        </Link>
        <Typography color="text.primary">{task.name}</Typography>
      </Breadcrumbs>

      {/* Header */}
      <Paper sx={{ p: 2, pb: 1, mb: 2 }}>
        <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 2 }}>
          <Box sx={{ flex: 1 }}>
            <Box
              sx={{
                display: 'flex',
                alignItems: 'center',
                gap: 2,
                p: '8px',
                mb: '8px',
              }}
            >
              <Typography variant="h4" component="h1">
                {task.name}
              </Typography>
              <StatusBadge status={task.status} />
            </Box>

            <Typography
              variant="body2"
              color="text.secondary"
              sx={{ pl: '8px' }}
            >
              Configuration: {task.config_name} • Strategy:{' '}
              {getStrategyDisplayName(strategies, task.strategy_type)}
            </Typography>

            {task.description && (
              <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                {task.description}
              </Typography>
            )}

            {/* Progress Percentage */}
            {task.status === TaskStatus.RUNNING && (
              <Typography
                variant="body2"
                color="text.secondary"
                sx={{ mt: 2, fontWeight: 600 }}
              >
                {Math.round(Math.min(Math.max(s.task.progress, 0), 100))}%{' '}
                {t('trading:detail.completed')}
              </Typography>
            )}
          </Box>

          <Box sx={{ display: 'flex', gap: 1 }}>
            <TaskControlButtons
              taskId={taskId}
              status={task.status}
              onStart={async (id) => {
                const { tradingTasksApi } = await import(
                  '../../services/api/tradingTasks'
                );
                await tradingTasksApi.start(id);
                refetch();
              }}
              onStop={async (id) => {
                const { tradingTasksApi } = await import(
                  '../../services/api/tradingTasks'
                );
                await tradingTasksApi.stop(id);
                refetch();
              }}
              onRestart={async (id) => {
                const { tradingTasksApi } = await import(
                  '../../services/api/tradingTasks'
                );
                await tradingTasksApi.restart(id);
                refetch();
              }}
              onResume={async (id) => {
                const { tradingTasksApi } = await import(
                  '../../services/api/tradingTasks'
                );
                await tradingTasksApi.resume(id);
                refetch();
              }}
              onPause={async (id) => {
                const { tradingTasksApi } = await import(
                  '../../services/api/tradingTasks'
                );
                await tradingTasksApi.pause(id);
                refetch();
              }}
            />
            <Box sx={{ display: 'flex' }}>
              <Tooltip title={t('common:actions.edit')}>
                <span>
                  <IconButton
                    onClick={() => navigate(`/trading-tasks/${taskId}/edit`)}
                    disabled={
                      task.status === TaskStatus.RUNNING ||
                      task.status === TaskStatus.PAUSED
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
                      task.status === TaskStatus.RUNNING ||
                      task.status === TaskStatus.PAUSED
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
      <Paper sx={{ mb: 0 }}>
        <Tabs
          value={currentTabValue}
          onChange={handleTabChange}
          aria-label="task detail tabs"
          sx={{ borderBottom: 1, borderColor: 'divider' }}
        >
          <Tab label={t('trading:tabs.overview')} {...a11yProps(0)} />
          <Tab label={t('trading:tabs.positions')} {...a11yProps(1)} />
          <Tab label={t('trading:tabs.trades')} {...a11yProps(2)} />
          <Tab label={t('trading:tabs.replay')} {...a11yProps(3)} />
          <Tab label={t('trading:tabs.events')} {...a11yProps(4)} />
          <Tab label={t('trading:tabs.logs')} {...a11yProps(5)} />
          <Tab label={t('trading:tabs.orders')} {...a11yProps(6)} />
        </Tabs>

        {/* Overview Tab */}
        <LazyTabPanel value={currentTabValue} index={0}>
          <Box sx={{ p: 3 }}>
            <Grid container spacing={3}>
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
                      <StatusBadge status={task.status} showIcon={false} />
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
                        s.pnl.realized >= 0 ? 'success.main' : 'error.main'
                      }
                    >
                      {s.pnl.realized >= 0 ? '+' : ''}
                      {s.pnl.realized.toFixed(2)} {pnlCurrency}
                    </Typography>
                  </Box>
                  <Box>
                    <Typography variant="caption" color="text.secondary">
                      {t('trading:detail.unrealizedPnl')} ({pnlCurrency})
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
                        {t('trading:detail.currentBalance')}
                      </Typography>
                      <Typography variant="body1">
                        {s.execution.currentBalance.toFixed(2)} {pnlCurrency}
                      </Typography>
                    </Box>
                  )}
                  <Box>
                    <Typography variant="caption" color="text.secondary">
                      {t('trading:detail.totalTradesCount')}
                    </Typography>
                    <Typography variant="body1">
                      {s.counts.totalTrades}
                    </Typography>
                  </Box>
                  <Box>
                    <Typography variant="caption" color="text.secondary">
                      {t('trading:detail.openPositions')}
                    </Typography>
                    <Typography variant="body1">
                      {s.counts.openPositions}
                    </Typography>
                  </Box>
                  <Box>
                    <Typography variant="caption" color="text.secondary">
                      {t('trading:detail.closedPositions')}
                    </Typography>
                    <Typography variant="body1">
                      {s.counts.closedPositions}
                    </Typography>
                  </Box>
                  {s.execution.ticksProcessed > 0 && (
                    <Box>
                      <Typography variant="caption" color="text.secondary">
                        {t('trading:detail.ticksProcessed')}
                      </Typography>
                      <Typography variant="body1">
                        {s.execution.ticksProcessed.toLocaleString()}
                      </Typography>
                    </Box>
                  )}
                </Box>
              </Grid>

              {(task.started_at || task.completed_at) && (
                <Grid size={{ xs: 12 }}>
                  <Divider sx={{ my: 2 }} />
                  <Typography variant="h6" gutterBottom>
                    {t('trading:detail.executionTimeline')}
                  </Typography>
                  <Box sx={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                    {task.execution_run_id != null && (
                      <Box>
                        <Typography variant="caption" color="text.secondary">
                          {t('trading:detail.executionId')}
                        </Typography>
                        <Typography variant="body1">
                          {task.execution_run_id}
                        </Typography>
                      </Box>
                    )}
                    {task.started_at && (
                      <Box>
                        <Typography variant="caption" color="text.secondary">
                          {t('trading:detail.startedAt')}
                        </Typography>
                        <Typography variant="body1">
                          {new Date(task.started_at).toLocaleString()}
                        </Typography>
                      </Box>
                    )}
                    {task.completed_at && (
                      <Box>
                        <Typography variant="caption" color="text.secondary">
                          {t('trading:detail.completedAt')}
                        </Typography>
                        <Typography variant="body1">
                          {new Date(task.completed_at).toLocaleString()}
                        </Typography>
                      </Box>
                    )}
                  </Box>
                </Grid>
              )}
            </Grid>
          </Box>
        </LazyTabPanel>

        {/* Positions Tab */}
        <LazyTabPanel value={currentTabValue} index={1}>
          <TaskPositionsTable
            taskId={taskId}
            taskType={TaskType.TRADING}
            enableRealTimeUpdates={task.status === TaskStatus.RUNNING}
            currentPrice={
              currentTick?.price != null ? parseFloat(currentTick.price) : null
            }
            pipSize={task.pip_size ? parseFloat(task.pip_size) : null}
          />
        </LazyTabPanel>

        {/* Trades Tab */}
        <LazyTabPanel value={currentTabValue} index={2}>
          <TaskTradesTable
            taskId={taskId}
            taskType={TaskType.TRADING}
            enableRealTimeUpdates={task.status === TaskStatus.RUNNING}
            pipSize={task.pip_size ? parseFloat(task.pip_size) : null}
          />
        </LazyTabPanel>

        {/* Replay Tab */}
        <LazyTabPanel value={currentTabValue} index={3}>
          <TaskTrendPanel
            taskId={taskId}
            taskType={TaskType.TRADING}
            instrument={task.instrument}
            latestExecution={task.latest_execution}
            enableRealTimeUpdates={task.status === TaskStatus.RUNNING}
            currentTick={currentTick}
            pipSize={task.pip_size ? parseFloat(task.pip_size) : null}
            configId={task.config_id}
          />
        </LazyTabPanel>

        {/* Events Tab */}
        <LazyTabPanel value={currentTabValue} index={4}>
          <TaskEventsTable
            taskId={taskId}
            taskType={TaskType.TRADING}
            enableRealTimeUpdates={task.status === TaskStatus.RUNNING}
          />
        </LazyTabPanel>

        {/* Logs Tab */}
        <LazyTabPanel value={currentTabValue} index={5}>
          <TaskLogsTable
            taskId={taskId}
            taskType={TaskType.TRADING}
            executionRunId={task.execution_run_id}
            enableRealTimeUpdates={task.status === TaskStatus.RUNNING}
          />
        </LazyTabPanel>

        {/* Orders Tab */}
        <LazyTabPanel value={currentTabValue} index={6}>
          <TaskOrdersTable
            taskId={taskId}
            taskType={TaskType.TRADING}
            executionRunId={task.execution_run_id}
            enableRealTimeUpdates={task.status === TaskStatus.RUNNING}
          />
        </LazyTabPanel>
      </Paper>

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
            // Error handled by mutation hook
          }
        }}
        isLoading={deleteTask.isLoading}
        hasExecutionHistory={true}
      />
    </Container>
  );
};

export default TradingTaskDetail;
