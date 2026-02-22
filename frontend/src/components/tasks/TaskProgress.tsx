import React from 'react';
import { Box, LinearProgress, Typography } from '@mui/material';
import { TaskStatus } from '../../types/common';

export interface TaskProgressProps {
  status: TaskStatus;
  progress: number; // 0-100
  compact?: boolean; // Compact mode for list views, full-width for detail pages
  showPercentage?: boolean;
}

/**
 * TaskProgress component for displaying task execution progress.
 *
 * Features:
 * - Compact mode for list views
 * - Full-width mode for detail pages
 * - Smooth progress animations
 * - Color-coded by status (blue=running, green=completed, red=failed)
 * - Hidden when task is not running
 *
 */
export const TaskProgress: React.FC<TaskProgressProps> = React.memo(
  ({ status, progress, compact = false, showPercentage = true }) => {
    // Only show progress for running tasks (Requirement 3.1)
    const isRunning = status === TaskStatus.RUNNING;

    // Clamp progress between 0 and 100
    const clampedProgress = React.useMemo(
      () => Math.min(Math.max(progress, 0), 100),
      [progress]
    );

    // Determine color based on status (Requirement: Color-code by status)
    const getProgressColor = () => {
      switch (status) {
        case TaskStatus.RUNNING:
          return 'primary'; // Blue for running
        case TaskStatus.COMPLETED:
          return 'success'; // Green for completed
        case TaskStatus.FAILED:
          return 'error'; // Red for failed
        default:
          return 'primary';
      }
    };

    // Determine height based on compact mode (Requirement 3.2, 3.3)
    const height = compact ? 6 : 8;

    // Hide when task is not running (Requirement: Hide when task is not running)
    if (!isRunning) {
      return null;
    }

    return (
      <Box sx={{ width: '100%' }}>
        {/* Progress percentage (Requirement 3.1) */}
        {showPercentage && (
          <Box
            sx={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              mb: compact ? 0.25 : 0.5,
            }}
          >
            <Typography
              variant={compact ? 'caption' : 'body2'}
              color="text.secondary"
              sx={{ fontWeight: 600 }}
              aria-hidden="true"
            >
              {`${Math.round(clampedProgress)}%`}
            </Typography>
          </Box>
        )}

        {/* Progress bar with smooth animations (Requirement 3.4) */}
        <LinearProgress
          variant="determinate"
          value={clampedProgress}
          color={getProgressColor()}
          aria-label={`Task progress: ${Math.round(clampedProgress)}%`}
          sx={{
            height,
            borderRadius: 1,
            '& .MuiLinearProgress-bar': {
              transition: 'transform 0.4s ease-in-out', // Smooth animation
            },
          }}
        />
      </Box>
    );
  }
);

TaskProgress.displayName = 'TaskProgress';
