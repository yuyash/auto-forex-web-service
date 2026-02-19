/**
 * BacktestTaskDetail Component
 *
 * Main detail view for backtest tasks using task-based API endpoints.
 * Displays task info and tab navigation for Events, Logs, Trades, and Replay.
 *
 */

import React, { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
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
} from '@mui/material';
import { useBacktestTask } from '../../hooks/useBacktestTasks';
import { useTaskPolling } from '../../hooks/useTaskPolling';
import { TaskControlButtons } from '../common/TaskControlButtons';
import { TaskEventsTable } from '../tasks/detail/TaskEventsTable';
import { StatusBadge } from '../tasks/display/StatusBadge';
import { TaskLogsTable } from '../tasks/detail/TaskLogsTable';
import { TaskTradesTable } from '../tasks/detail/TaskTradesTable';
import { TaskReplayPanel } from '../tasks/detail/TaskReplayPanel';
import { TaskProgress } from '../tasks/TaskProgress';
import { useOverviewPnl } from '../../hooks/useOverviewPnl';
import { TaskStatus, TaskType } from '../../types/common';

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

function TabPanel(props: TabPanelProps) {
  const { children, value, index, ...other } = props;

  const isActive = value === index;

  return (
    <div
      role="tabpanel"
      hidden={!isActive}
      id={`task-tabpanel-${index}`}
      aria-labelledby={`task-tab-${index}`}
      style={{
        display: isActive ? 'flex' : 'none',
        flexDirection: 'column',
        flex: 1,
        minHeight: 0,
        overflow: 'auto',
      }}
      {...other}
    >
      <Box
        sx={{
          pt: 1,
          display: 'flex',
          flexDirection: 'column',
          flex: 1,
          minHeight: 0,
        }}
      >
        {children}
      </Box>
    </div>
  );
}

function a11yProps(index: number) {
  return {
    id: `task-tab-${index}`,
    'aria-controls': `task-tabpanel-${index}`,
  };
}

export const BacktestTaskDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const taskId = id || '';

  // Get tab from URL, default to 'overview'
  const tabParam = searchParams.get('tab') || 'overview';
  const tabMap: Record<string, number> = {
    overview: 0,
    trades: 1,
    replay: 2,
    events: 3,
    logs: 4,
    equity: 2,
  };
  const tabNames = ['overview', 'trades', 'replay', 'events', 'logs'];
  const [tabValue, setTabValue] = useState(tabMap[tabParam] || 0);

  const {
    data: task,
    isLoading,
    error,
    refetch,
  } = useBacktestTask(taskId || undefined);

  const overviewSummary = useOverviewPnl(
    taskId,
    TaskType.BACKTEST,
    task?.latest_execution
  );

  // Use HTTP polling for task status updates
  const {
    status: polledStatus,
    startPolling,
    isPolling,
  } = useTaskPolling(taskId, 'backtest', {
    enabled: !!taskId,
    pollStatus: true,
    interval: 3000, // Poll every 3 seconds for active tasks
  });

  // Refetch when status changes
  const prevStatusRef = useRef<string | undefined>(undefined);
  useEffect(() => {
    if (polledStatus) {
      // Refetch when status changes
      if (polledStatus.status !== prevStatusRef.current) {
        refetch();
      }
      prevStatusRef.current = polledStatus.status;
    }
  }, [polledStatus, refetch]);

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
        <Alert severity="error">{error?.message || 'Task not found'}</Alert>
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
        overflow: 'hidden',
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
          Backtest Tasks
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
                p: '4px',
                mb: '4px',
              }}
            >
              <Typography variant="h4" component="h1">
                {task.name}
              </Typography>
              <StatusBadge status={polledStatus?.status || task.status} />
            </Box>

            <Typography variant="body2" color="text.secondary">
              {task.strategy_type}
            </Typography>

            {task.description && (
              <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                {task.description}
              </Typography>
            )}

            {/* Progress Bar */}
            <Box sx={{ mt: 2, maxWidth: 600 }}>
              <TaskProgress
                status={polledStatus?.status || task.status}
                progress={polledStatus?.progress ?? task.progress ?? 0}
                compact={false}
                showPercentage={true}
              />
            </Box>
          </Box>

          <Box sx={{ display: 'flex', gap: 1 }}>
            <TaskControlButtons
              taskId={taskId}
              status={polledStatus?.status || task.status}
              onStart={async (id) => {
                const { backtestTasksApi } = await import('../../services/api');
                await backtestTasksApi.start(id);
                console.log(
                  '[BacktestTaskDetail] Task action success, refetching'
                );
                refetch();
                if (!isPolling) {
                  console.log(
                    '[BacktestTaskDetail] Restarting polling after task action'
                  );
                  startPolling();
                }
              }}
              onStop={async (id) => {
                const { backtestTasksApi } = await import('../../services/api');
                await backtestTasksApi.stop(id);
                refetch();
              }}
              onRestart={async (id) => {
                const { backtestTasksApi } = await import('../../services/api');
                await backtestTasksApi.restart(id);
                refetch();
                if (!isPolling) {
                  startPolling();
                }
              }}
              onResume={async (id) => {
                const { backtestTasksApi } = await import('../../services/api');
                await backtestTasksApi.resume(id);
                refetch();
                if (!isPolling) {
                  startPolling();
                }
              }}
              onDelete={async (id) => {
                const { TradingService } = await import(
                  '../../api/generated/services/TradingService'
                );
                await TradingService.tradingTasksBacktestDestroy(String(id));
                navigate('/backtest-tasks');
              }}
            />
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
        <Tabs
          value={currentTabValue}
          onChange={handleTabChange}
          aria-label="task detail tabs"
          sx={{ borderBottom: 1, borderColor: 'divider', flexShrink: 0 }}
        >
          <Tab label="Overview" {...a11yProps(0)} />
          <Tab label="Trades" {...a11yProps(1)} />
          <Tab label="Replay" {...a11yProps(2)} />
          <Tab label="Raw Events" {...a11yProps(3)} />
          <Tab label="Raw Logs" {...a11yProps(4)} />
        </Tabs>

        {/* Overview Tab */}
        <TabPanel value={currentTabValue} index={0}>
          <Box sx={{ p: 3 }}>
            <Grid container spacing={3}>
              <Grid size={{ xs: 12, md: 6 }}>
                <Typography variant="h6" gutterBottom>
                  Task Information
                </Typography>
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                  <Box>
                    <Typography variant="caption" color="text.secondary">
                      Name
                    </Typography>
                    <Typography variant="body1">{task.name}</Typography>
                  </Box>

                  {task.description && (
                    <Box>
                      <Typography variant="caption" color="text.secondary">
                        Description
                      </Typography>
                      <Typography variant="body1">
                        {task.description}
                      </Typography>
                    </Box>
                  )}

                  <Box>
                    <Typography variant="caption" color="text.secondary">
                      Instrument
                    </Typography>
                    <Typography variant="body1">{task.instrument}</Typography>
                  </Box>

                  <Box>
                    <Typography variant="caption" color="text.secondary">
                      Pip Size
                    </Typography>
                    <Typography variant="body1">{task.pip_size}</Typography>
                  </Box>

                  <Box>
                    <Typography variant="caption" color="text.secondary">
                      Trading Mode
                    </Typography>
                    <Typography
                      variant="body1"
                      sx={{ textTransform: 'capitalize' }}
                    >
                      {task.trading_mode}
                    </Typography>
                  </Box>

                  <Box>
                    <Typography variant="caption" color="text.secondary">
                      Status
                    </Typography>
                    <Box sx={{ mt: 0.5 }}>
                      <StatusBadge
                        status={polledStatus?.status || task.status}
                        size="small"
                        showIcon={false}
                      />
                    </Box>
                  </Box>
                </Box>
              </Grid>

              <Grid size={{ xs: 12, md: 6 }}>
                <Typography variant="h6" gutterBottom>
                  Configuration
                </Typography>
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                  <Box>
                    <Typography variant="caption" color="text.secondary">
                      Strategy Configuration
                    </Typography>
                    <Link
                      component="button"
                      variant="body1"
                      onClick={() =>
                        navigate(`/configurations/${task.config_id}`)
                      }
                      sx={{ textAlign: 'left' }}
                    >
                      {task.config_name}
                    </Link>
                  </Box>

                  <Box>
                    <Typography variant="caption" color="text.secondary">
                      Strategy Type
                    </Typography>
                    <Typography
                      variant="body1"
                      sx={{ textTransform: 'capitalize' }}
                    >
                      {task.strategy_type}
                    </Typography>
                  </Box>

                  <Box>
                    <Typography variant="caption" color="text.secondary">
                      Data Source
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
                      Initial Balance
                    </Typography>
                    <Typography variant="body1">
                      ${parseFloat(task.initial_balance).toFixed(2)}
                    </Typography>
                  </Box>

                  <Box>
                    <Typography variant="caption" color="text.secondary">
                      Commission Per Trade
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
                  Backtest Period
                </Typography>
                <Box sx={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                  <Box>
                    <Typography variant="caption" color="text.secondary">
                      Start Time
                    </Typography>
                    <Typography variant="body1">
                      {new Date(task.start_time).toLocaleString()}
                    </Typography>
                  </Box>
                  <Box>
                    <Typography variant="caption" color="text.secondary">
                      End Time
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
                  Results
                </Typography>
                <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
                  <Box>
                    <Typography variant="caption" color="text.secondary">
                      Realized PnL ({pnlCurrency})
                    </Typography>
                    <Typography
                      variant="body1"
                      color={
                        overviewSummary.realizedPnl >= 0
                          ? 'success.main'
                          : 'error.main'
                      }
                    >
                      {overviewSummary.realizedPnl >= 0 ? '+' : ''}
                      {overviewSummary.realizedPnl.toFixed(2)} {pnlCurrency}
                    </Typography>
                  </Box>
                  <Box>
                    <Typography variant="caption" color="text.secondary">
                      Unrealized PnL ({pnlCurrency})
                    </Typography>
                    <Typography
                      variant="body1"
                      color={
                        overviewSummary.unrealizedPnl >= 0
                          ? 'success.main'
                          : 'error.main'
                      }
                    >
                      {overviewSummary.unrealizedPnl >= 0 ? '+' : ''}
                      {overviewSummary.unrealizedPnl.toFixed(2)} {pnlCurrency}
                    </Typography>
                  </Box>
                  <Box>
                    <Typography variant="caption" color="text.secondary">
                      Total Trades (count)
                    </Typography>
                    <Typography variant="body1">
                      {overviewSummary.totalTrades} trades
                    </Typography>
                  </Box>
                </Box>
              </Grid>

              {(task.started_at || task.completed_at) && (
                <Grid size={{ xs: 12 }}>
                  <Divider sx={{ my: 2 }} />
                  <Typography variant="h6" gutterBottom>
                    Execution Timeline
                  </Typography>
                  <Box sx={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                    {task.started_at && (
                      <Box>
                        <Typography variant="caption" color="text.secondary">
                          Started At
                        </Typography>
                        <Typography variant="body1">
                          {new Date(task.started_at).toLocaleString()}
                        </Typography>
                      </Box>
                    )}
                    {task.completed_at && (
                      <Box>
                        <Typography variant="caption" color="text.secondary">
                          Completed At
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
        </TabPanel>

        {/* Trades Tab */}
        <TabPanel value={currentTabValue} index={1}>
          <TaskTradesTable
            taskId={taskId}
            taskType={TaskType.BACKTEST}
            enableRealTimeUpdates={
              (polledStatus?.status || task.status) === TaskStatus.RUNNING
            }
            currentPrice={
              polledStatus?.current_tick?.price != null
                ? parseFloat(polledStatus.current_tick.price)
                : task.current_tick?.price != null
                  ? parseFloat(task.current_tick.price)
                  : null
            }
            pipSize={task.pip_size ? parseFloat(task.pip_size) : null}
          />
        </TabPanel>

        {/* Replay Tab */}
        <TabPanel value={currentTabValue} index={2}>
          <TaskReplayPanel
            taskId={taskId}
            taskType={TaskType.BACKTEST}
            instrument={task.instrument}
            startTime={task.start_time}
            endTime={task.end_time}
            latestExecution={task.latest_execution}
            currentTick={
              polledStatus?.current_tick ?? task.current_tick ?? null
            }
            enableRealTimeUpdates={
              (polledStatus?.status || task.status) === TaskStatus.RUNNING
            }
            pipSize={task.pip_size ? parseFloat(task.pip_size) : null}
          />
        </TabPanel>

        {/* Raw Events Tab */}
        <TabPanel value={currentTabValue} index={3}>
          <TaskEventsTable
            taskId={taskId}
            taskType={TaskType.BACKTEST}
            enableRealTimeUpdates={
              (polledStatus?.status || task.status) === TaskStatus.RUNNING
            }
          />
        </TabPanel>

        {/* Raw Logs Tab */}
        <TabPanel value={currentTabValue} index={4}>
          <TaskLogsTable
            taskId={taskId}
            taskType={TaskType.BACKTEST}
            executionId={task.celery_task_id || undefined}
            enableRealTimeUpdates={
              (polledStatus?.status || task.status) === TaskStatus.RUNNING
            }
          />
        </TabPanel>
      </Paper>
    </Container>
  );
};

export default BacktestTaskDetail;
