/**
 * TaskControlButtons - Reusable Task Control Component
 *
 * Button group with state-based enable/disable logic for task control actions.
 * Handles start, stop, pause, resume, restart, and delete actions.
 *
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
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
  autoHideLabels?: boolean;
  orientation?: 'horizontal' | 'vertical';
}

type ButtonColor =
  | 'primary'
  | 'secondary'
  | 'error'
  | 'warning'
  | 'info'
  | 'success';

interface ControlButtonConfig {
  actionKey: string;
  icon: React.ReactNode;
  label: string;
  action: (taskId: string) => void | Promise<void>;
  enabled: boolean;
  color?: ButtonColor;
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
  autoHideLabels = true,
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
  const [labelsFit, setLabelsFit] = useState(true);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const measurementRef = useRef<HTMLDivElement | null>(null);
  const pendingActionRef = useRef<string | null>(null);

  const isTrading = taskType === 'trading';

  const statusAllowsStart = status === TaskStatusEnum.CREATED;
  const statusAllowsStop = [
    TaskStatusEnum.STARTING,
    TaskStatusEnum.RUNNING,
    TaskStatusEnum.IDLE,
    TaskStatusEnum.DRAINING,
    ...(isTrading ? [] : [TaskStatusEnum.PAUSED]),
  ].includes(status);
  const statusAllowsPause = !isTrading && status === TaskStatusEnum.RUNNING;
  const statusAllowsResume = [
    TaskStatusEnum.PAUSED,
    TaskStatusEnum.STOPPED,
    ...(isTrading ? [TaskStatusEnum.FAILED] : []),
  ].includes(status);
  const statusAllowsRestart = [
    TaskStatusEnum.STOPPED,
    TaskStatusEnum.COMPLETED,
    TaskStatusEnum.FAILED,
  ].includes(status);
  const statusAllowsDelete = [
    TaskStatusEnum.CREATED,
    TaskStatusEnum.STOPPED,
    TaskStatusEnum.COMPLETED,
    TaskStatusEnum.FAILED,
  ].includes(status);

  const canStart = (actionPolicy?.can_start ?? true) && statusAllowsStart;
  const canStop = (actionPolicy?.can_stop ?? true) && statusAllowsStop;
  const canPause = (actionPolicy?.can_pause ?? true) && statusAllowsPause;
  const canResume = (actionPolicy?.can_resume ?? true) && statusAllowsResume;
  const pauseEnabled = canPause;
  const resumeEnabled = canResume;
  const canRestart = (actionPolicy?.can_restart ?? true) && statusAllowsRestart;
  const canDelete = (actionPolicy?.can_delete ?? true) && statusAllowsDelete;

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

  const buttonConfigs: ControlButtonConfig[] = [];

  if (onStart) {
    buttonConfigs.push({
      actionKey: 'start',
      icon: <StartIcon />,
      label: t('actions.start'),
      action: onStart,
      enabled: canStart,
      color: 'success',
    });
  }

  if (onResume) {
    buttonConfigs.push({
      actionKey: 'resume',
      icon: <ResumeIcon />,
      label: t('actions.resume'),
      action: onResume,
      enabled: resumeEnabled,
      color: 'primary',
    });
  }

  if (onPause && !isTrading) {
    buttonConfigs.push({
      actionKey: 'pause',
      icon: <PauseIcon />,
      label: t('actions.pause'),
      action: onPause,
      enabled: pauseEnabled,
      color: 'warning',
    });
  }

  if (onStop) {
    buttonConfigs.push({
      actionKey: 'stop',
      icon: <StopIcon />,
      label: t('actions.stop'),
      action: onStop,
      enabled: canStop,
      color: 'error',
    });
  }

  if (onRestart) {
    buttonConfigs.push({
      actionKey: 'restart',
      icon: <RestartIcon />,
      label: t('actions.restart'),
      action: onRestart,
      enabled: canRestart,
      color: 'info',
    });
  }

  if (onDelete) {
    buttonConfigs.push({
      actionKey: 'delete',
      icon: <DeleteIcon />,
      label: t('actions.delete'),
      action: onDelete,
      enabled: canDelete,
      color: 'error',
    });
  }

  const shouldAutoHideLabels =
    showLabels && autoHideLabels && orientation === 'horizontal';
  const effectiveShowLabels =
    showLabels && (!shouldAutoHideLabels || labelsFit);
  const measurementKey = `${size}:${variant}:${buttonConfigs
    .map((button) => `${button.actionKey}:${button.label}`)
    .join('|')}`;

  useEffect(() => {
    if (!shouldAutoHideLabels) {
      setLabelsFit(true);
      return;
    }

    const container = containerRef.current;
    const measurement = measurementRef.current;
    if (!container || !measurement) {
      return;
    }

    let frameId: number | null = null;
    const updateLabelsFit = () => {
      if (frameId !== null) {
        window.cancelAnimationFrame(frameId);
      }
      frameId = window.requestAnimationFrame(() => {
        const availableWidth = container.clientWidth;
        const requiredWidth = measurement.scrollWidth;
        if (availableWidth > 0 && requiredWidth > 0) {
          setLabelsFit(requiredWidth <= availableWidth + 1);
        }
      });
    };

    updateLabelsFit();

    const observer =
      typeof ResizeObserver !== 'undefined'
        ? new ResizeObserver(updateLabelsFit)
        : null;
    observer?.observe(container);
    observer?.observe(measurement);
    window.addEventListener('resize', updateLabelsFit);

    return () => {
      if (frameId !== null) {
        window.cancelAnimationFrame(frameId);
      }
      observer?.disconnect();
      window.removeEventListener('resize', updateLabelsFit);
    };
  }, [measurementKey, shouldAutoHideLabels]);

  const renderButton = (button: ControlButtonConfig) => {
    const isPending = pendingAction === button.actionKey;
    const isDisabled =
      !button.enabled || isLoading || disabled || pendingAction !== null;
    const buttonIcon = isPending ? (
      <CircularProgress size={16} color="inherit" />
    ) : (
      button.icon
    );

    if (effectiveShowLabels) {
      return (
        <Button
          key={button.actionKey}
          variant={variant}
          size={size}
          color={button.color}
          startIcon={buttonIcon}
          onClick={() => void handleAction(button.actionKey, button.action)}
          disabled={isDisabled}
          aria-label={button.label}
        >
          {button.label}
        </Button>
      );
    }

    return (
      <Tooltip key={button.actionKey} title={button.label}>
        <span>
          <IconButton
            size={size}
            color={button.color}
            onClick={() => void handleAction(button.actionKey, button.action)}
            disabled={isDisabled}
            aria-label={button.label}
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
    <Box
      ref={containerRef}
      sx={{
        position: 'relative',
        display: showLabels ? 'block' : 'inline-flex',
        width: showLabels ? '100%' : 'auto',
        maxWidth: '100%',
        minWidth: 0,
      }}
    >
      <ButtonGroup
        orientation={orientation}
        variant={variant}
        size={size}
        disabled={disabled}
        aria-label="Task control buttons"
        sx={{
          maxWidth: '100%',
          '& .MuiButton-root': {
            minWidth: 0,
            whiteSpace: 'nowrap',
          },
        }}
      >
        {buttonConfigs.map(renderButton)}
      </ButtonGroup>

      {shouldAutoHideLabels && (
        <Box
          ref={measurementRef}
          aria-hidden
          sx={{
            position: 'absolute',
            width: 'max-content',
            height: 0,
            overflow: 'hidden',
            visibility: 'hidden',
            pointerEvents: 'none',
            whiteSpace: 'nowrap',
          }}
        >
          <ButtonGroup
            orientation="horizontal"
            variant={variant}
            size={size}
            disabled={disabled}
            aria-hidden
            sx={{
              '& .MuiButton-root': {
                whiteSpace: 'nowrap',
              },
            }}
          >
            {buttonConfigs.map((button) => (
              <Button
                key={button.actionKey}
                variant={variant}
                size={size}
                color={button.color}
                startIcon={button.icon}
                tabIndex={-1}
              >
                {button.label}
              </Button>
            ))}
          </ButtonGroup>
        </Box>
      )}
    </Box>
  );
};

export default TaskControlButtons;
