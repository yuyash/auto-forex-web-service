// Hook for fetching available strategies
import { useQuery } from '@tanstack/react-query';
import { queryKeys } from '../config/reactQuery';
import { strategiesApi, type Strategy } from '../services/api';
import type { StrategyConfig } from '../types/strategy';

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
    queryKey: queryKeys.strategies.list(),
    queryFn: () => strategiesApi.list(),
    staleTime: 5 * 60 * 1000, // 5 minutes - strategies don't change often
  });

  return {
    strategies: data?.strategies || [],
    isLoading,
    error: error as Error | null,
  };
}

export function useStrategyDefaults(
  strategyId?: string,
  options?: { enabled?: boolean }
) {
  return useQuery({
    queryKey: strategyId
      ? queryKeys.strategies.defaults(strategyId)
      : [...queryKeys.strategies.all, 'defaults', 'empty'],
    queryFn: async (): Promise<StrategyConfig> => {
      const response = await strategiesApi.defaults(strategyId!);
      return (response.defaults ?? {}) as StrategyConfig;
    },
    enabled: Boolean(strategyId) && options?.enabled !== false,
    staleTime: 5 * 60 * 1000,
  });
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
