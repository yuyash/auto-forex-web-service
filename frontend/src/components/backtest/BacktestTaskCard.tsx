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
  PlayArrow as PlayIcon,
  Stop as StopIcon,
  Refresh as RefreshIcon,
  Visibility as ViewIcon,
  MoreVert as MoreVertIcon,
} from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import type { BacktestTask } from '../../types/backtestTask';
import { TaskStatus } from '../../types/common';
import { StatusBadge } from '../tasks/display/StatusBadge';
import { ProgressIndicator } from '../tasks/display/ProgressIndicator';
import { MetricCard } from '../tasks/display/MetricCard';
import BacktestTaskActions from './BacktestTaskActions';
import {
  useStartBacktestTask,
  useStopBacktestTask,
  useRerunBacktestTask,
} from '../../hooks/useBacktestTaskMutations';
import { useBacktestTaskPolling } from '../../hooks/useBacktestTasks';
import {
  useStrategies,
  getStrategyDisplayName,
} from '../../hooks/useStrategies';

interface BacktestTaskCardProps {
  task: BacktestTask;
}

export default function BacktestTaskCard({ task }: BacktestTaskCardProps) {
  const navigate = useNavigate();
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);

  const startTask = useStartBacktestTask();
  const stopTask = useStopBacktestTask();
  const rerunTask = useRerunBacktestTask();

  // Fetch strategies for display names
  const { strategies } = useStrategies();

  // Poll for updates when task is running
  const pollingEnabled = task.status === TaskStatus.RUNNING;
  const { data: updatedTask } = useBacktestTaskPolling(
    task.id,
    pollingEnabled,
    10000 // Poll every 10 seconds
  );

  // Use updated task data if available
  const currentTask = updatedTask || task;

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
      await startTask.mutate(task.id);
    } catch (error) {
      console.error('Failed to start task:', error);
    }
  };

  const handleStop = async () => {
    try {
      await stopTask.mutate(task.id);
    } catch (error) {
      console.error('Failed to stop task:', error);
    }
  };

  const handleRerun = async () => {
    try {
      await rerunTask.mutate(task.id);
    } catch (error) {
      console.error('Failed to rerun task:', error);
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

  // Calculate progress for running tasks (mock - would come from backend)
  const progress = currentTask.status === TaskStatus.RUNNING ? 50 : 0; // Mock progress

  return (
    <Card
      sx={{
        '&:hover': {
          boxShadow: 4,
          cursor: 'pointer',
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
          <Box sx={{ flex: 1, minWidth: 0 }} onClick={handleView}>
            <Typography variant="h6" component="h2" sx={{ mb: 1.5 }}>
              {currentTask.name}
            </Typography>
            <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', mb: 1 }}>
              <StatusBadge status={currentTask.status} />
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
            {currentTask.status === TaskStatus.CREATED && (
              <Tooltip title="Start">
                <IconButton
                  color="primary"
                  onClick={handleStart}
                  disabled={startTask.isLoading}
                  size="small"
                >
                  <PlayIcon />
                </IconButton>
              </Tooltip>
            )}
            {currentTask.status === TaskStatus.RUNNING && (
              <Tooltip title="Stop">
                <IconButton
                  color="error"
                  onClick={handleStop}
                  disabled={stopTask.isLoading}
                  size="small"
                >
                  <StopIcon />
                </IconButton>
              </Tooltip>
            )}
            {(currentTask.status === TaskStatus.COMPLETED ||
              currentTask.status === TaskStatus.FAILED ||
              currentTask.status === TaskStatus.STOPPED) && (
              <Tooltip title="Rerun">
                <IconButton
                  color="primary"
                  onClick={handleRerun}
                  disabled={rerunTask.isLoading}
                  size="small"
                >
                  <RefreshIcon />
                </IconButton>
              </Tooltip>
            )}
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

        {/* Progress bar for running tasks */}
        {currentTask.status === TaskStatus.RUNNING && (
          <Box sx={{ mb: 2 }}>
            <ProgressIndicator value={progress} label="Progress" />
          </Box>
        )}

        {/* Metrics for completed tasks */}
        {currentTask.status === TaskStatus.COMPLETED &&
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
        {currentTask.status === TaskStatus.FAILED && (
          <Box
            sx={{
              mt: 2,
              p: 2,
              bgcolor: 'error.light',
              borderRadius: 1,
            }}
          >
            <Typography variant="body2" color="error.dark">
              Task execution failed
            </Typography>
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
          {currentTask.status === TaskStatus.COMPLETED && (
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
