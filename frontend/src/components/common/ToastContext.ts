import { createContext } from 'react';
import type { AlertColor } from '@mui/material';

export interface ToastAction {
  label: string;
  onClick: () => void;
}

export interface ToastContextType {
  showToast: (
    message: string,
    severity?: AlertColor,
    duration?: number,
    action?: ToastAction
  ) => void;
  showSuccess: (message: string, duration?: number) => void;
  showError: (message: string, duration?: number, action?: ToastAction) => void;
  showWarning: (message: string, duration?: number) => void;
  showInfo: (message: string, duration?: number) => void;
}

export const ToastContext = createContext<ToastContextType | undefined>(
  undefined
);
