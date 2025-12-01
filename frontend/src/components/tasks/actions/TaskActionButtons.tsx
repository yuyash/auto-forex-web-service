import React from 'react';
import { Box, Button, Tooltip } from '@mui/material';
import { PlayArrow, Stop, Refresh, Delete } from '@mui/icons-material';
import { TaskStatus } from '../../../types/common';

export interface TaskActionButtonsProps {
  status: TaskStatus;
  onStart?: () => void;
  onStop?: () => void;
  onRerun?: () => void;
  onDelete?: () => void;
  loading?: boolean;
  disabled?: boolean;
}

/**
 * Shared component for task action buttons with consistent visibility logic.
 *
 * Button visibility rules:
 * - Show "Start" for created/stopped tasks
 * - Show "Stop" for running tasks
 * - Show "Rerun" for completed/failed tasks
 * - Disable all buttons during state transitions
 * - Disable "Delete" for running tasks
 *
 * Requirements: 4.1, 4.2, 4.3, 4.4
 */
export const TaskActionButtons: React.FC<TaskActionButtonsProps> = ({
  status,
  onStart,
  onStop,
  onRerun,
  onDelete,
  loading = false,
  disabled = false,
}) => {
  // Determine which buttons to show based on task status
  const showStart =
    status === TaskStatus.CREATED ||
    status === TaskStatus.STOPPED ||
    status === TaskStatus.PAUSED;
  const showStop =
    status === TaskStatus.RUNNING || status === TaskStatus.PAUSED;
  const showRerun =
    status === TaskStatus.COMPLETED || status === TaskStatus.FAILED;

  // Delete button is disabled for running tasks
  const deleteDisabled = status === TaskStatus.RUNNING || loading || disabled;

  // All action buttons are disabled during state transitions
  const actionDisabled = loading || disabled;

  return (
    <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
      {/* Start button - shown for created/stopped tasks */}
      {showStart && onStart && (
        <Button
          variant="contained"
          color="primary"
          startIcon={<PlayArrow />}
          onClick={onStart}
          disabled={actionDisabled}
          size="small"
          aria-label="Start task"
        >
          Start
        </Button>
      )}

      {/* Stop button - shown for running tasks */}
      {showStop && onStop && (
        <Button
          variant="contained"
          color="error"
          startIcon={<Stop />}
          onClick={onStop}
          disabled={actionDisabled}
          size="small"
          aria-label="Stop task"
        >
          Stop
        </Button>
      )}

      {/* Rerun button - shown for completed/failed tasks */}
      {showRerun && onRerun && (
        <Button
          variant="contained"
          color="primary"
          startIcon={<Refresh />}
          onClick={onRerun}
          disabled={actionDisabled}
          size="small"
          aria-label="Rerun task"
        >
          Rerun
        </Button>
      )}

      {/* Delete button - always shown but disabled for running tasks */}
      {onDelete && (
        <Tooltip
          title={
            status === TaskStatus.RUNNING
              ? 'Cannot delete while task is running'
              : ''
          }
          arrow
        >
          <span>
            <Button
              variant="outlined"
              color="error"
              startIcon={<Delete />}
              onClick={onDelete}
              disabled={deleteDisabled}
              size="small"
              aria-label="Delete task"
            >
              Delete
            </Button>
          </span>
        </Tooltip>
      )}
    </Box>
  );
};
