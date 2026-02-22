import React from 'react';
import {
  IconButton,
  Menu,
  MenuItem,
  ListItemIcon,
  ListItemText,
  Divider,
  Tooltip,
} from '@mui/material';
import {
  MoreVert,
  PlayArrow,
  Stop,
  Pause,
  PlayCircle,
  Refresh,
  ContentCopy,
  Edit,
  Delete,
  Visibility,
} from '@mui/icons-material';
import { TaskStatus } from '../../../types/common';

export interface TaskAction {
  id: string;
  label: string;
  icon: React.ReactNode;
  onClick: () => void;
  disabled?: boolean;
  divider?: boolean;
  color?: 'default' | 'primary' | 'error' | 'warning';
  tooltip?: string;
}

interface TaskActionMenuProps {
  status: TaskStatus;
  onStart?: () => void;
  onStop?: () => void;
  onPause?: () => void;
  onResume?: () => void;
  onRerun?: () => void;
  onCopy?: () => void;
  onEdit?: () => void;
  onDelete?: () => void;
  onView?: () => void;
  customActions?: TaskAction[];
  disabled?: boolean;
}

export const TaskActionMenu: React.FC<TaskActionMenuProps> = ({
  status,
  onStart,
  onStop,
  onPause,
  onResume,
  onRerun,
  onCopy,
  onEdit,
  onDelete,
  onView,
  customActions = [],
  disabled = false,
}) => {
  const [anchorEl, setAnchorEl] = React.useState<null | HTMLElement>(null);
  const open = Boolean(anchorEl);

  const handleClick = (event: React.MouseEvent<HTMLElement>) => {
    event.stopPropagation();
    setAnchorEl(event.currentTarget);
  };

  const handleClose = () => {
    setAnchorEl(null);
  };

  const handleAction = (action: () => void) => (event: React.MouseEvent) => {
    event.stopPropagation();
    handleClose();
    action();
  };

  // Build actions based on status and available handlers
  const actions: TaskAction[] = [];

  // View action
  if (onView) {
    actions.push({
      id: 'view',
      label: 'View Details',
      icon: <Visibility />,
      onClick: onView,
    });
  }

  // Lifecycle actions
  // CREATED: Start only
  if (status === TaskStatus.CREATED && onStart) {
    actions.push({
      id: 'start',
      label: 'Start',
      icon: <PlayArrow />,
      onClick: onStart,
      color: 'primary',
    });
  }

  // STARTING: Stop only
  if (status === TaskStatus.STARTING && onStop) {
    actions.push({
      id: 'stop',
      label: 'Stop',
      icon: <Stop />,
      onClick: onStop,
      color: 'error',
    });
  }

  // RUNNING: Stop, Pause
  if (status === TaskStatus.RUNNING) {
    if (onPause) {
      actions.push({
        id: 'pause',
        label: 'Pause',
        icon: <Pause />,
        onClick: onPause,
        color: 'warning',
      });
    }
    if (onStop) {
      actions.push({
        id: 'stop',
        label: 'Stop',
        icon: <Stop />,
        onClick: onStop,
        color: 'error',
      });
    }
  }

  // PAUSED: Stop, Resume
  if (status === TaskStatus.PAUSED) {
    if (onResume) {
      actions.push({
        id: 'resume',
        label: 'Resume',
        icon: <PlayCircle />,
        onClick: onResume,
        color: 'primary',
      });
    }
    if (onStop) {
      actions.push({
        id: 'stop',
        label: 'Stop',
        icon: <Stop />,
        onClick: onStop,
        color: 'error',
      });
    }
  }

  // STOPPED: Restart only
  if (status === TaskStatus.STOPPED) {
    if (onRerun) {
      actions.push({
        id: 'rerun',
        label: 'Restart',
        icon: <Refresh />,
        onClick: onRerun,
      });
    }
  }

  // COMPLETED: Restart (via Rerun)
  if (status === TaskStatus.COMPLETED && onRerun) {
    actions.push({
      id: 'rerun',
      label: 'Restart',
      icon: <Refresh />,
      onClick: onRerun,
    });
  }

  // FAILED: Restart (via Rerun)
  if (status === TaskStatus.FAILED && onRerun) {
    actions.push({
      id: 'rerun',
      label: 'Restart',
      icon: <Refresh />,
      onClick: onRerun,
    });
  }

  // Add divider before management actions
  if (actions.length > 0 && (onCopy || onEdit || onDelete)) {
    actions.push({
      id: 'divider-1',
      label: '',
      icon: null,
      onClick: () => {},
      divider: true,
    });
  }

  // Management actions
  if (onCopy) {
    actions.push({
      id: 'copy',
      label: 'Copy',
      icon: <ContentCopy />,
      onClick: onCopy,
    });
  }

  if (onEdit) {
    const isActive = [
      TaskStatus.STARTING,
      TaskStatus.RUNNING,
      TaskStatus.PAUSED,
      TaskStatus.STOPPING,
    ].includes(status);
    actions.push({
      id: 'edit',
      label: 'Edit',
      icon: <Edit />,
      onClick: onEdit,
      disabled: isActive,
      tooltip: isActive ? 'Cannot edit while task is active' : undefined,
    });
  }

  if (onDelete) {
    const cannotDelete = [
      TaskStatus.STARTING,
      TaskStatus.RUNNING,
      TaskStatus.PAUSED,
      TaskStatus.STOPPING,
    ].includes(status);
    actions.push({
      id: 'delete',
      label: 'Delete',
      icon: <Delete />,
      onClick: onDelete,
      color: 'error',
      disabled: cannotDelete,
      tooltip: cannotDelete ? 'Cannot delete while task is active' : undefined,
    });
  }

  // Add custom actions
  if (customActions.length > 0) {
    if (actions.length > 0) {
      actions.push({
        id: 'divider-2',
        label: '',
        icon: null,
        onClick: () => {},
        divider: true,
      });
    }
    actions.push(...customActions);
  }

  return (
    <>
      <Tooltip title="Actions">
        <IconButton
          onClick={handleClick}
          disabled={disabled}
          size="small"
          sx={{
            '&:hover': {
              bgcolor: 'action.hover',
            },
          }}
        >
          <MoreVert />
        </IconButton>
      </Tooltip>
      <Menu
        anchorEl={anchorEl}
        open={open}
        onClose={handleClose}
        onClick={(e) => e.stopPropagation()}
        transformOrigin={{ horizontal: 'right', vertical: 'top' }}
        anchorOrigin={{ horizontal: 'right', vertical: 'bottom' }}
      >
        {actions.map((action) => {
          if (action.divider) {
            return <Divider key={action.id} />;
          }

          const menuItem = (
            <MenuItem
              key={action.id}
              onClick={handleAction(action.onClick)}
              disabled={action.disabled}
              sx={{
                ...(action.color === 'error' && {
                  color: 'error.main',
                  '&:hover': {
                    bgcolor: 'error.light',
                  },
                }),
                ...(action.color === 'primary' && {
                  color: 'primary.main',
                }),
                ...(action.color === 'warning' && {
                  color: 'warning.main',
                }),
              }}
            >
              {action.icon && <ListItemIcon>{action.icon}</ListItemIcon>}
              <ListItemText>{action.label}</ListItemText>
            </MenuItem>
          );

          if (action.tooltip && action.disabled) {
            return (
              <Tooltip key={action.id} title={action.tooltip} placement="left">
                <span>{menuItem}</span>
              </Tooltip>
            );
          }

          return menuItem;
        })}
      </Menu>
    </>
  );
};
