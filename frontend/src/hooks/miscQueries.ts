import type { UseQueryOptions } from '@tanstack/react-query';
import { queryKeys } from '../config/reactQuery';
import { authApi, type UserSettingsResponse } from '../services/api/auth';
import { healthApi, strategiesApi, type Strategy } from '../services/api';
import { marketApi, type TickDataRange } from '../services/api/market';
import type { StrategyConfig } from '../types/strategy';
import type { GranularityOption } from '../services/api/market';

export function createUserSettingsQuery(options?: {
  enabled?: boolean;
}): UseQueryOptions<UserSettingsResponse> {
  return {
    queryKey: queryKeys.userSettings.detail(),
    queryFn: () => authApi.getUserSettings(),
    enabled: options?.enabled !== false,
  };
}

export function createBackendHealthQuery(options?: {
  enabled?: boolean;
}): UseQueryOptions<Awaited<ReturnType<typeof healthApi.backend>>> {
  return {
    queryKey: queryKeys.health.backend(),
    queryFn: () => healthApi.backend(),
    enabled: options?.enabled !== false,
    staleTime: 60_000,
  };
}

export function createOandaHealthStatusQuery(options: {
  enabled: boolean;
  staleTime: number;
}): UseQueryOptions<Awaited<ReturnType<typeof healthApi.getOandaStatus>>> {
  return {
    queryKey: queryKeys.health.oanda(),
    queryFn: () => healthApi.getOandaStatus(),
    enabled: options.enabled,
    staleTime: options.staleTime,
    retry: false,
  };
}

export function createStrategiesQuery(): UseQueryOptions<{
  strategies: Strategy[];
}> {
  return {
    queryKey: queryKeys.strategies.list(),
    queryFn: () => strategiesApi.list(),
    staleTime: 5 * 60 * 1000,
  };
}

export function createStrategyDefaultsQuery(
  strategyId?: string,
  options?: { enabled?: boolean }
): UseQueryOptions<StrategyConfig> {
  return {
    queryKey: strategyId
      ? queryKeys.strategies.defaults(strategyId)
      : [...queryKeys.strategies.all, 'defaults', 'empty'],
    queryFn: async (): Promise<StrategyConfig> => {
      const response = await strategiesApi.defaults(strategyId!);
      return (response.defaults ?? {}) as StrategyConfig;
    },
    enabled: Boolean(strategyId) && options?.enabled !== false,
    staleTime: 5 * 60 * 1000,
  };
}

export function createSupportedInstrumentsQuery(): UseQueryOptions<string[]> {
  return {
    queryKey: queryKeys.marketConfig.instruments(),
    queryFn: async () => {
      const response = await marketApi.getSupportedInstruments();
      return response.instruments ?? [];
    },
  };
}

export function createSupportedGranularitiesQuery(): UseQueryOptions<
  GranularityOption[]
> {
  return {
    queryKey: queryKeys.marketConfig.granularities(),
    queryFn: async () => {
      const response = await marketApi.getSupportedGranularities();
      return (response.granularities ?? []).filter(
        (granularity) => !granularity.value.startsWith('S')
      );
    },
  };
}

export function createTickDataRangeQuery(
  instrument?: string
): UseQueryOptions<TickDataRange> {
  return {
    queryKey: queryKeys.marketConfig.tickDataRange(instrument ?? ''),
    queryFn: async () => marketApi.getTickDataRange(instrument!),
    enabled: Boolean(instrument),
  };
}
