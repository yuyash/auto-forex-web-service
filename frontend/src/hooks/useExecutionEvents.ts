// Hook for fetching execution events with incremental updates
import { useQuery } from '@tanstack/react-query';
import { executionApi } from '../services/api';
import type { BacktestStrategyEvent } from '../types';

interface UseExecutionEventsOptions {
  enabled?: boolean;
  pollingInterval?: number;
  eventType?: string;
}

/**
 * Hook to fetch execution events with automatic polling and incremental updates
 *
 * @param executionId - The execution ID to fetch events for
 * @param options - Optional configuration
 * @param options.enabled - Enable/disable the query (default: true)
 * @param options.pollingInterval - Polling interval in ms (default: 3000)
 * @param options.eventType - Filter by event type
 */
export function useExecutionEvents(
  executionId: number | null | undefined,
  options?: UseExecutionEventsOptions
) {
  const { enabled = true, pollingInterval = 3000, eventType } = options || {};

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['execution-events', executionId, eventType],
    queryFn: async () => {
      if (!executionId) return { results: [], count: 0 };

      // Fetch events with optional filtering
      const response = await executionApi.getEvents(executionId, {
        page_size: 1000, // Get recent events
        event_type: eventType,
      });

      return response;
    },
    enabled: enabled && executionId != null,
    staleTime: 1000, // Consider data fresh for 1 second
    refetchInterval: pollingInterval, // Poll for new events
    refetchOnWindowFocus: true,
  });

  const events: BacktestStrategyEvent[] = data?.results || [];

  return {
    events,
    count: data?.count || 0,
    isLoading,
    error: error as Error | null,
    refetch,
  };
}
