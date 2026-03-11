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
  useMediaQuery,
  useTheme,
} from '@mui/material';
import {
  Edit as EditIcon,
  Delete as DeleteIcon,
  Settings as SettingsIcon,
} from '@mui/icons-material';
import { useTradingTask } from '../../hooks/useTradingTasks';
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
import { useDeleteTradingTask } from '../../hooks/useTradingTaskMutations';
import { invalidateTradingTasksCache } from '../../hooks/useTradingTasks';
import { LazyTabPanel } from '../common/LazyTabPanel';
import { TabConfigDialog } from '../common/TabConfigDialog';
import { useTabConfig, type TabItem } from '../../hooks/useTabConfig';

function a11yProps(index: number) {
  return { id: `task-tab-${index}`, 'aria-controls': `task-tabpanel-${index}` };
}

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

  const { data: task, isLoading, error, refetch } = useTradingTask(taskId);
  const { strategies } = useStrategies();
  const isTaskRunning = task?.status === TaskStatus.RUNNING;
  const overviewSummary = useTaskSummary(
    taskId,
    TaskType.TRADING,
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
  const {
    status: polledStatus,
    startPolling,
    isPolling,
  } = useTaskPolling(taskId, 'trading', {
    enabled: !!taskId,
    pollStatus: true,
    interval: 3000,
  });
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
  const pnlCurrency = task.instrument?.includes('_')
    ? task.instrument.split('_')[1]
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
      <Paper sx={{ p: { xs: 1.5, sm: 2 }, pb: 1, mb: { xs: 1, sm: 2 } }}>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
          {/* Row 1: Task name + status badge */}
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              gap: 1,
              p: '4px',
              flexWrap: 'wrap',
            }}
          >
            <Typography
              variant="h4"
              component="h1"
              sx={{
                fontSize: { xs: '1.25rem', sm: '2.125rem' },
                wordBreak: 'break-word',
                flex: 1,
                minWidth: 0,
              }}
            >
              {task.name}
            </Typography>
            <StatusBadge status={polledStatus?.status || task.status} />
          </Box>

          {/* Row 2: Controls — separate row on mobile */}
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              gap: 1,
              pl: '4px',
              flexWrap: 'wrap',
            }}
          >
            <TaskControlButtons
              taskId={taskId}
              status={polledStatus?.status || task.status}
              onStart={async (id) => {
                const { tradingTasksApi } = await import(
                  '../../services/api/tradingTasks'
                );
                await tradingTasksApi.start(id);
                refetch();
                if (!isPolling) startPolling();
              }}
              onStop={async (id) => {
                const { tradingTasksApi } = await import(
                  '../../services/api/tradingTasks'
                );
                await tradingTasksApi.stop(id);
              }}
              onRestart={async (id) => {
                const { tradingTasksApi } = await import(
                  '../../services/api/tradingTasks'
                );
                await tradingTasksApi.restart(id);
                refetch();
                if (!isPolling) startPolling();
              }}
              onResume={async (id) => {
                const { tradingTasksApi } = await import(
                  '../../services/api/tradingTasks'
                );
                await tradingTasksApi.resume(id);
                refetch();
                if (!isPolling) startPolling();
              }}
              onPause={async (id) => {
                const { tradingTasksApi } = await import(
                  '../../services/api/tradingTasks'
                );
                await tradingTasksApi.pause(id);
                refetch();
              }}
            />
            <Tooltip title={t('common:actions.edit')}>
              <span>
                <IconButton
                  size={isMobile ? 'small' : 'medium'}
                  onClick={() => navigate(`/trading-tasks/${taskId}/edit`)}
                  disabled={
                    (polledStatus?.status || task.status) ===
                      TaskStatus.RUNNING ||
                    (polledStatus?.status || task.status) === TaskStatus.PAUSED
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
                  size={isMobile ? 'small' : 'medium'}
                  onClick={() => setDeleteDialogOpen(true)}
                  disabled={
                    (polledStatus?.status || task.status) ===
                      TaskStatus.RUNNING ||
                    (polledStatus?.status || task.status) === TaskStatus.PAUSED
                  }
                  color="error"
                  aria-label={t('common:actions.delete')}
                >
                  <DeleteIcon />
                </IconButton>
              </span>
            </Tooltip>
          </Box>

          {/* Strategy name */}
          <Typography variant="body2" color="text.secondary" sx={{ pl: '4px' }}>
            {getStrategyDisplayName(strategies, task.strategy_type)}
          </Typography>

          {task.description && (
            <Typography
              variant="body2"
              color="text.secondary"
              sx={{ pl: '4px' }}
            >
              {task.description}
            </Typography>
          )}

          {/* Price ticker — compact on mobile */}
          {s.tick.mid != null &&
            (() => {
              const decimals = task.pip_size
                ? String(task.pip_size).split('.')[1]?.length || 5
                : 5;
              return (
                <Box
                  sx={{
                    display: 'flex',
                    flexWrap: 'wrap',
                    alignItems: 'center',
                    gap: { xs: 0.5, sm: 1 },
                    pl: '4px',
                    rowGap: 0.25,
                    fontSize: { xs: '0.7rem', sm: '0.875rem' },
                  }}
                >
                  <Typography
                    variant="body2"
                    color="text.secondary"
                    component="span"
                    sx={{ fontSize: 'inherit' }}
                  >
                    {task.instrument}:
                  </Typography>
                  <Typography
                    variant="caption"
                    color="text.secondary"
                    component="span"
                    sx={{ fontFamily: 'monospace', fontSize: 'inherit' }}
                  >
                    Mid {s.tick.mid.toFixed(decimals)}
                  </Typography>
                  {s.tick.bid != null && s.tick.ask != null && (
                    <>
                      <Typography
                        variant="caption"
                        color="text.secondary"
                        component="span"
                        sx={{ fontFamily: 'monospace', fontSize: 'inherit' }}
                      >
                        Bid {s.tick.bid.toFixed(decimals)}
                      </Typography>
                      <Typography
                        variant="caption"
                        color="text.secondary"
                        component="span"
                        sx={{ fontFamily: 'monospace', fontSize: 'inherit' }}
                      >
                        Ask {s.tick.ask.toFixed(decimals)}
                      </Typography>
                      <Typography
                        variant="caption"
                        color="text.secondary"
                        component="span"
                        sx={{ fontFamily: 'monospace', fontSize: 'inherit' }}
                      >
                        Spd {(s.tick.ask - s.tick.bid).toFixed(decimals)}
                      </Typography>
                    </>
                  )}
                </Box>
              );
            })()}

          {/* Progress */}
          {(polledStatus?.status || task.status) === TaskStatus.RUNNING && (
            <Typography
              variant="body2"
              color="text.secondary"
              sx={{ pl: '4px', fontWeight: 600 }}
            >
              {Math.round(Math.min(Math.max(s.task.progress, 0), 100))}%{' '}
              {t('trading:detail.completed')}
            </Typography>
          )}
        </Box>
      </Paper>

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
              <Tab
                key={tab.id}
                label={tab.label}
                {...a11yProps(idx)}
                sx={{
                  minWidth: { xs: 'auto', sm: 90 },
                  px: { xs: 1, sm: 2 },
                  fontSize: { xs: '0.75rem', sm: '0.875rem' },
                }}
              />
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

        {visibleTabIds.includes('overview') && (
          <LazyTabPanel
            value={activeTabIndex}
            index={visibleTabIds.indexOf('overview')}
          >
            <Box sx={{ p: { xs: 1.5, sm: 3 } }}>
              <Grid container spacing={{ xs: 2, sm: 3 }}>
                <Grid size={{ xs: 12, md: 6 }}>
                  <Typography variant="h6" gutterBottom>
                    {t('trading:detail.taskInformation')}
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
                        {task.dry_run
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
          </LazyTabPanel>
        )}

        {visibleTabIds.includes('trend') && (
          <LazyTabPanel
            value={activeTabIndex}
            index={visibleTabIds.indexOf('trend')}
          >
            <TaskTrendPanel
              taskId={taskId}
              taskType={TaskType.TRADING}
              instrument={task.instrument}
              executionRunId={task.execution_id}
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
        {visibleTabIds.includes('positions') && (
          <LazyTabPanel
            value={activeTabIndex}
            index={visibleTabIds.indexOf('positions')}
          >
            <TaskPositionsTable
              taskId={taskId}
              taskType={TaskType.TRADING}
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
        {visibleTabIds.includes('trades') && (
          <LazyTabPanel
            value={activeTabIndex}
            index={visibleTabIds.indexOf('trades')}
          >
            <TaskTradesTable
              taskId={taskId}
              taskType={TaskType.TRADING}
              executionRunId={task.execution_id}
              enableRealTimeUpdates={
                (polledStatus?.status || task.status) === TaskStatus.RUNNING
              }
              pipSize={task.pip_size ? parseFloat(task.pip_size) : null}
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
              executionRunId={task.execution_id}
              enableRealTimeUpdates={
                (polledStatus?.status || task.status) === TaskStatus.RUNNING
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
              executionRunId={task.execution_id}
              enableRealTimeUpdates={
                (polledStatus?.status || task.status) === TaskStatus.RUNNING
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
