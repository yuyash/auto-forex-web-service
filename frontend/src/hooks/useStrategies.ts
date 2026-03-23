import { type Strategy } from '../services/api';
import type { StrategyConfig } from '../types/strategy';
import {
  createStrategiesQuery,
  createStrategyDefaultsQuery,
} from './miscQueries';
import { mapQueryStateFields, useSimpleQueryState } from './useTaskCollections';

interface UseStrategiesResult {
  strategies: Strategy[];
  isLoading: boolean;
  error: Error | null;
}

/**
 * Hook to fetch list of available strategies with their display names
 */
export function useStrategies(): UseStrategiesResult {
  const query = useSimpleQueryState(createStrategiesQuery());
  return mapQueryStateFields(query, (data) => ({
    strategies: data?.strategies || [],
  }));
}

export function useStrategyDefaults(
  strategyId?: string,
  options?: { enabled?: boolean }
) {
  return useSimpleQueryState<StrategyConfig>(
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
