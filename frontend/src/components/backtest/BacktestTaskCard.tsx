import { useState, useEffect } from 'react';

import {
  Card,
  CardContent,
  Box,
  Typography,
  Chip,
  IconButton,
  Tooltip,
} from '@mui/material';
import Grid from '@mui/material/Grid';
import {
  Visibility as ViewIcon,
  MoreVert as MoreVertIcon,
} from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import type { BacktestTask } from '../../types/backtestTask';
import { TaskStatus } from '../../types/common';
import { StatusBadge } from '../tasks/display/StatusBadge';
import { TaskProgress } from '../tasks/TaskProgress';
import { StatCard } from '../tasks/display/StatCard';
import { TaskControlButtons } from '../common/TaskControlButtons';
import BacktestTaskActions from './BacktestTaskActions';
import { useTaskPolling } from '../../hooks/useTaskPolling';
import {
  useStrategies,
  getStrategyDisplayName,
} from '../../hooks/useStrategies';
import { useToast } from '../common';
import { backtestTasksApi } from '../../services/api';
import { invalidateBacktestTasksCache } from '../../hooks/useBacktestTasks';
import { TradingService } from '../../api/generated/services/TradingService';

interface BacktestTaskCardProps {
  task: BacktestTask;
  onRefresh?: () => void;
}

export default function BacktestTaskCard({
  task,
  onRefresh,
}: BacktestTaskCardProps) {
  const navigate = useNavigate();
  const { showError, showSuccess } = useToast();
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [optimisticStatus, setOptimisticStatus] = useState<TaskStatus | null>(
    null
  );
  const [isLoading, setIsLoading] = useState(false);

  // Fetch strategies for display names
  const { strategies } = useStrategies();

  // Poll for updates when task is running or optimistically set to running (Requirements 1.2, 4.5)
  const pollingEnabled =
    task.status === TaskStatus.RUNNING ||
    optimisticStatus === TaskStatus.RUNNING;

  const { status: polledStatus } = useTaskPolling(task.id, 'backtest', {
    enabled: pollingEnabled,
    pollStatus: true,
    interval: 5000, // Poll every 5 seconds for running tasks
  });

  // Use polled status if available, otherwise use task status
  const currentStatus = polledStatus?.status || task.status;

  // Clear optimistic status when actual status matches (derived state pattern)
  const displayStatus: TaskStatus =
    optimisticStatus && currentStatus !== optimisticStatus
      ? optimisticStatus
      : currentStatus;

  // Trigger refresh when polled status differs from task prop status
  // This ensures parent component gets updated data
  useEffect(() => {
    if (polledStatus && polledStatus.status !== task.status) {
      console.log('[BacktestTaskCard] Status changed via polling:', {
        taskId: task.id,
        propStatus: task.status,
        polledStatus: polledStatus.status,
      });
      // Clear optimistic status since we have real status now
      setOptimisticStatus(null);

      // Invalidate cache to force fresh data fetch
      invalidateBacktestTasksCache();

      // Notify parent to refetch task list
      onRefresh?.();
    }
  }, [polledStatus, task.status, task.id, onRefresh]);

  // Use original task data (polledStatus only provides status, not full task details)
  const currentTask = task;

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
    try {
      await backtestTasksApi.start(taskId);
      setOptimisticStatus(TaskStatus.RUNNING);
      showSuccess('Backtest task started successfully');
      onRefresh?.();
    } catch (error) {
      console.error('Failed to start task:', error);
      setOptimisticStatus(null);
      const errorMessage =
        error instanceof Error ? error.message : 'Failed to start task';
      showError(errorMessage, 8000, {
        label: 'Retry',
        onClick: () => handleStart(taskId),
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleStop = async (taskId: string) => {
    setIsLoading(true);
    try {
      await backtestTasksApi.stop(taskId);
      setOptimisticStatus(TaskStatus.STOPPED);
      showSuccess('Backtest task stopped successfully');
      onRefresh?.();
    } catch (error) {
      console.error('Failed to stop task:', error);
      setOptimisticStatus(null);
      const errorMessage =
        error instanceof Error ? error.message : 'Failed to stop task';
      showError(errorMessage);
    } finally {
      setIsLoading(false);
    }
  };

  const handleResume = async (taskId: string) => {
    setIsLoading(true);
    try {
      await backtestTasksApi.resume(taskId);
      setOptimisticStatus(TaskStatus.RUNNING);
      showSuccess('Backtest task resumed successfully');
      onRefresh?.();
    } catch (error) {
      console.error('Failed to resume task:', error);
      setOptimisticStatus(null);
      const errorMessage =
        error instanceof Error ? error.message : 'Failed to resume task';
      showError(errorMessage, 8000, {
        label: 'Retry',
        onClick: () => handleResume(taskId),
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleRestart = async (taskId: string) => {
    setIsLoading(true);
    try {
      await backtestTasksApi.restart(taskId);
      setOptimisticStatus(TaskStatus.RUNNING);
      showSuccess('Backtest task restarted successfully');
      onRefresh?.();
    } catch (error) {
      console.error('Failed to restart task:', error);
      setOptimisticStatus(null);
      const errorMessage =
        error instanceof Error ? error.message : 'Failed to restart task';
      showError(errorMessage, 8000, {
        label: 'Retry',
        onClick: () => handleRestart(taskId),
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleDelete = async (taskId: string) => {
    setIsLoading(true);
    try {
      await TradingService.tradingTasksBacktestDestroy(String(taskId));
      invalidateBacktestTasksCache();
      showSuccess('Backtest task deleted successfully');
      onRefresh?.();
    } catch (error) {
      console.error('Failed to delete task:', error);
      const errorMessage =
        error instanceof Error ? error.message : 'Failed to delete task';
      showError(errorMessage);
    } finally {
      setIsLoading(false);
    }
  };

  const formatDate = (dateString: string): string => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  };

  const formatDateTime = (dateString: string): string => {
    return new Date(dateString).toLocaleString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  // Get progress from polled status for running tasks
  const progress = polledStatus?.progress || 0;

  return (
    <Card
      sx={{
        '&:hover': {
          boxShadow: 4,
        },
        transition: 'box-shadow 0.3s',
      }}
    >
      <CardContent>
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
            <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', mb: 1 }}>
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
                  size="small"
                  variant="outlined"
                />
              )}
              {currentTask.config_name && (
                <Chip
                  label={currentTask.config_name}
                  size="small"
                  variant="outlined"
                  color="primary"
                />
              )}
            </Box>
            <Typography variant="body2" color="text.secondary">
              {formatDate(currentTask.start_time)} to{' '}
              {formatDate(currentTask.end_time)}
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
            <Tooltip title="View Details">
              <IconButton color="primary" onClick={handleView} size="small">
                <ViewIcon />
              </IconButton>
            </Tooltip>
            <IconButton onClick={handleActionsClick} size="small">
              <MoreVertIcon />
            </IconButton>
          </Box>
        </Box>

        {/* Action buttons using TaskControlButtons component */}
        <Box sx={{ mb: 2 }}>
          <TaskControlButtons
            taskId={task.id}
            status={displayStatus}
            onStart={handleStart}
            onStop={handleStop}
            onResume={handleResume}
            onRestart={handleRestart}
            onDelete={handleDelete}
            isLoading={isLoading}
            size="small"
            showLabels={true}
          />
        </Box>

        {/* Progress bar for running tasks using TaskProgress component in compact mode (Requirement 3.2) */}
        {displayStatus === TaskStatus.RUNNING && (
          <Box sx={{ mb: 2 }}>
            <TaskProgress
              status={displayStatus}
              progress={progress}
              compact={true}
              showPercentage={true}
            />
          </Box>
        )}

        {/* Stats for completed tasks */}
        {displayStatus === TaskStatus.COMPLETED &&
          currentTask.latest_execution && (
            <Grid container spacing={2} sx={{ mt: 1 }}>
              {currentTask.latest_execution.total_return && (
                <Grid size={{ xs: 6, sm: 3 }}>
                  <StatCard
                    title="Total Return"
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
                    title="Win Rate"
                    value={`${currentTask.latest_execution.win_rate}%`}
                  />
                </Grid>
              )}
              {currentTask.latest_execution.total_trades !== undefined && (
                <Grid size={{ xs: 6, sm: 3 }}>
                  <StatCard
                    title="Total Trades"
                    value={currentTask.latest_execution.total_trades.toString()}
                  />
                </Grid>
              )}
            </Grid>
          )}

        {/* Error message for failed tasks */}
        {displayStatus === TaskStatus.FAILED && (
          <Box
            sx={{
              mt: 2,
              p: 2,
              bgcolor: 'error.light',
              borderRadius: 1,
            }}
          >
            <Typography variant="body2" color="error.dark" fontWeight="bold">
              Task execution failed
            </Typography>
            {currentTask.latest_execution?.error_message && (
              <Typography variant="body2" color="error.dark" sx={{ mt: 1 }}>
                {currentTask.latest_execution.error_message}
              </Typography>
            )}
          </Box>
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
          <Typography variant="caption" color="text.secondary">
            Created: {formatDateTime(currentTask.created_at)}
          </Typography>
          {displayStatus === TaskStatus.COMPLETED && (
            <Typography variant="caption" color="text.secondary">
              Completed: {formatDateTime(currentTask.updated_at)}
            </Typography>
          )}
        </Box>
      </CardContent>

      <BacktestTaskActions
        task={currentTask}
        anchorEl={anchorEl}
        onClose={handleActionsClose}
        onRefresh={onRefresh}
      />
    </Card>
  );
}
