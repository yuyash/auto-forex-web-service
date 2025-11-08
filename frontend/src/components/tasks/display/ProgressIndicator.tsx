import React from 'react';
import {
  Box,
  LinearProgress,
  Typography,
  CircularProgress,
  Tooltip,
} from '@mui/material';
import { getProgressAriaLabel } from '../../../utils/ariaUtils';

interface ProgressIndicatorProps {
  value: number; // 0-100
  variant?: 'linear' | 'circular';
  size?: 'small' | 'medium' | 'large';
  showPercentage?: boolean;
  label?: string;
  color?: 'primary' | 'secondary' | 'success' | 'error' | 'warning' | 'info';
  animated?: boolean;
  estimatedTimeRemaining?: string;
  status?: string;
}

export const ProgressIndicator: React.FC<ProgressIndicatorProps> = React.memo(
  ({
    value,
    variant = 'linear',
    size = 'medium',
    showPercentage = true,
    label,
    color = 'primary',
    animated = true,
    estimatedTimeRemaining,
    status = 'running',
  }) => {
    // Clamp value between 0 and 100
    const clampedValue = React.useMemo(
      () => Math.min(Math.max(value, 0), 100),
      [value]
    );

    const circularSize = React.useMemo(() => {
      if (size === 'small') return 40;
      if (size === 'large') return 80;
      return 60;
    }, [size]);

    const linearHeight = React.useMemo(() => {
      if (size === 'small') return 6;
      if (size === 'large') return 12;
      return 8;
    }, [size]);

    if (variant === 'circular') {
      return (
        <Tooltip
          title={
            estimatedTimeRemaining
              ? `${clampedValue.toFixed(1)}% • ${estimatedTimeRemaining} remaining`
              : `${clampedValue.toFixed(1)}%`
          }
        >
          <Box
            sx={{ position: 'relative', display: 'inline-flex' }}
            role="progressbar"
            aria-valuenow={clampedValue}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label={getProgressAriaLabel(clampedValue, status)}
          >
            <CircularProgress
              variant="determinate"
              value={clampedValue}
              size={circularSize}
              color={color}
              sx={{
                ...(animated && {
                  transition: 'transform 0.3s ease-in-out',
                }),
              }}
            />
            {showPercentage && (
              <Box
                sx={{
                  top: 0,
                  left: 0,
                  bottom: 0,
                  right: 0,
                  position: 'absolute',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <Typography
                  variant={size === 'small' ? 'caption' : 'body2'}
                  component="div"
                  color="text.secondary"
                  sx={{ fontWeight: 600 }}
                >
                  {`${Math.round(clampedValue)}%`}
                </Typography>
              </Box>
            )}
          </Box>
        </Tooltip>
      );
    }

    return (
      <Box
        sx={{ width: '100%' }}
        role="progressbar"
        aria-valuenow={clampedValue}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={getProgressAriaLabel(clampedValue, status)}
      >
        {(label || showPercentage) && (
          <Box
            sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}
          >
            {label && (
              <Typography
                variant="body2"
                color="text.secondary"
                id="progress-label"
              >
                {label}
              </Typography>
            )}
            {showPercentage && (
              <Typography
                variant="body2"
                color="text.secondary"
                sx={{ fontWeight: 600 }}
                aria-hidden="true"
              >
                {`${Math.round(clampedValue)}%`}
              </Typography>
            )}
          </Box>
        )}
        <LinearProgress
          variant="determinate"
          value={clampedValue}
          color={color}
          sx={{
            height: linearHeight,
            borderRadius: 1,
            ...(animated && {
              '& .MuiLinearProgress-bar': {
                transition: 'transform 0.4s ease-in-out',
              },
            }),
          }}
        />
        {estimatedTimeRemaining && (
          <Typography
            variant="caption"
            color="text.secondary"
            sx={{ display: 'block', mt: 0.5 }}
          >
            {estimatedTimeRemaining} remaining
          </Typography>
        )}
      </Box>
    );
  }
);
