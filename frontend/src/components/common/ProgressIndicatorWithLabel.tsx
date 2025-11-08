import React from 'react';
import {
  Box,
  LinearProgress,
  Typography,
  CircularProgress,
} from '@mui/material';

interface ProgressIndicatorWithLabelProps {
  value: number;
  label?: string;
  variant?: 'linear' | 'circular';
  showPercentage?: boolean;
  color?: 'primary' | 'secondary' | 'success' | 'error' | 'info' | 'warning';
}

/**
 * Progress indicator with optional label and percentage display
 * Useful for showing progress of long-running operations
 */
const ProgressIndicatorWithLabel: React.FC<ProgressIndicatorWithLabelProps> = ({
  value,
  label,
  variant = 'linear',
  showPercentage = true,
  color = 'primary',
}) => {
  if (variant === 'circular') {
    return (
      <Box sx={{ position: 'relative', display: 'inline-flex' }}>
        <CircularProgress
          variant="determinate"
          value={value}
          color={color}
          size={60}
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
              variant="caption"
              component="div"
              color="text.secondary"
            >
              {`${Math.round(value)}%`}
            </Typography>
          </Box>
        )}
      </Box>
    );
  }

  return (
    <Box sx={{ width: '100%' }}>
      {label && (
        <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
          <Typography variant="body2" color="text.secondary">
            {label}
          </Typography>
          {showPercentage && (
            <Typography variant="body2" color="text.secondary">
              {`${Math.round(value)}%`}
            </Typography>
          )}
        </Box>
      )}
      <LinearProgress
        variant="determinate"
        value={value}
        color={color}
        sx={{ height: 8, borderRadius: 4 }}
      />
    </Box>
  );
};

export default ProgressIndicatorWithLabel;
