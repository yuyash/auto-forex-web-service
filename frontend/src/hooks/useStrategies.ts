// Hook for fetching available strategies
import { useQuery } from '@tanstack/react-query';
import { strategiesApi, type Strategy } from '../services/api';

interface UseStrategiesResult {
  strategies: Strategy[];
  isLoading: boolean;
  error: Error | null;
}

/**
 * Hook to fetch list of available strategies with their display names
 */
export function useStrategies(): UseStrategiesResult {
  const { data, isLoading, error } = useQuery({
    queryKey: ['strategies'],
    queryFn: () => strategiesApi.list(),
    staleTime: 5 * 60 * 1000, // 5 minutes - strategies don't change often
  });

  return {
    strategies: data?.strategies || [],
    isLoading,
    error: error as Error | null,
  };
}

/**
 * Get display name for a strategy ID
 */
export function getStrategyDisplayName(
  strategies: Strategy[],
  strategyId: string
): string {
  const strategy = strategies.find((s) => s.id === strategyId);
  return strategy?.name || strategyId;
}
