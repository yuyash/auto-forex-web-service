// Hook for fetching execution metrics with polling
import { useQuery } from '@tanstack/react-query';
import { executionApi } from '../services/api';

interface UseExecutionMetricsOptions {
  enabled?: boolean;
  pollingInterval?: number;
}

/**
 * Hook to fetch latest execution metrics checkpoint with automatic polling
 *
 * @param executionId - The execution ID to fetch metrics for
 * @param options - Optional configuration
 * @param options.enabled - Enable/disable the query (default: true)
 * @param options.pollingInterval - Polling interval in ms (default: 5000)
 */
export function useExecutionMetrics(
  executionId: number | null | undefined,
  options?: UseExecutionMetricsOptions
) {
  const { enabled = true, pollingInterval = 5000 } = options || {};

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['execution-metrics', executionId],
    queryFn: () => executionApi.getMetricsLatest(executionId!),
    enabled: enabled && executionId != null,
    staleTime: 2000, // Consider data fresh for 2 seconds
    refetchInterval: pollingInterval, // Poll for updated metrics
    refetchOnWindowFocus: true,
  });

  return {
    metrics: data,
    isLoading,
    error: error as Error | null,
    refetch,
  };
}
