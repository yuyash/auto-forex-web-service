import React from 'react';
import { CircularProgress } from '@mui/material';

interface ButtonLoadingSpinnerProps {
  size?: number;
  color?: 'inherit' | 'primary' | 'secondary';
}

/**
 * Small loading spinner for use inside buttons
 */
const ButtonLoadingSpinner: React.FC<ButtonLoadingSpinnerProps> = ({
  size = 20,
  color = 'inherit',
}) => {
  return <CircularProgress size={size} color={color} />;
};

export default ButtonLoadingSpinner;
