import { useState } from 'react';

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
import { TaskProgressBar } from '../tasks/display/TaskProgressBar';
import { MetricCard } from '../tasks/display/MetricCard';
import { TaskActionButtons } from '../tasks/actions/TaskActionButtons';
import BacktestTaskActions from './BacktestTaskActions';
import {
  useStartBacktestTask,
  useStopBacktestTask,
  useRerunBacktestTask,
} from '../../hooks/useBacktestTaskMutations';
import { useTaskPolling } from '../../hooks/useTaskPolling';
import {
  useStrategies,
  getStrategyDisplayName,
} from '../../hooks/useStrategies';
import { useToast } from '../common';

interface BacktestTaskCardProps {
  task: BacktestTask;
}

export default function BacktestTaskCard({ task }: BacktestTaskCardProps) {
  const navigate = useNavigate();
  const { showError } = useToast();
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [optimisticStatus, setOptimisticStatus] = useState<TaskStatus | null>(
    null
  );

  const startTask = useStartBacktestTask();
  const stopTask = useStopBacktestTask();
  const rerunTask = useRerunBacktestTask();

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
  const displayStatus =
    optimisticStatus && currentStatus !== optimisticStatus
      ? optimisticStatus
      : currentStatus;

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

  const handleStart = async () => {
    try {
      // Optimistically update status to RUNNING
      setOptimisticStatus(TaskStatus.RUNNING);
      await startTask.mutate(task.id);
    } catch (error) {
      console.error('Failed to start task:', error);
      // Revert optimistic update on error
      setOptimisticStatus(null);

      // Show error notification with retry option
      const errorMessage =
        error instanceof Error ? error.message : 'Failed to start task';
      showError(errorMessage, 8000, {
        label: 'Retry',
        onClick: handleStart,
      });
    }
  };

  const handleStop = async () => {
    try {
      // Optimistically update status to STOPPED
      setOptimisticStatus(TaskStatus.STOPPED);
      await stopTask.mutate(task.id);
    } catch (error) {
      console.error('Failed to stop task:', error);
      // Revert optimistic update on error
      setOptimisticStatus(null);

      // Show error notification
      const errorMessage =
        error instanceof Error ? error.message : 'Failed to stop task';
      showError(errorMessage);
    }
  };

  const handleRerun = async () => {
    try {
      // Optimistically update status to RUNNING
      setOptimisticStatus(TaskStatus.RUNNING);
      await rerunTask.mutate(task.id);
    } catch (error) {
      console.error('Failed to rerun task:', error);
      // Revert optimistic update on error
      setOptimisticStatus(null);

      // Show error notification with retry option
      const errorMessage =
        error instanceof Error ? error.message : 'Failed to rerun task';
      showError(errorMessage, 8000, {
        label: 'Retry',
        onClick: handleRerun,
      });
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

  // Determine if action buttons are loading
  const isLoading =
    startTask.isLoading || stopTask.isLoading || rerunTask.isLoading;

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
              <Chip
                label={getStrategyDisplayName(
                  strategies,
                  currentTask.strategy_type
                )}
                size="small"
                variant="outlined"
              />
              <Chip
                label={currentTask.config_name}
                size="small"
                variant="outlined"
                color="primary"
              />
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

        {/* Action buttons using shared component */}
        <Box sx={{ mb: 2 }}>
          <TaskActionButtons
            status={displayStatus}
            onStart={handleStart}
            onStop={handleStop}
            onRerun={handleRerun}
            loading={isLoading}
          />
        </Box>

        {/* Progress bar for running tasks using shared component */}
        {displayStatus === TaskStatus.RUNNING && (
          <Box sx={{ mb: 2 }}>
            <TaskProgressBar
              status={displayStatus}
              progress={progress}
              showPercentage={true}
            />
          </Box>
        )}

        {/* Metrics for completed tasks */}
        {displayStatus === TaskStatus.COMPLETED &&
          currentTask.latest_execution && (
            <Grid container spacing={2} sx={{ mt: 1 }}>
              {currentTask.latest_execution.total_return && (
                <Grid size={{ xs: 6, sm: 3 }}>
                  <MetricCard
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
                  <MetricCard
                    title="Win Rate"
                    value={`${currentTask.latest_execution.win_rate}%`}
                  />
                </Grid>
              )}
              {currentTask.latest_execution.total_trades !== undefined && (
                <Grid size={{ xs: 6, sm: 3 }}>
                  <MetricCard
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
      />
    </Card>
  );
}
