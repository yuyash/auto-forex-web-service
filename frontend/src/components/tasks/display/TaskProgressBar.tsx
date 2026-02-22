import React from 'react';
import { Box, LinearProgress, Typography } from '@mui/material';
import { TaskStatus } from '../../../types/common';
import { getProgressAriaLabel } from '../../../utils/ariaUtils';

export interface TaskProgressBarProps {
  status: TaskStatus;
  progress: number; // 0-100
  showPercentage?: boolean;
  size?: 'small' | 'medium' | 'large';
  estimatedTimeRemaining?: string;
}

/**
 * Shared component for displaying task progress with consistent behavior.
 *
 * Progress bar rules:
 * - Display progress bar only for running tasks
 * - Show progress percentage (0-100)
 * - Reset to 0% when task starts
 * - Keep at 100% when task completes
 * - Ensure consistent display across all views
 *
 */
export const TaskProgressBar: React.FC<TaskProgressBarProps> = React.memo(
  ({
    status,
    progress,
    showPercentage = true,
    size = 'medium',
    estimatedTimeRemaining,
  }) => {
    // Only show progress for running tasks
    const isRunning = status === TaskStatus.RUNNING;

    // Clamp progress between 0 and 100
    const clampedProgress = React.useMemo(
      () => Math.min(Math.max(progress, 0), 100),
      [progress]
    );

    // Determine height based on size
    const height = React.useMemo(() => {
      if (size === 'small') return 6;
      if (size === 'large') return 12;
      return 8;
    }, [size]);

    // Don't render anything if task is not running
    if (!isRunning) {
      return null;
    }

    return (
      <Box
        sx={{ width: '100%' }}
        role="progressbar"
        aria-valuenow={clampedProgress}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={getProgressAriaLabel(clampedProgress, status)}
      >
        {/* Progress percentage and label */}
        {showPercentage && (
          <Box
            sx={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              mb: 0.5,
            }}
          >
            <Typography
              variant="body2"
              color="text.secondary"
              sx={{ fontWeight: 600 }}
              aria-hidden="true"
            >
              {`${Math.round(clampedProgress)}%`}
            </Typography>
            {estimatedTimeRemaining && (
              <Typography variant="caption" color="text.secondary">
                {estimatedTimeRemaining} remaining
              </Typography>
            )}
          </Box>
        )}

        {/* Progress bar */}
        <LinearProgress
          variant="determinate"
          value={clampedProgress}
          color="primary"
          sx={{
            height,
            borderRadius: 1,
            '& .MuiLinearProgress-bar': {
              transition: 'transform 0.4s ease-in-out',
            },
          }}
        />
      </Box>
    );
  }
);

TaskProgressBar.displayName = 'TaskProgressBar';
