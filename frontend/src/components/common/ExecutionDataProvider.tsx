/**
 * ExecutionDataProvider - HOC component for providing execution data
 *
 * Wraps children with execution data fetched via useTaskPolling hook.
 * Handles loading, error, and data states.
 */

import React from 'react';
import { Box, CircularProgress, Alert, Typography } from '@mui/material';
import { useTaskPolling } from '../../hooks/useTaskPolling';

export interface ExecutionDataProviderProps {
  taskId: string;
  taskType: 'backtest' | 'trading';
  children: (executionId: string | null, isLoading: boolean) => React.ReactNode;
  fallback?: React.ReactNode;
  errorFallback?: (error: Error) => React.ReactNode;
}

export const ExecutionDataProvider: React.FC<ExecutionDataProviderProps> = ({
  taskId,
  taskType,
  children,
  fallback,
  errorFallback,
}) => {
  const { status, isLoading, error } = useTaskPolling(
    String(taskId),
    taskType,
    { enabled: true, pollStatus: true }
  );

  // Loading state (only when no status data yet)
  if (isLoading && !status) {
    if (fallback) {
      return <>{fallback}</>;
    }
    return (
      <Box display="flex" justifyContent="center" alignItems="center" p={3}>
        <CircularProgress />
      </Box>
    );
  }

  // Error state
  if (error) {
    if (errorFallback) {
      return <>{errorFallback(error)}</>;
    }
    return (
      <Alert severity="error">
        <Typography variant="subtitle1">
          Error Loading Execution Data
        </Typography>
        <Typography variant="body2">{error.message}</Typography>
      </Alert>
    );
  }

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const executionId = (status as any)?.execution_id ?? null;

  return <>{children(executionId, isLoading)}</>;
};

export default ExecutionDataProvider;
