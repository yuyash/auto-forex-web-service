import { useState, useEffect, useRef } from 'react';
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
} from '@mui/material';
import { useTheme } from '@mui/material/styles';
import Grid from '@mui/material/Grid';
import {
  Visibility as ViewIcon,
  MoreVert as MoreVertIcon,
  Warning as WarningIcon,
} from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import {
  shouldEnableRealtimeTaskUpdates,
  shouldPollTaskStatus,
} from '../../hooks/taskResourceQueries';
import { useTaskSummary } from '../../hooks/useTaskSummary';
import type { TradingTask } from '../../types/tradingTask';
import { TaskStatus, TaskType } from '../../types/common';
import { StatusBadge } from '../tasks/display/StatusBadge';
import { TaskControlButtons } from '../common/TaskControlButtons';
import TradingTaskActions from './TradingTaskActions';
import { DeleteTaskDialog } from '../tasks/actions/DeleteTaskDialog';
import { TaskActionConfirmDialog } from '../tasks/actions/TaskActionConfirmDialog';
import { useToast } from '../common';
import { useTaskActionDialog } from '../../hooks/useTaskActionDialog';
import { useTradingTask } from '../../hooks/useTradingTasks';
import {
  useStrategies,
  getStrategyDisplayName,
} from '../../hooks/useStrategies';
import { useAuth } from '../../contexts/AuthContext';
import {
  useDeleteTradingTask,
  useRestartTradingTask,
  useResumeTradingTask,
  useStartTradingTask,
  useStopTradingTask,
} from '../../hooks/useTradingTaskMutations';
import { useAppSettings } from '../../hooks/useAppSettings';
import { logger } from '../../utils/logger';
import { formatAppNumber, currencySymbol } from '../../utils/numberFormat';
import { formatTaskActionError } from '../../utils/taskActionError';
import { formatDateTimeInTimezone } from '../../utils/timezone';

interface TradingTaskCardProps {
  task: TradingTask;
  onRefresh?: () => void;
}

export default function TradingTaskCard({
  task,
  onRefresh,
}: TradingTaskCardProps) {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
  const { settings: appSettings } = useAppSettings();
  const activePollingIntervalMs = Math.min(
    appSettings.healthCheckIntervalSeconds * 1000,
    2_000
  );
  const [optimisticStatus, setOptimisticStatus] = useState<TaskStatus | null>(
    null
  );
  const [isLoading, setIsLoading] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const { pendingAction, requestConfirm, cancelAction } = useTaskActionDialog();
  const prevTaskRef = useRef<TradingTask>(task);
  const startTask = useStartTradingTask();
  const stopTask = useStopTradingTask();
  const resumeTask = useResumeTradingTask();
  const restartTask = useRestartTradingTask();
  const deleteTask = useDeleteTradingTask();

  const { t } = useTranslation(['trading', 'common']);
  const { showError, showSuccess, showWarning, showInfo } = useToast();
  const timezone = user?.timezone || 'UTC';
  const language = user?.language;

  // Fetch strategies for display names
  const { strategies } = useStrategies();

  // Poll for updates when task is running or paused (more frequent for live trading) (Requirements 1.2, 4.5)
  const pollingEnabled =
    shouldPollTaskStatus(task.status) ||
    shouldPollTaskStatus(optimisticStatus ?? undefined) ||
    shouldEnableRealtimeTaskUpdates(task.status) ||
    shouldEnableRealtimeTaskUpdates(optimisticStatus ?? undefined);

  const { data: polledTask } = useTradingTask(task.id, {
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

  // Use original task data (polledStatus only provides status, not full task details)
  const currentTask = polledTask || task;
  const shouldShowPnlSnapshot = displayStatus !== TaskStatus.CREATED;
  const { summary: taskSummary } = useTaskSummary(
    shouldShowPnlSnapshot ? task.id : '',
    TaskType.TRADING,
    undefined,
    {
      polling: shouldShowPnlSnapshot && pollingEnabled,
      interval: activePollingIntervalMs,
    }
  );

  // Trigger refresh when polled status differs from task prop status
  // This ensures parent component gets updated data
  useEffect(() => {
    if (polledTask && polledTask.status !== task.status) {
      logger.debug('Trading task status changed via polling', {
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

  // Show toast notifications for status changes and trades
  useEffect(() => {
    const prevTask = prevTaskRef.current;

    // Status change notifications - use displayStatus for accurate current state
    if (prevTask.status !== displayStatus) {
      switch (displayStatus) {
        case TaskStatus.RUNNING:
          showSuccess(`Task "${currentTask.name}" is now running`);
          break;
        case TaskStatus.PAUSED:
          showWarning(`Task "${currentTask.name}" has been paused`);
          break;
        case TaskStatus.STOPPED:
          showInfo(`Task "${currentTask.name}" has been stopped`);
          break;
        case TaskStatus.FAILED:
          showError(`Task "${currentTask.name}" has failed`);
          break;
      }
      // Update prevTask status to reflect the new status
      prevTaskRef.current = { ...prevTask, status: displayStatus };
    }

    // Trade notifications (check if total trades increased)
    if (
      currentTask.latest_execution?.total_trades &&
      prevTask.latest_execution?.total_trades &&
      currentTask.latest_execution.total_trades >
        prevTask.latest_execution.total_trades
    ) {
      const newTrades =
        currentTask.latest_execution.total_trades -
        prevTask.latest_execution.total_trades;
      showInfo(
        `${newTrades} new trade${newTrades > 1 ? 's' : ''} executed on "${currentTask.name}"`
      );
    }

    prevTaskRef.current = currentTask;
  }, [
    currentTask,
    displayStatus,
    showSuccess,
    showWarning,
    showInfo,
    showError,
  ]);

  const handleActionsClick = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleActionsClose = () => {
    setAnchorEl(null);
  };

  const handleView = () => {
    navigate(`/trading-tasks/${task.id}`);
  };

  const handleStart = async (taskId: string | number) => {
    setIsLoading(true);
    setOptimisticStatus(TaskStatus.STARTING);
    try {
      await startTask.mutate(String(taskId));
      setOptimisticStatus(null);
      showSuccess(t('trading:toast.startedSuccessfully'));
      onRefresh?.();
    } catch (error) {
      logger.error('Failed to start trading task', {
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

  const handleStop = async (taskId: string | number) => {
    setIsLoading(true);
    setOptimisticStatus(TaskStatus.STOPPING);
    try {
      await stopTask.mutate({ id: String(taskId) });
      setOptimisticStatus(null);
      showSuccess(t('trading:toast.stoppedSuccessfully'));
      onRefresh?.();
    } catch (error) {
      logger.error('Failed to stop trading task', {
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

  const handleResume = async (taskId: string | number) => {
    setIsLoading(true);
    setOptimisticStatus(TaskStatus.STARTING);
    try {
      await resumeTask.mutate(String(taskId));
      setOptimisticStatus(null);
      showSuccess(t('trading:toast.resumedSuccessfully'));
      onRefresh?.();
    } catch (error) {
      logger.error('Failed to resume trading task', {
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

  const handleRestart = async (taskId: string | number) => {
    setIsLoading(true);
    setOptimisticStatus(TaskStatus.STARTING);
    try {
      await restartTask.mutate(String(taskId));
      setOptimisticStatus(null);
      showSuccess(t('trading:toast.restartedSuccessfully'));
      onRefresh?.();
    } catch (error) {
      logger.error('Failed to restart trading task', {
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
      showSuccess(t('trading:toast.deletedSuccessfully'));
      setDeleteDialogOpen(false);
      onRefresh?.();
    } catch (error) {
      logger.error('Failed to delete trading task', {
        taskId: task.id,
        error: error instanceof Error ? error.message : String(error),
      });
      const errorMessage = formatTaskActionError(
        error,
        'Failed to delete task'
      );
      showError(errorMessage);
    } finally {
      setIsDeleting(false);
    }
  };

  const formatDateTime = (dateString: string): string => {
    return formatDateTimeInTimezone(dateString, timezone, language, {
      includeTimezone: true,
    });
  };

  const quoteCurrency = currencySymbol(
    currentTask.instrument.split('_').at(-1) ||
      currentTask.latest_execution?.quote_currency ||
      taskSummary.execution.displayCurrency ||
      'JPY'
  );
  const formatPnl = (value: number): string => {
    return `${formatAppNumber(value, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
      signed: true,
    })}${quoteCurrency ? ` ${quoteCurrency}` : ''}`;
  };

  const realizedPnl = taskSummary.pnl.realized;
  const unrealizedPnl = taskSummary.pnl.unrealized;
  const totalPnl = realizedPnl + unrealizedPnl;
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

  return (
    <Card
      sx={{
        '&:hover': {
          boxShadow: 4,
        },
        transition: 'box-shadow 0.3s',
        border:
          displayStatus === TaskStatus.RUNNING ? '2px solid' : '1px solid',
        borderColor:
          displayStatus === TaskStatus.RUNNING ? 'success.main' : 'divider',
      }}
    >
      <CardContent sx={{ px: { xs: 1.5, sm: 2 }, py: { xs: 1.5, sm: 2 } }}>
        {/* Risk Warning for Live Trading */}
        {displayStatus === TaskStatus.RUNNING &&
          currentTask.account_type === 'live' && (
            <Alert severity="warning" icon={<WarningIcon />} sx={{ mb: 2 }}>
              <Typography variant="caption">
                <strong>{t('trading:warnings.liveTrading')}</strong>
              </Typography>
            </Alert>
          )}

        <Box
          sx={{
            display: 'flex',
            justifyContent: 'space-between',
            mb: 2,
            gap: 1,
          }}
        >
          <Box
            sx={{ flex: 1, minWidth: 0, cursor: 'pointer' }}
            onClick={handleView}
          >
            <Typography variant="h6" component="h2" sx={{ mb: 1.5 }}>
              {currentTask.name}
            </Typography>
            <Box
              sx={{
                display: 'flex',
                gap: 1,
                alignItems: 'center',
                mb: 1,
                flexWrap: 'wrap',
              }}
            >
              <StatusBadge status={displayStatus} />
              {currentTask.account_type === 'live' && (
                <Chip
                  label={t('common:labels.liveAccount')}
                  color="error"
                  size="small"
                  sx={{ fontWeight: 'bold' }}
                />
              )}
              <Chip
                label={getStrategyDisplayName(
                  strategies,
                  currentTask.strategy_type
                )}
                variant="outlined"
                size="small"
              />
              {!isMobile && (
                <Chip
                  label={currentTask.config_name}
                  variant="outlined"
                  color="primary"
                  size="small"
                />
              )}
              <Chip
                label={currentTask.account_name}
                variant="outlined"
                color="secondary"
                size="small"
              />
            </Box>
            {currentTask.description && (
              <Typography variant="body2" color="text.secondary">
                {currentTask.description}
              </Typography>
            )}
          </Box>

          <Box
            sx={{
              display: 'flex',
              gap: 0.5,
              alignItems: 'flex-start',
              flexShrink: 0,
            }}
          >
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
        <Box sx={{ mb: 2 }}>
          <TaskControlButtons
            taskId={task.id}
            status={displayStatus}
            taskType="trading"
            onStart={(id) => requestConfirm('start', String(id))}
            onStop={(id) => requestConfirm('stop', String(id))}
            onResume={(id) => requestConfirm('resume', String(id))}
            onRestart={(id) => requestConfirm('restart', String(id))}
            onDelete={handleDelete}
            isLoading={isLoading}
            showLabels={!isMobile}
            size={isMobile ? 'medium' : 'small'}
          />
        </Box>

        {shouldShowPnlSnapshot && (
          <Grid container spacing={1} sx={{ mt: 1, mb: 1.5 }}>
            {pnlItems.map((item) => (
              <Grid key={item.key} size={{ xs: 12, sm: 4 }}>
                <Box
                  sx={{
                    height: '100%',
                    minHeight: 64,
                    p: 1,
                    border: 1,
                    borderColor: 'divider',
                    borderRadius: 1,
                    bgcolor: 'action.hover',
                    display: 'flex',
                    flexDirection: 'column',
                    justifyContent: 'space-between',
                    gap: 1,
                  }}
                >
                  <Typography
                    variant="caption"
                    color="text.secondary"
                    sx={{ fontWeight: 600 }}
                  >
                    {item.label}
                  </Typography>
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
                    {formatPnl(item.value)}
                  </Typography>
                </Box>
              </Grid>
            ))}
          </Grid>
        )}

        {/* Error message for failed tasks */}
        {displayStatus === TaskStatus.FAILED && (
          <Alert severity="error" sx={{ mt: 2 }}>
            <Typography variant="body2" fontWeight="bold">
              {t('trading:card.taskExecutionFailed')}
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
            mt: 2,
            pt: 2,
            borderTop: 1,
            borderColor: 'divider',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <Box>
            <Typography variant="caption" color="text.secondary">
              {t('common:labels.created')}:{' '}
              {formatDateTime(currentTask.created_at)}
            </Typography>
            {currentTask.updated_at && (
              <Typography
                variant="caption"
                color="text.secondary"
                sx={{ display: 'block' }}
              >
                {t('common:labels.lastRun')}:{' '}
                {formatDateTime(currentTask.updated_at)}
              </Typography>
            )}
          </Box>
          {displayStatus === TaskStatus.RUNNING && (
            <Chip label="LIVE" color="success" sx={{ fontWeight: 'bold' }} />
          )}
        </Box>
      </CardContent>

      <TradingTaskActions
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
            else if (type === 'stop') void handleStop(taskId);
            else if (type === 'resume') void handleResume(taskId);
            else if (type === 'restart') void handleRestart(taskId);
          }}
        />
      )}
    </Card>
  );
}
