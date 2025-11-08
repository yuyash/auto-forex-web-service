import { useState, useEffect, useRef } from 'react';

import {
  Card,
  CardContent,
  Box,
  Typography,
  Chip,
  IconButton,
  Tooltip,
  Alert,
} from '@mui/material';
import Grid from '@mui/material/Grid';
import {
  PlayArrow as PlayIcon,
  Stop as StopIcon,
  Pause as PauseIcon,
  PlayCircleOutline as ResumeIcon,
  Visibility as ViewIcon,
  MoreVert as MoreVertIcon,
  Warning as WarningIcon,
} from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import type { TradingTask } from '../../types/tradingTask';
import { TaskStatus } from '../../types/common';
import { StatusBadge } from '../tasks/display/StatusBadge';
import { MetricCard } from '../tasks/display/MetricCard';
import TradingTaskActions from './TradingTaskActions';
import {
  useStartTradingTask,
  useStopTradingTask,
  usePauseTradingTask,
  useResumeTradingTask,
} from '../../hooks/useTradingTaskMutations';
import { useTradingTaskPolling } from '../../hooks/useTradingTasks';
import { useToast } from '../common';

interface TradingTaskCardProps {
  task: TradingTask;
}

export default function TradingTaskCard({ task }: TradingTaskCardProps) {
  const navigate = useNavigate();
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const toast = useToast();
  const prevTaskRef = useRef<TradingTask>(task);

  const startTask = useStartTradingTask();
  const stopTask = useStopTradingTask();
  const pauseTask = usePauseTradingTask();
  const resumeTask = useResumeTradingTask();

  // Poll for updates when task is running or paused (more frequent for live trading)
  const pollingEnabled =
    task.status === TaskStatus.RUNNING || task.status === TaskStatus.PAUSED;
  const { data: updatedTask } = useTradingTaskPolling(
    task.id,
    pollingEnabled,
    5000 // Poll every 5 seconds for live trading
  );

  // Use updated task data if available
  const currentTask = updatedTask || task;

  // Show toast notifications for status changes and trades
  useEffect(() => {
    const prevTask = prevTaskRef.current;

    // Status change notifications
    if (prevTask.status !== currentTask.status) {
      switch (currentTask.status) {
        case TaskStatus.RUNNING:
          toast.showSuccess(`Task "${currentTask.name}" is now running`);
          break;
        case TaskStatus.PAUSED:
          toast.showWarning(`Task "${currentTask.name}" has been paused`);
          break;
        case TaskStatus.STOPPED:
          toast.showInfo(`Task "${currentTask.name}" has been stopped`);
          break;
        case TaskStatus.FAILED:
          toast.showError(`Task "${currentTask.name}" has failed`);
          break;
      }
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
      toast.showInfo(
        `${newTrades} new trade${newTrades > 1 ? 's' : ''} executed on "${currentTask.name}"`
      );
    }

    prevTaskRef.current = currentTask;
  }, [currentTask, toast]);

  const handleActionsClick = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleActionsClose = () => {
    setAnchorEl(null);
  };

  const handleView = () => {
    navigate(`/trading-tasks/${task.id}`);
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

  const handlePause = async () => {
    try {
      await pauseTask.mutate(task.id);
    } catch (error) {
      console.error('Failed to pause task:', error);
    }
  };

  const handleResume = async () => {
    try {
      await resumeTask.mutate(task.id);
    } catch (error) {
      console.error('Failed to resume task:', error);
    }
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

  // Mock P&L and positions data (would come from backend in real implementation)
  const mockPnL = currentTask.latest_execution?.total_pnl
    ? parseFloat(currentTask.latest_execution.total_pnl)
    : 0;
  const mockOpenPositions = 0; // Would come from backend

  return (
    <Card
      sx={{
        '&:hover': {
          boxShadow: 4,
          cursor: 'pointer',
        },
        transition: 'box-shadow 0.3s',
        border:
          currentTask.status === TaskStatus.RUNNING ? '2px solid' : '1px solid',
        borderColor:
          currentTask.status === TaskStatus.RUNNING
            ? 'success.main'
            : 'divider',
      }}
    >
      <CardContent>
        {/* Risk Warning for Live Trading */}
        {currentTask.status === TaskStatus.RUNNING && (
          <Alert severity="warning" icon={<WarningIcon />} sx={{ mb: 2 }}>
            <Typography variant="caption">
              <strong>Live Trading Active:</strong> Real money is at risk.
              Monitor closely.
            </Typography>
          </Alert>
        )}

        <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 2 }}>
          <Box sx={{ flex: 1 }} onClick={handleView}>
            <Typography variant="h6" component="h2" gutterBottom>
              {currentTask.name}
            </Typography>
            <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', mb: 1 }}>
              <StatusBadge status={currentTask.status} />
              <Chip
                label={currentTask.strategy_type}
                size="small"
                variant="outlined"
              />
              <Chip
                label={currentTask.config_name}
                size="small"
                variant="outlined"
                color="primary"
              />
              <Chip
                label={currentTask.account_name}
                size="small"
                variant="outlined"
                color="secondary"
              />
            </Box>
            {currentTask.description && (
              <Typography variant="body2" color="text.secondary">
                {currentTask.description}
              </Typography>
            )}
          </Box>

          <Box sx={{ display: 'flex', gap: 1, alignItems: 'flex-start' }}>
            {currentTask.status === TaskStatus.CREATED && (
              <Tooltip title="Start">
                <IconButton
                  color="primary"
                  onClick={handleStart}
                  disabled={startTask.isLoading}
                >
                  <PlayIcon />
                </IconButton>
              </Tooltip>
            )}
            {currentTask.status === TaskStatus.RUNNING && (
              <>
                <Tooltip title="Pause">
                  <IconButton
                    color="warning"
                    onClick={handlePause}
                    disabled={pauseTask.isLoading}
                  >
                    <PauseIcon />
                  </IconButton>
                </Tooltip>
                <Tooltip title="Stop">
                  <IconButton
                    color="error"
                    onClick={handleStop}
                    disabled={stopTask.isLoading}
                  >
                    <StopIcon />
                  </IconButton>
                </Tooltip>
              </>
            )}
            {currentTask.status === TaskStatus.PAUSED && (
              <>
                <Tooltip title="Resume">
                  <IconButton
                    color="primary"
                    onClick={handleResume}
                    disabled={resumeTask.isLoading}
                  >
                    <ResumeIcon />
                  </IconButton>
                </Tooltip>
                <Tooltip title="Stop">
                  <IconButton
                    color="error"
                    onClick={handleStop}
                    disabled={stopTask.isLoading}
                  >
                    <StopIcon />
                  </IconButton>
                </Tooltip>
              </>
            )}
            {currentTask.status === TaskStatus.STOPPED && (
              <Tooltip title="Start">
                <IconButton
                  color="primary"
                  onClick={handleStart}
                  disabled={startTask.isLoading}
                >
                  <PlayIcon />
                </IconButton>
              </Tooltip>
            )}
            <Tooltip title="View Details">
              <IconButton color="primary" onClick={handleView}>
                <ViewIcon />
              </IconButton>
            </Tooltip>
            <IconButton onClick={handleActionsClick}>
              <MoreVertIcon />
            </IconButton>
          </Box>
        </Box>

        {/* Live Metrics for Running/Paused Tasks */}
        {(currentTask.status === TaskStatus.RUNNING ||
          currentTask.status === TaskStatus.PAUSED) && (
          <Grid container spacing={2} sx={{ mt: 1 }}>
            <Grid size={{ xs: 6, sm: 4 }}>
              <MetricCard
                title="Live P&L"
                value={`$${mockPnL.toFixed(2)}`}
                color={mockPnL >= 0 ? 'success' : 'error'}
              />
            </Grid>
            <Grid size={{ xs: 6, sm: 4 }}>
              <MetricCard
                title="Open Positions"
                value={mockOpenPositions.toString()}
              />
            </Grid>
            {currentTask.latest_execution?.total_trades !== undefined && (
              <Grid size={{ xs: 6, sm: 4 }}>
                <MetricCard
                  title="Total Trades"
                  value={currentTask.latest_execution.total_trades.toString()}
                />
              </Grid>
            )}
          </Grid>
        )}

        {/* Performance Metrics for Stopped/Completed Tasks */}
        {(currentTask.status === TaskStatus.STOPPED ||
          currentTask.status === TaskStatus.COMPLETED) &&
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
          {currentTask.status === TaskStatus.RUNNING && (
            <Chip
              label="LIVE"
              size="small"
              color="success"
              sx={{ fontWeight: 'bold' }}
            />
          )}
        </Box>
      </CardContent>

      <TradingTaskActions
        task={currentTask}
        anchorEl={anchorEl}
        onClose={handleActionsClose}
      />
    </Card>
  );
}
