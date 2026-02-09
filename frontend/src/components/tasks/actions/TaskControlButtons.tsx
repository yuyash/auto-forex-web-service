// TaskControlButtons component - Start, Stop, Resume, Restart buttons
import React, { useState } from 'react';
import {
  Box,
  Button,
  ButtonGroup,
  CircularProgress,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Typography,
  FormControlLabel,
  Radio,
  RadioGroup,
} from '@mui/material';
import {
  PlayArrow as StartIcon,
  Stop as StopIcon,
  Pause as PauseIcon,
  PlayCircle as ResumeIcon,
  Refresh as RestartIcon,
} from '@mui/icons-material';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { backtestTasksApi, tradingTasksApi } from '../../../services/api';
import { TaskType, TaskStatus } from '../../../types';

interface TaskControlButtonsProps {
  taskId: number;
  taskType: TaskType;
  currentStatus: TaskStatus;
  onSuccess?: () => void;
  onError?: (error: Error) => void;
}

export const TaskControlButtons: React.FC<TaskControlButtonsProps> = ({
  taskId,
  taskType,
  currentStatus,
  onSuccess,
  onError,
}) => {
  const queryClient = useQueryClient();
  const [stopDialogOpen, setStopDialogOpen] = useState(false);
  const [restartDialogOpen, setRestartDialogOpen] = useState(false);
  const [stopMode, setStopMode] = useState<
    'immediate' | 'graceful' | 'graceful_close'
  >('graceful');
  const [clearState, setClearState] = useState(true);

  const api =
    taskType === TaskType.BACKTEST ? backtestTasksApi : tradingTasksApi;

  // Start mutation
  const startMutation = useMutation<unknown, Error, void>({
    mutationFn: () => {
      console.log(
        `[TaskControl:START] Initiating start - taskId=${taskId}, taskType=${taskType}`
      );
      return api.start(taskId);
    },
    onSuccess: (data) => {
      console.log(`[TaskControl:START] SUCCESS - taskId=${taskId}`, data);
      queryClient.invalidateQueries({ queryKey: ['execution-status'] });
      queryClient.invalidateQueries({
        queryKey:
          taskType === TaskType.BACKTEST
            ? ['backtest-task', taskId]
            : ['trading-task', taskId],
      });
      onSuccess?.();
    },
    onError: (error: Error) => {
      console.error(`[TaskControl:START] ERROR - taskId=${taskId}`, error);
      onError?.(error);
    },
  });

  // Stop mutation
  const stopMutation = useMutation<unknown, Error, void>({
    mutationFn: () => {
      console.log(
        `[TaskControl:STOP] Initiating stop - taskId=${taskId}, taskType=${taskType}, mode=${stopMode}`
      );
      if (taskType === TaskType.TRADING) {
        return tradingTasksApi.stop(taskId);
      }
      return backtestTasksApi.stop(taskId);
    },
    onSuccess: (data) => {
      console.log(`[TaskControl:STOP] SUCCESS - taskId=${taskId}`, data);
      queryClient.invalidateQueries({ queryKey: ['execution-status'] });
      queryClient.invalidateQueries({
        queryKey:
          taskType === TaskType.BACKTEST
            ? ['backtest-task', taskId]
            : ['trading-task', taskId],
      });
      setStopDialogOpen(false);
      onSuccess?.();
    },
    onError: (error: Error) => {
      console.error(`[TaskControl:STOP] ERROR - taskId=${taskId}`, error);
      setStopDialogOpen(false);
      onError?.(error);
    },
  });

  // Pause mutation (trading only)
  const pauseMutation = useMutation<unknown, Error, void>({
    mutationFn: () => {
      console.log(`[TaskControl:PAUSE] Initiating pause - taskId=${taskId}`);
      return tradingTasksApi.pause(taskId);
    },
    onSuccess: (data) => {
      console.log(`[TaskControl:PAUSE] SUCCESS - taskId=${taskId}`, data);
      queryClient.invalidateQueries({ queryKey: ['execution-status'] });
      queryClient.invalidateQueries({ queryKey: ['trading-task', taskId] });
      onSuccess?.();
    },
    onError: (error: Error) => {
      console.error(`[TaskControl:PAUSE] ERROR - taskId=${taskId}`, error);
      onError?.(error);
    },
  });

  // Resume mutation (trading only)
  const resumeMutation = useMutation<unknown, Error, void>({
    mutationFn: () => {
      console.log(`[TaskControl:RESUME] Initiating resume - taskId=${taskId}`);
      return tradingTasksApi.resume(taskId);
    },
    onSuccess: (data) => {
      console.log(`[TaskControl:RESUME] SUCCESS - taskId=${taskId}`, data);
      queryClient.invalidateQueries({ queryKey: ['execution-status'] });
      queryClient.invalidateQueries({ queryKey: ['trading-task', taskId] });
      onSuccess?.();
    },
    onError: (error: Error) => {
      console.error(`[TaskControl:RESUME] ERROR - taskId=${taskId}`, error);
      onError?.(error);
    },
  });

  // Restart mutation
  const restartMutation = useMutation<unknown, Error, void>({
    mutationFn: () => {
      console.log(
        `[TaskControl:RESTART] Initiating restart - taskId=${taskId}, taskType=${taskType}, clearState=${clearState}`
      );
      return api.restart(taskId);
    },
    onSuccess: (data) => {
      console.log(`[TaskControl:RESTART] SUCCESS - taskId=${taskId}`, data);
      queryClient.invalidateQueries({ queryKey: ['execution-status'] });
      queryClient.invalidateQueries({
        queryKey:
          taskType === TaskType.BACKTEST
            ? ['backtest-task', taskId]
            : ['trading-task', taskId],
      });
      setRestartDialogOpen(false);
      onSuccess?.();
    },
    onError: (error: Error) => {
      console.error(`[TaskControl:RESTART] ERROR - taskId=${taskId}`, error);
      setRestartDialogOpen(false);
      onError?.(error);
    },
  });

  const isLoading =
    startMutation.isPending ||
    stopMutation.isPending ||
    pauseMutation.isPending ||
    resumeMutation.isPending ||
    restartMutation.isPending;

  const canStart = [TaskStatus.CREATED].includes(currentStatus);

  const canStop = currentStatus === TaskStatus.RUNNING;

  const canPause = currentStatus === TaskStatus.RUNNING;

  const canResume = currentStatus === TaskStatus.PAUSED;

  const canRestart = [
    TaskStatus.STOPPED,
    TaskStatus.COMPLETED,
    TaskStatus.FAILED,
  ].includes(currentStatus);

  const hasAnyButton =
    canStart || canStop || canPause || canResume || canRestart;

  if (!hasAnyButton) {
    return null;
  }

  return (
    <>
      <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
        <ButtonGroup variant="contained" disabled={isLoading}>
          {canStart && (
            <Button
              startIcon={
                isLoading ? <CircularProgress size={16} /> : <StartIcon />
              }
              onClick={() => startMutation.mutate()}
              color="primary"
            >
              Start
            </Button>
          )}

          {canStop && (
            <Button
              startIcon={
                isLoading ? <CircularProgress size={16} /> : <StopIcon />
              }
              onClick={() => setStopDialogOpen(true)}
              color="error"
            >
              Stop
            </Button>
          )}

          {canPause && (
            <Button
              startIcon={
                isLoading ? <CircularProgress size={16} /> : <PauseIcon />
              }
              onClick={() => pauseMutation.mutate()}
              color="warning"
            >
              Pause
            </Button>
          )}

          {canResume && (
            <Button
              startIcon={
                isLoading ? <CircularProgress size={16} /> : <ResumeIcon />
              }
              onClick={() => resumeMutation.mutate()}
              color="success"
            >
              Resume
            </Button>
          )}

          {canRestart && (
            <Button
              startIcon={
                isLoading ? <CircularProgress size={16} /> : <RestartIcon />
              }
              onClick={() => setRestartDialogOpen(true)}
              color="info"
            >
              Restart
            </Button>
          )}
        </ButtonGroup>
      </Box>

      {/* Stop Dialog */}
      <Dialog open={stopDialogOpen} onClose={() => setStopDialogOpen(false)}>
        <DialogTitle>Stop Task</DialogTitle>
        <DialogContent>
          <Typography gutterBottom>
            Are you sure you want to stop this task?
          </Typography>
          {taskType === TaskType.TRADING && (
            <RadioGroup
              value={stopMode}
              onChange={(e) =>
                setStopMode(
                  e.target.value as 'immediate' | 'graceful' | 'graceful_close'
                )
              }
            >
              <FormControlLabel
                value="graceful"
                control={<Radio />}
                label="Graceful - Stop after current tick"
              />
              <FormControlLabel
                value="graceful_close"
                control={<Radio />}
                label="Graceful Close - Close all positions then stop"
              />
              <FormControlLabel
                value="immediate"
                control={<Radio />}
                label="Immediate - Stop immediately"
              />
            </RadioGroup>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setStopDialogOpen(false)}>Cancel</Button>
          <Button
            onClick={() => stopMutation.mutate()}
            color="error"
            variant="contained"
          >
            Stop
          </Button>
        </DialogActions>
      </Dialog>

      {/* Restart Dialog */}
      <Dialog
        open={restartDialogOpen}
        onClose={() => setRestartDialogOpen(false)}
      >
        <DialogTitle>Restart Task</DialogTitle>
        <DialogContent>
          <Typography gutterBottom>
            Are you sure you want to restart this task?
          </Typography>
          <FormControlLabel
            control={
              <Radio
                checked={clearState}
                onChange={(e) => setClearState(e.target.checked)}
              />
            }
            label="Clear strategy state (start fresh)"
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setRestartDialogOpen(false)}>Cancel</Button>
          <Button
            onClick={() => restartMutation.mutate()}
            color="info"
            variant="contained"
          >
            Restart
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
};
