import React, { useState, useCallback, type ReactNode } from 'react';
import { Snackbar, Alert, type AlertColor } from '@mui/material';
import { ToastContext } from './ToastContext';
import { getAriaLive } from '../../utils/ariaUtils';

interface ToastMessage {
  id: string;
  message: string;
  severity: AlertColor;
  duration?: number;
}

interface ToastProviderProps {
  children: ReactNode;
  maxToasts?: number;
  defaultDuration?: number;
}

export const ToastProvider: React.FC<ToastProviderProps> = ({
  children,
  maxToasts = 3,
  defaultDuration = 6000,
}) => {
  const [toasts, setToasts] = useState<ToastMessage[]>([]);

  const showToast = useCallback(
    (
      message: string,
      severity: AlertColor = 'info',
      duration: number = defaultDuration
    ) => {
      const id = `toast-${Date.now()}-${Math.random()}`;
      setToasts((prev) => {
        const newToasts = [...prev, { id, message, severity, duration }];
        // Limit the number of toasts displayed
        return newToasts.slice(-maxToasts);
      });
    },
    [maxToasts, defaultDuration]
  );

  const showSuccess = useCallback(
    (message: string, duration?: number) => {
      showToast(message, 'success', duration);
    },
    [showToast]
  );

  const showError = useCallback(
    (message: string, duration: number = 8000) => {
      // Errors stay longer by default
      showToast(message, 'error', duration);
    },
    [showToast]
  );

  const showWarning = useCallback(
    (message: string, duration: number = 7000) => {
      // Warnings stay slightly longer
      showToast(message, 'warning', duration);
    },
    [showToast]
  );

  const showInfo = useCallback(
    (message: string, duration?: number) => {
      showToast(message, 'info', duration);
    },
    [showToast]
  );

  const handleClose = (id: string) => {
    setToasts((prev) => prev.filter((toast) => toast.id !== id));
  };

  return (
    <ToastContext.Provider
      value={{ showToast, showSuccess, showError, showWarning, showInfo }}
    >
      {children}
      {toasts.map((toast, index) => (
        <Snackbar
          key={toast.id}
          open={true}
          autoHideDuration={toast.duration}
          onClose={() => handleClose(toast.id)}
          anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
          sx={{
            bottom: { xs: 16 + index * 70, sm: 24 + index * 70 },
            zIndex: (theme) => theme.zIndex.snackbar + index,
          }}
        >
          <Alert
            onClose={() => handleClose(toast.id)}
            severity={toast.severity}
            role="alert"
            aria-live={getAriaLive(toast.severity)}
            variant="filled"
            elevation={6}
            sx={{
              width: '100%',
              minWidth: 300,
              maxWidth: 500,
            }}
          >
            {toast.message}
          </Alert>
        </Snackbar>
      ))}
    </ToastContext.Provider>
  );
};

export default ToastProvider;
