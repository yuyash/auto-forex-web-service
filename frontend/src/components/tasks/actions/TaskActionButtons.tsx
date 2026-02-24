import React from 'react';
import { Box, Button, Tooltip } from '@mui/material';
import {
  PlayArrow,
  PlayCircleOutline,
  Stop,
  Pause,
  Refresh,
  Delete,
  RestartAlt,
} from '@mui/icons-material';
import { TaskStatus } from '../../../types/common';

export interface TaskActionButtonsProps {
  status: TaskStatus;
  onStart?: () => void;
  onStop?: () => void;
  onPause?: () => void;
  onResume?: () => void;
  onRestart?: () => void;
  onRerun?: () => void;
  onDelete?: () => void;
  loading?: boolean;
  disabled?: boolean;
  // State management props for showing Resume vs Restart
  canResume?: boolean;
  hasOpenPositions?: boolean;
}

/**
 * Shared component for task action buttons with consistent visibility logic.
 *
 * Button visibility rules:
 * - Show "Start" for CREATED tasks only (never executed before)
 * - Show "Resume" for stopped/paused tasks that can resume (has previous state)
 * - Show "Restart" for stopped/paused/failed tasks to start fresh
 * - Show "Stop" for running/paused tasks
 * - Show "Rerun" for completed/failed tasks (legacy support)
 * - Disable all buttons during state transitions
 * - Disable "Delete" for running tasks
 *
 */
export const TaskActionButtons: React.FC<TaskActionButtonsProps> = ({
  status,
  onStart,
  onStop,
  onPause,
  onResume,
  onRestart,
  onRerun,
  onDelete,
  loading = false,
  disabled = false,
  canResume = false,
  hasOpenPositions = false,
}) => {
  // Determine which buttons to show based on task status
  const isCreated = status === TaskStatus.CREATED;
  const isStopped = status === TaskStatus.STOPPED;
  const isPaused = status === TaskStatus.PAUSED;
  const isRunning = status === TaskStatus.RUNNING;
  const isFailed = status === TaskStatus.FAILED;
  const isCompleted = status === TaskStatus.COMPLETED;

  // Start: For CREATED tasks only (never executed before)
  const showStart = isCreated && onStart;

  // Resume: For PAUSED tasks only
  // TODO: Pause/Resume are temporarily disabled. Remove the override below to re-enable.
  // eslint-disable-next-line no-constant-binary-expression
  const showResume = false && isPaused && canResume && onResume;

  // Restart: For STOPPED/COMPLETED/FAILED tasks when we want a fresh start
  const showRestart = (isStopped || isCompleted || isFailed) && onRestart;

  // Stop: For STARTING/RUNNING/PAUSED tasks
  const showStop = (isRunning || isPaused) && onStop;

  // Pause: For RUNNING tasks only
  // TODO: Pause/Resume are temporarily disabled. Remove the override below to re-enable.
  // eslint-disable-next-line no-constant-binary-expression
  const showPause = false && isRunning && onPause;

  // Rerun: For COMPLETED/FAILED tasks (legacy, if Restart is not used)
  const showRerun = (isCompleted || isFailed) && !showRestart && onRerun;

  // Delete button is disabled for active tasks
  const deleteDisabled = isRunning || loading || disabled;

  // All action buttons are disabled during state transitions
  const actionDisabled = loading || disabled;

  return (
    <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
      {/* Start button - shown for created tasks only */}
      {showStart && (
        <Button
          variant="contained"
          color="primary"
          startIcon={<PlayArrow />}
          onClick={onStart}
          disabled={actionDisabled}
          aria-label="Start task"
        >
          Start
        </Button>
      )}

      {/* Resume button - shown for stopped/paused tasks with state */}
      {showResume && (
        <Tooltip title="Continue from where you stopped" arrow>
          <Button
            variant="contained"
            color="primary"
            startIcon={<PlayCircleOutline />}
            onClick={onResume}
            disabled={actionDisabled}
            aria-label="Resume task"
          >
            Resume
          </Button>
        </Tooltip>
      )}

      {/* Restart button - shown for stopped/paused/failed tasks */}
      {showRestart && (
        <Tooltip
          title={
            hasOpenPositions
              ? 'Restart from scratch (has open positions)'
              : 'Start fresh with new execution'
          }
          arrow
        >
          <Button
            variant="outlined"
            color="warning"
            startIcon={<RestartAlt />}
            onClick={onRestart}
            disabled={actionDisabled}
            aria-label="Restart task"
          >
            Restart
          </Button>
        </Tooltip>
      )}

      {/* Stop button - shown for running tasks */}
      {showStop && (
        <Button
          variant="contained"
          color="error"
          startIcon={<Stop />}
          onClick={onStop}
          disabled={actionDisabled}
          aria-label="Stop task"
        >
          Stop
        </Button>
      )}

      {/* Pause button - shown for running tasks */}
      {showPause && (
        <Tooltip title="Pause task, preserving execution state" arrow>
          <Button
            variant="outlined"
            color="warning"
            startIcon={<Pause />}
            onClick={onPause}
            disabled={actionDisabled}
            aria-label="Pause task"
          >
            Pause
          </Button>
        </Tooltip>
      )}

      {/* Rerun button - shown for completed/failed tasks (legacy) */}
      {showRerun && (
        <Button
          variant="contained"
          color="primary"
          startIcon={<Refresh />}
          onClick={onRerun}
          disabled={actionDisabled}
          aria-label="Rerun task"
        >
          Rerun
        </Button>
      )}

      {/* Delete button - always shown but disabled for running tasks */}
      {onDelete && (
        <Button
          variant="outlined"
          color="error"
          startIcon={<Delete />}
          onClick={onDelete}
          disabled={deleteDisabled}
          aria-label="Delete task"
        >
          Delete
        </Button>
      )}
    </Box>
  );
};
