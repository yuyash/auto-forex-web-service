/**
 * ExecutionDataProvider - Higher-Order Component
 *
 * Fetches execution_id from task status and provides it to child components.
 * Handles loading and error states for execution data retrieval.
 *
 * Requirements: 11.1, 11.2, 11.3, 11.4
 */

import React, { ReactNode } from 'react';
import { Box, CircularProgress, Alert, AlertTitle } from '@mui/material';
import { useTaskPolling } from '../../hooks/useTaskPolling';
import type { TaskType } from '../../types/common';

export interface ExecutionDataProviderProps {
  taskId: number;
  taskType: TaskType;
  children: (executionId: number | null, isLoading: boolean) => ReactNode;
  fallback?: ReactNode;
  errorFallback?: (error: Error) => ReactNode;
}

/**
 * ExecutionDataProvider Component
 *
 * Fetches the execution_id from task status and provides it to children.
 * Automatically polls for status updates when task is running.
 *
 * @param taskId - The ID of the task to fetch execution data for
 * @param taskType - The type of task ('backtest' or 'trading')
 * @param children - Render prop function that receives executionId and isLoading
 * @param fallback - Optional custom loading fallback
 * @param errorFallback - Optional custom error fallback
 *
 * @example
 * ```tsx
 * <ExecutionDataProvider taskId={taskId} taskType="backtest">
 *   {(executionId, isLoading) => (
 *     isLoading ? <LoadingSpinner /> : <ExecutionDetails executionId={executionId} />
 *   )}
 * </ExecutionDataProvider>
 * ```
 */
export const ExecutionDataProvider: React.FC<ExecutionDataProviderProps> = ({
  taskId,
  taskType,
  children,
  fallback,
  errorFallback,
}) => {
  const { status, isLoading, error } = useTaskPolling(taskId, taskType, {
    enabled: true,
    pollStatus: true,
    pollDetails: false,
    pollLogs: false,
    interval: 3000,
  });

  // Handle error state
  if (error) {
    if (errorFallback) {
      return <>{errorFallback(error)}</>;
    }

    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="error">
          <AlertTitle>Error Loading Execution Data</AlertTitle>
          {error.message || 'Failed to fetch execution data. Please try again.'}
        </Alert>
      </Box>
    );
  }

  // Handle loading state
  if (isLoading && !status) {
    if (fallback) {
      return <>{fallback}</>;
    }

    return (
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          minHeight: '200px',
        }}
      >
        <CircularProgress />
      </Box>
    );
  }

  // Extract execution_id from status
  const executionId = status?.execution_id ?? null;

  // Render children with execution data
  return <>{children(executionId, isLoading)}</>;
};

export default ExecutionDataProvider;
