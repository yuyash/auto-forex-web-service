// Hook for fetching available strategies
import { useQuery } from '@tanstack/react-query';
import { type Strategy } from '../services/api';
import type { StrategyConfig } from '../types/strategy';
import {
  createStrategiesQuery,
  createStrategyDefaultsQuery,
} from './miscQueries';

interface UseStrategiesResult {
  strategies: Strategy[];
  isLoading: boolean;
  error: Error | null;
}

/**
 * Hook to fetch list of available strategies with their display names
 */
export function useStrategies(): UseStrategiesResult {
  const { data, isLoading, error } = useQuery(createStrategiesQuery());

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
  return useQuery<StrategyConfig>(
    createStrategyDefaultsQuery(strategyId, options)
  );
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
