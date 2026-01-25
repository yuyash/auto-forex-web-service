import React from 'react';
import { Chip } from '@mui/material';
import type { ChipProps } from '@mui/material';
import {
  CheckCircle,
  PlayArrow,
  Stop,
  Pause,
  Error,
  FiberManualRecord,
} from '@mui/icons-material';
import { TaskStatus } from '../../../types/common';
import { getStatusAriaLabel } from '../../../utils/ariaUtils';

interface StatusBadgeProps {
  status: TaskStatus;
  size?: ChipProps['size'];
  variant?: ChipProps['variant'];
  showIcon?: boolean;
}

const STATUS_CONFIG: Record<
  TaskStatus,
  {
    label: string;
    color: ChipProps['color'];
    icon: React.ElementType;
  }
> = {
  [TaskStatus.CREATED]: {
    label: 'Created',
    color: 'default',
    icon: FiberManualRecord,
  },
  [TaskStatus.RUNNING]: {
    label: 'Running',
    color: 'primary',
    icon: PlayArrow,
  },
  [TaskStatus.PAUSED]: {
    label: 'Paused',
    color: 'info',
    icon: Pause,
  },
  [TaskStatus.STOPPED]: {
    label: 'Stopped',
    color: 'warning',
    icon: Stop,
  },
  [TaskStatus.COMPLETED]: {
    label: 'Completed',
    color: 'success',
    icon: CheckCircle,
  },
  [TaskStatus.FAILED]: {
    label: 'Failed',
    color: 'error',
    icon: Error,
  },
};

export const StatusBadge: React.FC<StatusBadgeProps> = React.memo(
  ({ status, size = 'small', variant = 'filled', showIcon = true }) => {
    const config = STATUS_CONFIG[status];

    // Safety check for invalid status
    if (!config) {
      console.warn(`Invalid status received: ${status}`);
      return (
        <Chip
          label="Unknown"
          color="default"
          size={size}
          variant={variant}
          role="status"
        />
      );
    }

    const Icon = config.icon;

    return (
      <Chip
        label={config.label}
        color={config.color}
        size={size}
        variant={variant}
        icon={showIcon ? <Icon /> : undefined}
        role="status"
        aria-label={getStatusAriaLabel(status)}
        sx={{
          fontWeight: 500,
          ...(status === TaskStatus.RUNNING && {
            animation: 'pulse 2s ease-in-out infinite',
            '@keyframes pulse': {
              '0%, 100%': {
                opacity: 1,
              },
              '50%': {
                opacity: 0.7,
              },
            },
          }),
        }}
      />
    );
  }
);
