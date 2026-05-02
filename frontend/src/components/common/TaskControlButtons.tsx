/**
 * TaskControlButtons - Reusable Task Control Component
 *
 * Button group with state-based enable/disable logic for task control actions.
 * Handles start, stop, pause, resume, restart, and delete actions.
 *
 */

import React, { useCallback, useRef, useState } from 'react';
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
  PlayCircleOutline as ResumeIcon,
  Stop as StopIcon,
  Pause as PauseIcon,
  Replay as RestartIcon,
  Delete as DeleteIcon,
} from '@mui/icons-material';
import { useTranslation } from 'react-i18next';
import type { TaskActionPolicy, TaskStatus } from '../../types/common';
import { TaskStatus as TaskStatusEnum } from '../../types/common';

export interface TaskControlButtonsProps {
  taskId: string;
  status: TaskStatus;
  taskType?: 'backtest' | 'trading';
  actionPolicy?: TaskActionPolicy;
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
  taskType,
  actionPolicy,
  onStart,
  onStop,
  onPause,
  onResume,
  onRestart,
  onDelete,
  isLoading = false,
  disabled = false,
  size = 'small',
  variant = 'outlined',
  showLabels = false,
  orientation = 'horizontal',
}) => {
  // Determine which buttons should be enabled based on status and task type.
  //
  // Trading tasks:
  //   CREATED: Start only
  //   STARTING: Stop only
  //   RUNNING: Stop
  //   STOPPING: (none)
  //   STOPPED: Resume, Restart, Delete
  //   COMPLETED: Restart, Delete
  //   FAILED: Resume, Restart, Delete
  //
  // Backtest tasks (unchanged):
  //   CREATED: Start only
  //   STARTING: Stop only
  //   RUNNING: Stop, Pause
  //   PAUSED: Stop, Resume
  //   STOPPING: (none)
  //   STOPPED: Restart, Delete
  //   COMPLETED: Restart, Delete
  //   FAILED: Restart, Delete
  const { t } = useTranslation('common');
  const [pendingAction, setPendingAction] = useState<string | null>(null);
  const pendingActionRef = useRef<string | null>(null);

  const isTrading = taskType === 'trading';

  const canStart = actionPolicy?.can_start ?? status === TaskStatusEnum.CREATED;

  const canStop =
    actionPolicy?.can_stop ??
    [
      TaskStatusEnum.STARTING,
      TaskStatusEnum.RUNNING,
      TaskStatusEnum.IDLE,
      TaskStatusEnum.DRAINING,
      ...(isTrading ? [] : [TaskStatusEnum.PAUSED]),
    ].includes(status);
  const canPause =
    actionPolicy?.can_pause ??
    (!isTrading && status === TaskStatusEnum.RUNNING);
  const canResume =
    actionPolicy?.can_resume ??
    (isTrading
      ? [TaskStatusEnum.STOPPED, TaskStatusEnum.FAILED].includes(status)
      : status === TaskStatusEnum.PAUSED);
  const pauseEnabled = canPause;
  const resumeEnabled = canResume;
  const canRestart =
    actionPolicy?.can_restart ??
    [
      TaskStatusEnum.STOPPED,
      TaskStatusEnum.COMPLETED,
      TaskStatusEnum.FAILED,
    ].includes(status);
  const canDelete =
    actionPolicy?.can_delete ??
    [
      TaskStatusEnum.CREATED,
      TaskStatusEnum.STOPPED,
      TaskStatusEnum.COMPLETED,
      TaskStatusEnum.FAILED,
    ].includes(status);

  const handleAction = useCallback(
    async (
      actionKey: string,
      action?: (taskId: string) => void | Promise<void>
    ) => {
      if (action && !isLoading && !disabled && !pendingActionRef.current) {
        pendingActionRef.current = actionKey;
        setPendingAction(actionKey);
        try {
          await action(taskId);
        } finally {
          pendingActionRef.current = null;
          setPendingAction(null);
        }
      }
    },
    [disabled, isLoading, taskId]
  );

  const renderButton = (
    actionKey: string,
    icon: React.ReactNode,
    label: string,
    onClick: () => void,
    enabled: boolean,
    color?: 'primary' | 'secondary' | 'error' | 'warning' | 'info' | 'success'
  ) => {
    const isPending = pendingAction === actionKey;
    const isDisabled =
      !enabled || isLoading || disabled || pendingAction !== null;
    const buttonIcon = isPending ? (
      <CircularProgress size={16} color="inherit" />
    ) : (
      icon
    );

    if (showLabels) {
      return (
        <Button
          variant={variant}
          size={size}
          color={color}
          startIcon={buttonIcon}
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
            {buttonIcon}
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
          'start',
          <StartIcon />,
          t('actions.start'),
          () => void handleAction('start', onStart),
          canStart,
          'success'
        )}

      {/* Resume Button */}
      {onResume &&
        renderButton(
          'resume',
          <ResumeIcon />,
          t('actions.resume'),
          () => void handleAction('resume', onResume),
          resumeEnabled,
          'primary'
        )}

      {/* Pause Button (backtest only) */}
      {onPause &&
        !isTrading &&
        renderButton(
          'pause',
          <PauseIcon />,
          t('actions.pause'),
          () => void handleAction('pause', onPause),
          pauseEnabled,
          'warning'
        )}

      {/* Stop Button */}
      {onStop &&
        renderButton(
          'stop',
          <StopIcon />,
          t('actions.stop'),
          () => void handleAction('stop', onStop),
          canStop,
          'error'
        )}

      {/* Restart Button */}
      {onRestart &&
        renderButton(
          'restart',
          <RestartIcon />,
          t('actions.restart'),
          () => void handleAction('restart', onRestart),
          canRestart,
          'info'
        )}

      {/* Delete Button */}
      {onDelete &&
        renderButton(
          'delete',
          <DeleteIcon />,
          t('actions.delete'),
          () => void handleAction('delete', onDelete),
          canDelete,
          'error'
        )}
    </ButtonGroup>
  );
};

export default TaskControlButtons;
