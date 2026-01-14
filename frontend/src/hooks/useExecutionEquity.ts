// Hook for fetching execution equity curve with incremental updates
import { useQuery } from '@tanstack/react-query';
import { executionApi } from '../services/api';
import type { EquityPoint } from '../types';

interface UseExecutionEquityOptions {
  enabled?: boolean;
  pollingInterval?: number;
}

/**
 * Hook to fetch execution equity curve with automatic polling and incremental updates
 *
 * @param executionId - The execution ID to fetch equity for
 * @param options - Optional configuration
 * @param options.enabled - Enable/disable the query (default: true)
 * @param options.pollingInterval - Polling interval in ms (default: 5000)
 */
export function useExecutionEquity(
  executionId: number | null | undefined,
  options?: UseExecutionEquityOptions
) {
  const { enabled = true, pollingInterval = 5000 } = options || {};

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['execution-equity', executionId],
    queryFn: async () => {
      if (!executionId) return { results: [], count: 0 };

      // Fetch all equity points
      const response = await executionApi.getEquity(executionId, {
        page_size: 10000, // Large page size to get all points
      });

      return response;
    },
    enabled: enabled && executionId != null,
    staleTime: 2000, // Consider data fresh for 2 seconds
    refetchInterval: pollingInterval, // Poll for new equity points
    refetchOnWindowFocus: true,
  });

  const equityPoints: EquityPoint[] = data?.results || [];

  return {
    equityPoints,
    count: data?.count || 0,
    isLoading,
    error: error as Error | null,
    refetch,
  };
}
