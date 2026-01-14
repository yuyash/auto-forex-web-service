// Hook for fetching execution status with polling
import { useQuery } from '@tanstack/react-query';
import { executionApi } from '../services/api';
import type { ExecutionStatusResponse } from '../services/api';

interface UseExecutionStatusOptions {
  enabled?: boolean;
  pollingInterval?: number;
}

/**
 * Hook to fetch execution status with automatic polling
 *
 * @param executionId - The execution ID to fetch status for
 * @param options - Optional configuration
 * @param options.enabled - Enable/disable the query (default: true)
 * @param options.pollingInterval - Polling interval in ms (default: 3000)
 */
export function useExecutionStatus(
  executionId: number | null | undefined,
  options?: UseExecutionStatusOptions
) {
  const { enabled = true, pollingInterval = 3000 } = options || {};

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['execution-status', executionId],
    queryFn: () => executionApi.getStatus(executionId!),
    enabled: enabled && executionId != null,
    staleTime: 1000, // Consider data fresh for 1 second
    refetchInterval: (query) => {
      const status = query.state.data as ExecutionStatusResponse | undefined;
      // Poll if status is running or pending
      if (status?.status === 'running' || status?.status === 'pending') {
        return pollingInterval;
      }
      return false; // Disable polling for completed/failed/stopped tasks
    },
    refetchOnWindowFocus: true,
  });

  return {
    data,
    isLoading,
    error: error as Error | null,
    refetch,
  };
}
