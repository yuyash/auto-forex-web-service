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
  Button,
  Menu,
  MenuItem,
  ListItemIcon,
  ListItemText,
} from '@mui/material';
import Grid from '@mui/material/Grid';
import {
  PlayArrow as PlayIcon,
  Stop as StopIcon,
  Visibility as ViewIcon,
  MoreVert as MoreVertIcon,
  Warning as WarningIcon,
  TrendingFlat as KeepPositionsIcon,
  ExitToApp as ClosePositionsIcon,
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
} from '../../hooks/useTradingTaskMutations';
import { useTaskPolling } from '../../hooks/useTaskPolling';
import { useToast } from '../common';
import {
  useStrategies,
  getStrategyDisplayName,
} from '../../hooks/useStrategies';

import type { StopMode } from '../../hooks/useTradingTaskMutations';

interface TradingTaskCardProps {
  task: TradingTask;
  onRefresh?: () => void;
}

export default function TradingTaskCard({
  task,
  onRefresh,
}: TradingTaskCardProps) {
  const navigate = useNavigate();
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [stopMenuAnchor, setStopMenuAnchor] = useState<null | HTMLElement>(
    null
  );
  const [optimisticStatus, setOptimisticStatus] = useState<TaskStatus | null>(
    null
  );
  const toast = useToast();
  const prevTaskRef = useRef<TradingTask>(task);

  const startTask = useStartTradingTask();
  const stopTask = useStopTradingTask();

  // Fetch strategies for display names
  const { strategies } = useStrategies();

  // Poll for updates when task is running or paused (more frequent for live trading) (Requirements 1.2, 4.5)
  const pollingEnabled =
    task.status === TaskStatus.RUNNING ||
    task.status === TaskStatus.PAUSED ||
    optimisticStatus === TaskStatus.RUNNING ||
    optimisticStatus === TaskStatus.PAUSED;

  const { status: polledStatus } = useTaskPolling(task.id, 'trading', {
    enabled: pollingEnabled,
    pollStatus: true,
    interval: 3000, // Poll every 3 seconds for live trading (more frequent)
  });

  // Use polled status if available, otherwise use task status
  const currentStatus = polledStatus?.status || task.status;

  // Clear optimistic status when actual status matches (derived state pattern)
  const displayStatus: TaskStatus =
    optimisticStatus && currentStatus !== optimisticStatus
      ? optimisticStatus
      : currentStatus;

  // Use original task data (polledStatus only provides status, not full task details)
  const currentTask = task;

  // Trigger refresh when polled status differs from task prop status
  // This ensures parent component gets updated data
  useEffect(() => {
    if (polledStatus && polledStatus.status !== task.status) {
      console.log('[TradingTaskCard] Status changed via polling:', {
        taskId: task.id,
        propStatus: task.status,
        polledStatus: polledStatus.status,
      });
      // Clear optimistic status since we have real status now
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setOptimisticStatus(null);
      // Notify parent to refetch task list
      onRefresh?.();
    }
  }, [polledStatus, task.status, task.id, onRefresh]);

  // Show toast notifications for status changes and trades
  useEffect(() => {
    const prevTask = prevTaskRef.current;

    // Status change notifications - use displayStatus for accurate current state
    if (prevTask.status !== displayStatus) {
      switch (displayStatus) {
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
      toast.showInfo(
        `${newTrades} new trade${newTrades > 1 ? 's' : ''} executed on "${currentTask.name}"`
      );
    }

    prevTaskRef.current = currentTask;
  }, [currentTask, displayStatus, toast]);

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
      // Wait for API response before updating status
      await startTask.mutate(task.id);
      // Only update status after successful response
      setOptimisticStatus(TaskStatus.RUNNING);
      // Trigger refresh after successful start
      onRefresh?.();
    } catch (error) {
      console.error('Failed to start task:', error);
      // Clear any optimistic update on error
      setOptimisticStatus(null);

      // Show error notification with retry option
      const errorMessage =
        error instanceof Error ? error.message : 'Failed to start task';
      toast.showError(errorMessage, undefined, {
        label: 'Retry',
        onClick: handleStart,
      });
    }
  };

  const handleStopMenuOpen = (event: React.MouseEvent<HTMLElement>) => {
    setStopMenuAnchor(event.currentTarget);
  };

  const handleStopMenuClose = () => {
    setStopMenuAnchor(null);
  };

  const handleStop = async (mode: StopMode = 'graceful') => {
    handleStopMenuClose();
    try {
      // Wait for API response before updating status
      await stopTask.mutate({ id: task.id, mode });
      // Only update status after successful response
      setOptimisticStatus(TaskStatus.STOPPED);
      // Trigger refresh after successful stop
      onRefresh?.();
    } catch (error) {
      console.error('Failed to stop task:', error);
      // Clear any optimistic update on error
      setOptimisticStatus(null);

      // Show error notification
      const errorMessage =
        error instanceof Error ? error.message : 'Failed to stop task';
      toast.showError(errorMessage);
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

  const currentPnL = currentTask.latest_execution?.total_pnl
    ? parseFloat(currentTask.latest_execution.total_pnl)
    : 0;
  const openPositions = 0;

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
      <CardContent>
        {/* Risk Warning for Live Trading */}
        {displayStatus === TaskStatus.RUNNING &&
          currentTask.account_type === 'live' && (
            <Alert severity="warning" icon={<WarningIcon />} sx={{ mb: 2 }}>
              <Typography variant="caption">
                <strong>Live Trading Active:</strong> Real money is at risk.
                Monitor closely.
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
                  label="LIVE ACCOUNT"
                  size="small"
                  color="error"
                  sx={{ fontWeight: 'bold' }}
                />
              )}
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

        {/* Action buttons - Trading tasks have different button logic */}
        <Box sx={{ mb: 2, display: 'flex', gap: 1 }}>
          {(displayStatus === TaskStatus.CREATED ||
            displayStatus === TaskStatus.STOPPED ||
            displayStatus === TaskStatus.PAUSED) && (
            <Button
              variant="contained"
              color="primary"
              startIcon={<PlayIcon />}
              onClick={handleStart}
              disabled={startTask.isLoading || stopTask.isLoading}
              size="small"
            >
              {startTask.isLoading ? 'Starting...' : 'Start'}
            </Button>
          )}
          {(displayStatus === TaskStatus.RUNNING ||
            displayStatus === TaskStatus.PAUSED) && (
            <Button
              variant="contained"
              color="error"
              startIcon={<StopIcon />}
              onClick={handleStopMenuOpen}
              disabled={stopTask.isLoading || startTask.isLoading}
              size="small"
            >
              {stopTask.isLoading ? 'Stopping...' : 'Stop'}
            </Button>
          )}
        </Box>

        {/* Live Metrics for Running/Paused Tasks */}
        {(displayStatus === TaskStatus.RUNNING ||
          displayStatus === TaskStatus.PAUSED) && (
          <Grid container spacing={2} sx={{ mt: 1 }}>
            <Grid size={{ xs: 6, sm: 4 }}>
              <MetricCard
                title="Live P&L"
                value={`$${currentPnL.toFixed(2)}`}
                color={currentPnL >= 0 ? 'success' : 'error'}
              />
            </Grid>
            <Grid size={{ xs: 6, sm: 4 }}>
              <MetricCard
                title="Open Positions"
                value={openPositions.toString()}
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
        {(displayStatus === TaskStatus.STOPPED ||
          displayStatus === TaskStatus.COMPLETED) &&
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
          {displayStatus === TaskStatus.RUNNING && (
            <Chip
              label="LIVE"
              size="small"
              color="success"
              sx={{ fontWeight: 'bold' }}
            />
          )}
        </Box>
      </CardContent>

      {/* Stop Mode Menu */}
      <Menu
        anchorEl={stopMenuAnchor}
        open={Boolean(stopMenuAnchor)}
        onClose={handleStopMenuClose}
      >
        <MenuItem onClick={() => handleStop('graceful')}>
          <ListItemIcon>
            <KeepPositionsIcon fontSize="small" color="primary" />
          </ListItemIcon>
          <ListItemText
            primary="Stop (Keep Positions)"
            secondary="Stop trading but keep all open positions"
          />
        </MenuItem>
        <MenuItem onClick={() => handleStop('graceful_close')}>
          <ListItemIcon>
            <ClosePositionsIcon fontSize="small" color="error" />
          </ListItemIcon>
          <ListItemText
            primary="Stop (Close All Positions)"
            secondary="Stop trading and close all positions at market price"
          />
        </MenuItem>
      </Menu>

      <TradingTaskActions
        task={currentTask}
        anchorEl={anchorEl}
        onClose={handleActionsClose}
        onRefresh={onRefresh}
      />
    </Card>
  );
}
