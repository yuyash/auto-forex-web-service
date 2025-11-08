import React from 'react';
import {
  Alert,
  AlertTitle,
  Box,
  Typography,
  Collapse,
  IconButton,
  Paper,
} from '@mui/material';
import {
  ExpandMore,
  ExpandLess,
  Error as ErrorIcon,
  Warning as WarningIcon,
  Info as InfoIcon,
} from '@mui/icons-material';
import type { ApiError } from '../../../types/common';

interface ErrorDisplayProps {
  error: ApiError | Error | string | null;
  severity?: 'error' | 'warning' | 'info';
  title?: string;
  showDetails?: boolean;
  onRetry?: () => void;
  onDismiss?: () => void;
}

export const ErrorDisplay: React.FC<ErrorDisplayProps> = ({
  error,
  severity = 'error',
  title,
  showDetails = true,
  onRetry,
  onDismiss,
}) => {
  const [expanded, setExpanded] = React.useState(false);

  if (!error) return null;

  // Parse error message
  const getErrorMessage = (): string => {
    if (typeof error === 'string') {
      return error;
    }

    if (error instanceof Error) {
      return error.message;
    }

    // Handle ApiError
    if ('error' in error && error.error) {
      return error.error.message;
    }

    if ('message' in error && error.message) {
      return error.message as string;
    }

    if ('detail' in error && error.detail) {
      return error.detail as string;
    }

    return 'An unexpected error occurred';
  };

  // Get error details
  const getErrorDetails = (): Record<string, unknown> | null => {
    if (typeof error === 'string' || error instanceof Error) {
      return null;
    }

    if ('error' in error && error.error?.details) {
      return error.error.details;
    }

    // Return all other fields as details
    const { error: errorField, message, detail, ...rest } = error;
    // Avoid unused variable warning
    void errorField;
    void message;
    void detail;
    return Object.keys(rest).length > 0 ? rest : null;
  };

  // Get error code
  const getErrorCode = (): string | null => {
    if (typeof error === 'string' || error instanceof Error) {
      return null;
    }

    if ('error' in error && error.error?.code) {
      return error.error.code;
    }

    return null;
  };

  const errorMessage = getErrorMessage();
  const errorDetails = getErrorDetails();
  const errorCode = getErrorCode();
  const hasDetails =
    showDetails && (errorDetails || errorCode || error instanceof Error);

  const getIcon = () => {
    switch (severity) {
      case 'warning':
        return <WarningIcon />;
      case 'info':
        return <InfoIcon />;
      default:
        return <ErrorIcon />;
    }
  };

  return (
    <Alert
      severity={severity}
      icon={getIcon()}
      onClose={onDismiss}
      action={
        hasDetails ? (
          <IconButton
            size="small"
            onClick={() => setExpanded(!expanded)}
            sx={{ ml: 1 }}
          >
            {expanded ? <ExpandLess /> : <ExpandMore />}
          </IconButton>
        ) : undefined
      }
    >
      {title && <AlertTitle>{title}</AlertTitle>}
      <Typography variant="body2">{errorMessage}</Typography>

      {onRetry && (
        <Box sx={{ mt: 1 }}>
          <Typography
            variant="body2"
            component="span"
            sx={{
              cursor: 'pointer',
              textDecoration: 'underline',
              fontWeight: 500,
            }}
            onClick={onRetry}
          >
            Try again
          </Typography>
        </Box>
      )}

      {hasDetails && (
        <Collapse in={expanded} timeout="auto" unmountOnExit>
          <Paper
            variant="outlined"
            sx={{
              mt: 2,
              p: 2,
              bgcolor: 'background.default',
              maxHeight: 300,
              overflow: 'auto',
            }}
          >
            {errorCode && (
              <Box sx={{ mb: 1 }}>
                <Typography variant="caption" color="text.secondary">
                  Error Code:
                </Typography>
                <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                  {errorCode}
                </Typography>
              </Box>
            )}

            {error instanceof Error && error.stack && (
              <Box sx={{ mb: 1 }}>
                <Typography variant="caption" color="text.secondary">
                  Stack Trace:
                </Typography>
                <Typography
                  variant="body2"
                  component="pre"
                  sx={{
                    fontFamily: 'monospace',
                    fontSize: '0.75rem',
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-word',
                  }}
                >
                  {error.stack}
                </Typography>
              </Box>
            )}

            {errorDetails && (
              <Box>
                <Typography variant="caption" color="text.secondary">
                  Details:
                </Typography>
                <Typography
                  variant="body2"
                  component="pre"
                  sx={{
                    fontFamily: 'monospace',
                    fontSize: '0.75rem',
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-word',
                  }}
                >
                  {JSON.stringify(errorDetails, null, 2)}
                </Typography>
              </Box>
            )}
          </Paper>
        </Collapse>
      )}
    </Alert>
  );
};
