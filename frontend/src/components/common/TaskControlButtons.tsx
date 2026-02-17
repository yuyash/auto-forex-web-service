/**
 * TaskControlButtons - Reusable Task Control Component
 *
 * Button group with state-based enable/disable logic for task control actions.
 * Handles start, stop, pause, resume, restart, and delete actions.
 *
 * Requirements: 11.3, 11.4, 11.11, 11.12
 */

import React from 'react';
import {
  ButtonGroup,
  Button,
  IconButton,
  Tooltip,
  CircularProgress,
  Box,
} from '@mui/material';
import {
  PlayArrow as StartIcon,
  Stop as StopIcon,
  Pause as PauseIcon,
  Replay as RestartIcon,
  Delete as DeleteIcon,
} from '@mui/icons-material';
import type { TaskStatus } from '../../types/common';
import { TaskStatus as TaskStatusEnum } from '../../types/common';

export interface TaskControlButtonsProps {
  taskId: string;
  status: TaskStatus;
  onStart?: (taskId: string) => void | Promise<void>;
  onStop?: (taskId: string) => void | Promise<void>;
  onPause?: (taskId: string) => void | Promise<void>;
  onResume?: (taskId: string) => void | Promise<void>;
  onRestart?: (taskId: string) => void | Promise<void>;
  onDelete?: (taskId: string) => void | Promise<void>;
  isLoading?: boolean;
  disabled?: boolean;
  size?: 'small' | 'medium' | 'large';
  variant?: 'text' | 'outlined' | 'contained';
  showLabels?: boolean;
  orientation?: 'horizontal' | 'vertical';
}

/**
 * TaskControlButtons Component
 *
 * Provides a consistent set of control buttons for task management.
 * Buttons are automatically enabled/disabled based on task status.
 *
 * @param taskId - The ID of the task to control
 * @param status - Current task status
 * @param onStart - Callback for start action
 * @param onStop - Callback for stop action
 * @param onPause - Callback for pause action
 * @param onResume - Callback for resume action
 * @param onRestart - Callback for restart action
 * @param onDelete - Callback for delete action
 * @param isLoading - Loading state for async operations
 * @param disabled - Disable all buttons
 * @param size - Button size
 * @param variant - Button variant
 * @param showLabels - Show button labels (default: false for icon-only)
 * @param orientation - Button group orientation
 *
 * @example
 * ```tsx
 * <TaskControlButtons
 *   taskId={task.id}
 *   status={task.status}
 *   onStart={handleStart}
 *   onStop={handleStop}
 *   onResume={handleResume}
 *   onRestart={handleRestart}
 *   onDelete={handleDelete}
 * />
 * ```
 */
export const TaskControlButtons: React.FC<TaskControlButtonsProps> = ({
  taskId,
  status,
  onStart,
  onStop,
  onPause,
  onResume,
  onRestart,
  onDelete,
  isLoading = false,
  disabled = false,
  size = 'medium',
  variant = 'outlined',
  showLabels = false,
  orientation = 'horizontal',
}) => {
  // Determine which buttons should be enabled based on status
  const canStart = [
    TaskStatusEnum.CREATED,
    'idle' as TaskStatus,
    TaskStatusEnum.STOPPED,
    TaskStatusEnum.COMPLETED,
    TaskStatusEnum.FAILED,
  ].includes(status);

  const canStop = [TaskStatusEnum.RUNNING].includes(status);
  const canPause = status === TaskStatusEnum.RUNNING;
  const canResume = [TaskStatusEnum.PAUSED, TaskStatusEnum.STOPPED].includes(
    status
  );
  const canRestart = [
    TaskStatusEnum.STOPPED,
    TaskStatusEnum.COMPLETED,
    TaskStatusEnum.FAILED,
  ].includes(status);
  const canDelete = ![TaskStatusEnum.RUNNING].includes(status);

  const handleAction = async (
    action?: (taskId: string) => void | Promise<void>
  ) => {
    if (action && !isLoading && !disabled) {
      await action(taskId);
    }
  };

  const renderButton = (
    icon: React.ReactNode,
    label: string,
    onClick: () => void,
    enabled: boolean,
    color?: 'primary' | 'secondary' | 'error' | 'warning' | 'info' | 'success'
  ) => {
    const isDisabled = !enabled || isLoading || disabled;

    if (showLabels) {
      return (
        <Button
          variant={variant}
          size={size}
          color={color}
          startIcon={icon}
          onClick={onClick}
          disabled={isDisabled}
          aria-label={label}
        >
          {label}
        </Button>
      );
    }

    return (
      <Tooltip title={label}>
        <span>
          <IconButton
            size={size}
            color={color}
            onClick={onClick}
            disabled={isDisabled}
            aria-label={label}
          >
            {icon}
          </IconButton>
        </span>
      </Tooltip>
    );
  };

  if (isLoading) {
    return (
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <CircularProgress size={size === 'small' ? 20 : 24} />
      </Box>
    );
  }

  return (
    <ButtonGroup
      orientation={orientation}
      variant={variant}
      size={size}
      disabled={disabled}
      aria-label="Task control buttons"
    >
      {/* Start Button */}
      {onStart &&
        renderButton(
          <StartIcon />,
          'Start',
          () => handleAction(onStart),
          canStart,
          'success'
        )}

      {/* Resume Button */}
      {onResume &&
        renderButton(
          <StartIcon />,
          'Resume',
          () => handleAction(onResume),
          canResume,
          'primary'
        )}

      {/* Pause Button */}
      {onPause &&
        renderButton(
          <PauseIcon />,
          'Pause',
          () => handleAction(onPause),
          canPause,
          'warning'
        )}

      {/* Stop Button */}
      {onStop &&
        renderButton(
          <StopIcon />,
          'Stop',
          () => handleAction(onStop),
          canStop,
          'error'
        )}

      {/* Restart Button */}
      {onRestart &&
        renderButton(
          <RestartIcon />,
          'Restart',
          () => handleAction(onRestart),
          canRestart,
          'info'
        )}

      {/* Delete Button */}
      {onDelete &&
        renderButton(
          <DeleteIcon />,
          'Delete',
          () => handleAction(onDelete),
          canDelete,
          'error'
        )}
    </ButtonGroup>
  );
};

export default TaskControlButtons;
