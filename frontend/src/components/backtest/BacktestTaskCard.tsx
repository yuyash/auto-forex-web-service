import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';

import {
  Card,
  CardContent,
  Box,
  Typography,
  Chip,
  IconButton,
  Tooltip,
  Alert,
  useMediaQuery,
  Checkbox,
} from '@mui/material';
import { useTheme } from '@mui/material/styles';
import Grid from '@mui/material/Grid';
import {
  Visibility as ViewIcon,
  MoreVert as MoreVertIcon,
} from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import {
  shouldEnableRealtimeTaskUpdates,
  shouldPollTaskStatus,
} from '../../hooks/taskResourceQueries';
import type { BacktestTask } from '../../types/backtestTask';
import { TaskStatus, TaskType } from '../../types/common';
import { StatusBadge } from '../tasks/display/StatusBadge';
import { TaskProgress } from '../tasks/TaskProgress';
import { StatCard } from '../tasks/display/StatCard';
import { TaskControlButtons } from '../common/TaskControlButtons';
import BacktestTaskActions from './BacktestTaskActions';
import { DeleteTaskDialog } from '../tasks/actions/DeleteTaskDialog';
import {
  StopOptionsDialog,
  type StopOption,
} from '../tasks/actions/StopOptionsDialog';
import { TaskActionConfirmDialog } from '../tasks/actions/TaskActionConfirmDialog';
import { useTaskActionDialog } from '../../hooks/useTaskActionDialog';
import { useBacktestTask } from '../../hooks/useBacktestTasks';
import { useTaskSummary } from '../../hooks/useTaskSummary';
import {
  useStrategies,
  getStrategyDisplayName,
} from '../../hooks/useStrategies';
import {
  useDeleteBacktestTask,
  usePauseBacktestTask,
  useResumeBacktestTask,
  useRerunBacktestTask,
  useStartBacktestTask,
  useStopBacktestTask,
} from '../../hooks/useBacktestTaskMutations';
import { useToast } from '../common';
import { useAppSettings } from '../../hooks/useAppSettings';
import { logger } from '../../utils/logger';
import { formatTaskActionError } from '../../utils/taskActionError';
import { formatDateTimeInTimezone } from '../../utils/timezone';
import {
  formatMoneyAmount,
  formatMoneyPayload,
} from '../../utils/numberFormat';
import { quoteCurrencyFromInstrument } from '../../utils/instrumentCurrency';
import { formatCurrencyConversionContext } from '../../utils/currencyConversion';
import { useAuth } from '../../contexts/AuthContext';

interface BacktestTaskCardProps {
  task: BacktestTask;
  onRefresh?: () => void;
  selected?: boolean;
  onSelectedChange?: (id: string, selected: boolean) => void;
}

export default function BacktestTaskCard({
  task,
  onRefresh,
  selected = false,
  onSelectedChange,
}: BacktestTaskCardProps) {
  const { t, i18n } = useTranslation(['backtest', 'common']);
  const navigate = useNavigate();
  const { showError, showSuccess } = useToast();
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
  const { settings: appSettings } = useAppSettings();
  const activePollingIntervalMs = Math.min(
    appSettings.healthCheckIntervalSeconds * 1000,
    2_000
  );
  const { user } = useAuth();
  const timezone = user?.timezone || 'UTC';
  const language = i18n?.resolvedLanguage;
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [optimisticStatus, setOptimisticStatus] = useState<TaskStatus | null>(
    null
  );
  const [isLoading, setIsLoading] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [stopDialogOpen, setStopDialogOpen] = useState(false);
  const { pendingAction, requestConfirm, cancelAction } = useTaskActionDialog();
  const startTask = useStartBacktestTask();
  const stopTask = useStopBacktestTask();
  const resumeTask = useResumeBacktestTask();
  const pauseTask = usePauseBacktestTask();
  const restartTask = useRerunBacktestTask();
  const deleteTask = useDeleteBacktestTask();

  // Fetch strategies for display names
  const { strategies } = useStrategies();

  // Poll for updates when task is running or optimistically set to running (Requirements 1.2, 4.5)
  const pollingEnabled =
    shouldPollTaskStatus(task.status) ||
    shouldPollTaskStatus(optimisticStatus ?? undefined) ||
    shouldEnableRealtimeTaskUpdates(task.status) ||
    shouldEnableRealtimeTaskUpdates(optimisticStatus ?? undefined);

  const { data: polledTask } = useBacktestTask(task.id, {
    enabled: pollingEnabled,
    enablePolling: pollingEnabled,
    pollingInterval: activePollingIntervalMs,
  });

  // Use polled status if available, otherwise use task status
  const currentStatus = polledTask?.status || task.status;

  // Clear optimistic status when actual status matches (derived state pattern)
  const displayStatus: TaskStatus =
    optimisticStatus && currentStatus !== optimisticStatus
      ? optimisticStatus
      : currentStatus;

  // Trigger refresh when polled status differs from task prop status
  // This ensures parent component gets updated data
  useEffect(() => {
    if (polledTask && polledTask.status !== task.status) {
      logger.debug('Backtest task status changed via polling', {
        taskId: task.id,
        propStatus: task.status,
        polledStatus: polledTask.status,
      });
      // Clear optimistic status since we have real status now
      setOptimisticStatus(null);

      // Notify parent to refetch task list
      onRefresh?.();
    }
  }, [polledTask, task.status, task.id, onRefresh]);

  // Use original task data (polledStatus only provides status, not full task details)
  const currentTask = polledTask || task;

  const handleActionsClick = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleActionsClose = () => {
    setAnchorEl(null);
  };

  const handleView = () => {
    navigate(`/backtest-tasks/${task.id}`);
  };

  const handleStart = async (taskId: string) => {
    setIsLoading(true);
    setOptimisticStatus(TaskStatus.STARTING);
    try {
      await startTask.mutate(taskId);
      setOptimisticStatus(null);
      showSuccess(t('backtest:toast.startedSuccessfully'));
      onRefresh?.();
    } catch (error) {
      logger.error('Failed to start backtest task', {
        taskId,
        error: error instanceof Error ? error.message : String(error),
      });
      setOptimisticStatus(null);
      const errorMessage = formatTaskActionError(error, 'Failed to start task');
      showError(errorMessage, 8000, {
        label: 'Retry',
        onClick: () => handleStart(taskId),
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleStop = async (
    taskId: string,
    mode: StopOption = 'graceful',
    drainDurationMinutes?: number
  ) => {
    setStopDialogOpen(false);
    setIsLoading(true);
    setOptimisticStatus(
      mode === 'drain' ? TaskStatus.DRAINING : TaskStatus.STOPPING
    );
    try {
      await stopTask.mutate({
        id: taskId,
        mode,
        ...(drainDurationMinutes !== undefined ? { drainDurationMinutes } : {}),
      });
      setOptimisticStatus(null);
      showSuccess(t('backtest:toast.stoppedSuccessfully'));
      onRefresh?.();
    } catch (error) {
      logger.error('Failed to stop backtest task', {
        taskId,
        error: error instanceof Error ? error.message : String(error),
      });
      setOptimisticStatus(null);
      const errorMessage = formatTaskActionError(error, 'Failed to stop task');
      showError(errorMessage);
    } finally {
      setIsLoading(false);
    }
  };

  const handleStopRequest = async () => {
    if (isLoading) {
      return;
    }
    setStopDialogOpen(true);
  };

  const handleResume = async (taskId: string) => {
    setIsLoading(true);
    setOptimisticStatus(TaskStatus.STARTING);
    try {
      await resumeTask.mutate(taskId);
      setOptimisticStatus(null);
      showSuccess(t('backtest:toast.resumedSuccessfully'));
      onRefresh?.();
    } catch (error) {
      logger.error('Failed to resume backtest task', {
        taskId,
        error: error instanceof Error ? error.message : String(error),
      });
      setOptimisticStatus(null);
      const errorMessage = formatTaskActionError(
        error,
        'Failed to resume task'
      );
      showError(errorMessage, 8000, {
        label: 'Retry',
        onClick: () => handleResume(taskId),
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handlePause = async (taskId: string) => {
    setIsLoading(true);
    setOptimisticStatus(TaskStatus.PAUSED);
    try {
      await pauseTask.mutate(taskId);
      setOptimisticStatus(null);
      showSuccess(t('backtest:toast.pausedSuccessfully'));
      onRefresh?.();
    } catch (error) {
      logger.error('Failed to pause backtest task', {
        taskId,
        error: error instanceof Error ? error.message : String(error),
      });
      setOptimisticStatus(null);
      const errorMessage = formatTaskActionError(error, 'Failed to pause task');
      showError(errorMessage, 8000, {
        label: 'Retry',
        onClick: () => handlePause(taskId),
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleRestart = async (taskId: string) => {
    setIsLoading(true);
    setOptimisticStatus(TaskStatus.STARTING);
    try {
      await restartTask.mutate(taskId);
      setOptimisticStatus(null);
      showSuccess(t('backtest:toast.restartedSuccessfully'));
      onRefresh?.();
    } catch (error) {
      logger.error('Failed to restart backtest task', {
        taskId,
        error: error instanceof Error ? error.message : String(error),
      });
      setOptimisticStatus(null);
      const errorMessage = formatTaskActionError(
        error,
        'Failed to restart task'
      );
      showError(errorMessage, 8000, {
        label: 'Retry',
        onClick: () => handleRestart(taskId),
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleDelete = async () => {
    setDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = async () => {
    setIsDeleting(true);
    try {
      await deleteTask.mutate(String(task.id));
      showSuccess(t('backtest:toast.deletedSuccessfully'));
      setDeleteDialogOpen(false);
      onRefresh?.();
    } catch (error) {
      logger.error('Failed to delete backtest task', {
        taskId: task.id,
        error: error instanceof Error ? error.message : String(error),
      });
      const errorMessage =
        error instanceof Error ? error.message : 'Failed to delete task';
      showError(errorMessage);
    } finally {
      setIsDeleting(false);
    }
  };

  const formatPeriod = (dateString: string): string =>
    formatDateTimeInTimezone(dateString, timezone, language, {
      includeTimezone: true,
    });

  const formatTs = (dateString: string): string =>
    formatDateTimeInTimezone(dateString, timezone, language, {
      includeTimezone: true,
    });

  // Get progress from summary endpoint
  const summaryData = useTaskSummary(task.id, TaskType.BACKTEST, undefined, {
    polling: pollingEnabled,
    interval: activePollingIntervalMs,
  });
  const { summary } = summaryData;
  const progress = summary.task.progress;
  const pnlCurrency =
    summary.pnl.currency ||
    quoteCurrencyFromInstrument(currentTask.instrument) ||
    currentTask.display_currency ||
    summary.execution.accountCurrency ||
    currentTask.account_currency ||
    '';
  const realizedPnl = summary.pnl.realized;
  const unrealizedPnl = summary.pnl.unrealized;
  const totalPnl = realizedPnl + unrealizedPnl;
  const pnlDisplayMoney = {
    total: summary.pnl.totalDisplayMoney,
    realized: summary.pnl.realizedDisplayMoney,
    unrealized: summary.pnl.unrealizedDisplayMoney,
  };
  const pnlConversionTooltip = formatCurrencyConversionContext(
    summary.pnl.displayConversionContext,
    { language, separators: appSettings, t, timezone }
  );
  const formatPnl = (
    value: number,
    money?: { amount: string; currency: string } | null
  ): string =>
    money
      ? formatMoneyPayload(money, {
          signed: true,
        })
      : formatMoneyAmount(value, pnlCurrency, {
          signed: true,
        });
  const pnlItems = [
    {
      key: 'total',
      label: t('common:metrics.total_pnl'),
      value: totalPnl,
    },
    {
      key: 'realized',
      label: t('common:metrics.realized_pnl'),
      value: realizedPnl,
    },
    {
      key: 'unrealized',
      label: t('common:metrics.unrealized_pnl'),
      value: unrealizedPnl,
    },
  ];
  const shouldShowPnlSnapshot = displayStatus !== TaskStatus.CREATED;

  return (
    <Card
      sx={{
        '&:hover': {
          boxShadow: 4,
        },
        transition: 'box-shadow 0.3s',
        border: '1px solid',
        borderColor: 'divider',
        outline: selected ? '2px solid' : '2px solid transparent',
        outlineColor: selected ? 'primary.main' : 'transparent',
        outlineOffset: 2,
      }}
    >
      <CardContent
        sx={{
          p: { xs: 1, sm: 1.25 },
          '&:last-child': { pb: { xs: 1, sm: 1.25 } },
        }}
      >
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'space-between',
            mb: 0.75,
            gap: 1,
          }}
        >
          <Box
            sx={{ flex: 1, minWidth: 0, cursor: 'pointer' }}
            onClick={handleView}
          >
            <Typography
              variant="subtitle1"
              component="h2"
              sx={{ mb: 0.5, fontWeight: 600, lineHeight: 1.25 }}
            >
              {currentTask.name}
            </Typography>
            <Box
              sx={{
                display: 'flex',
                gap: 0.5,
                alignItems: 'center',
                mb: 0.5,
                flexWrap: 'wrap',
              }}
            >
              <StatusBadge status={displayStatus} />
              {getStrategyDisplayName(
                strategies,
                currentTask.strategy_type
              ) && (
                <Chip
                  label={getStrategyDisplayName(
                    strategies,
                    currentTask.strategy_type
                  )}
                  variant="outlined"
                  size="small"
                />
              )}
              {!isMobile && currentTask.config_name && (
                <Chip
                  label={currentTask.config_name}
                  variant="outlined"
                  color="primary"
                  size="small"
                />
              )}
            </Box>
            <Typography variant="caption" color="text.secondary">
              {formatPeriod(currentTask.start_time)} -{' '}
              {formatPeriod(currentTask.end_time)}
            </Typography>
          </Box>

          <Box
            sx={{
              display: 'flex',
              gap: 0.5,
              alignItems: 'flex-start',
              flexShrink: 0,
            }}
          >
            {onSelectedChange && (
              <Tooltip
                title={t('common:actions.selectForCompare', {
                  defaultValue: 'Select for comparison',
                })}
              >
                <Checkbox
                  checked={selected}
                  onChange={(event) => {
                    event.stopPropagation();
                    onSelectedChange(task.id, event.target.checked);
                  }}
                  onClick={(event) => event.stopPropagation()}
                  inputProps={{
                    'aria-label': t('common:actions.selectForCompare', {
                      defaultValue: 'Select for comparison',
                    }),
                  }}
                  size="small"
                  sx={{ p: 0.5 }}
                />
              </Tooltip>
            )}
            <Tooltip title={t('common:actions.viewDetails')}>
              <IconButton color="primary" onClick={handleView}>
                <ViewIcon />
              </IconButton>
            </Tooltip>
            <IconButton onClick={handleActionsClick}>
              <MoreVertIcon />
            </IconButton>
          </Box>
        </Box>

        {/* Action buttons using TaskControlButtons component */}
        <Box sx={{ mb: 0.75 }}>
          <TaskControlButtons
            taskId={task.id}
            status={displayStatus}
            taskType="backtest"
            onStart={(id) => requestConfirm('start', id)}
            onStop={handleStopRequest}
            onPause={(id) => requestConfirm('pause', id)}
            onResume={(id) => requestConfirm('resume', id)}
            onRestart={(id) => requestConfirm('restart', id)}
            onDelete={handleDelete}
            isLoading={isLoading}
            showLabels={!isMobile}
            size={isMobile ? 'medium' : 'small'}
          />
        </Box>

        {/* Progress bar for running tasks using TaskProgress component in compact mode (Requirement 3.2) */}
        {displayStatus === TaskStatus.RUNNING && (
          <Box sx={{ mb: 0.75 }}>
            <TaskProgress
              status={displayStatus}
              progress={progress}
              compact={true}
              showPercentage={true}
            />
          </Box>
        )}

        {shouldShowPnlSnapshot && (
          <Grid container spacing={0.75} sx={{ mt: 0.75, mb: 0.75 }}>
            {pnlItems.map((item) => (
              <Grid key={item.key} size={{ xs: 12, sm: 4 }}>
                <Box
                  sx={{
                    height: '100%',
                    minHeight: 50,
                    p: 0.75,
                    border: 1,
                    borderColor: 'divider',
                    borderRadius: 1,
                    bgcolor: 'action.hover',
                    display: 'flex',
                    flexDirection: 'column',
                    justifyContent: 'space-between',
                    gap: 0.25,
                  }}
                >
                  <Typography
                    variant="caption"
                    color="text.secondary"
                    sx={{ fontWeight: 600 }}
                  >
                    {item.label}
                  </Typography>
                  <Tooltip
                    title={pnlConversionTooltip}
                    arrow
                    disableHoverListener={!pnlConversionTooltip}
                  >
                    <Typography
                      variant="body1"
                      component="div"
                      color={item.value >= 0 ? 'success.main' : 'error.main'}
                      sx={{
                        fontWeight: 700,
                        lineHeight: 1.25,
                        overflowWrap: 'anywhere',
                      }}
                    >
                      {formatPnl(
                        item.value,
                        pnlDisplayMoney[
                          item.key as keyof typeof pnlDisplayMoney
                        ]
                      )}
                    </Typography>
                  </Tooltip>
                </Box>
              </Grid>
            ))}
          </Grid>
        )}

        {/* Stats for completed tasks */}
        {displayStatus === TaskStatus.COMPLETED &&
          currentTask.latest_execution && (
            <Grid container spacing={1} sx={{ mt: 0.75 }}>
              {currentTask.latest_execution.total_return && (
                <Grid size={{ xs: 6, sm: 3 }}>
                  <StatCard
                    title={t('backtest:results.totalReturn')}
                    value={`${currentTask.latest_execution.total_return}%`}
                    color={
                      parseFloat(currentTask.latest_execution.total_return) >= 0
                        ? 'success'
                        : 'error'
                    }
                  />
                </Grid>
              )}
              {currentTask.latest_execution.win_rate && (
                <Grid size={{ xs: 6, sm: 3 }}>
                  <StatCard
                    title={t('backtest:results.winRate')}
                    value={`${currentTask.latest_execution.win_rate}%`}
                  />
                </Grid>
              )}
              {currentTask.latest_execution.total_trades !== undefined && (
                <Grid size={{ xs: 6, sm: 3 }}>
                  <StatCard
                    title={t('backtest:results.totalTrades')}
                    value={currentTask.latest_execution.total_trades.toString()}
                  />
                </Grid>
              )}
            </Grid>
          )}

        {/* Error message for failed tasks */}
        {displayStatus === TaskStatus.FAILED && (
          <Alert severity="error" sx={{ mt: 1 }}>
            <Typography variant="body2" fontWeight="bold">
              {t('backtest:card.taskExecutionFailed')}
            </Typography>
            {currentTask.latest_execution?.error_message && (
              <Typography variant="body2" sx={{ mt: 0.5 }}>
                {currentTask.latest_execution.error_message}
              </Typography>
            )}
          </Alert>
        )}

        {/* Footer with metadata */}
        <Box
          sx={{
            mt: 1,
            pt: 1,
            borderTop: 1,
            borderColor: 'divider',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <Box>
            <Typography variant="caption" color="text.secondary">
              {t('common:labels.created')}: {formatTs(currentTask.created_at)}
            </Typography>
            {currentTask.updated_at && (
              <Typography
                variant="caption"
                color="text.secondary"
                sx={{ display: 'block' }}
              >
                {t('common:labels.lastRun')}: {formatTs(currentTask.updated_at)}
              </Typography>
            )}
          </Box>
        </Box>
      </CardContent>

      <BacktestTaskActions
        task={currentTask}
        anchorEl={anchorEl}
        onClose={handleActionsClose}
        onRefresh={onRefresh}
      />

      <DeleteTaskDialog
        open={deleteDialogOpen}
        taskName={task.name}
        taskStatus={task.status}
        onCancel={() => setDeleteDialogOpen(false)}
        onConfirm={handleDeleteConfirm}
        isLoading={isDeleting}
        hasExecutionHistory={true}
      />
      <StopOptionsDialog
        open={stopDialogOpen}
        taskName={task.name}
        taskType="backtest"
        isLoading={isLoading}
        onCancel={() => setStopDialogOpen(false)}
        onConfirm={({ option, drainDurationMinutes }) =>
          void handleStop(task.id, option, drainDurationMinutes)
        }
      />
      {pendingAction && (
        <TaskActionConfirmDialog
          open={true}
          action={pendingAction.type}
          taskName={task.name}
          isLoading={isLoading}
          onCancel={cancelAction}
          onConfirm={() => {
            const { type, taskId } = pendingAction;
            cancelAction();
            if (type === 'start') void handleStart(taskId);
            else if (type === 'pause') void handlePause(taskId);
            else if (type === 'resume') void handleResume(taskId);
            else if (type === 'restart') void handleRestart(taskId);
          }}
        />
      )}
    </Card>
  );
}
