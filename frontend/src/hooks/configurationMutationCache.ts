import { queryClient, queryKeys } from '../config/reactQuery';
import type { PaginatedResponse, StrategyConfig } from '../types';

type ConfigListParams = Record<string, unknown> | undefined;

function getListParams(queryKey: readonly unknown[]): ConfigListParams {
  const candidate = queryKey[2];
  return candidate && typeof candidate === 'object'
    ? (candidate as Record<string, unknown>)
    : undefined;
}

function matchesConfigurationFilter(
  config: StrategyConfig,
  params?: ConfigListParams
): boolean {
  if (!params) {
    return true;
  }

  const strategyType = params.strategy_type;
  if (
    typeof strategyType === 'string' &&
    strategyType &&
    config.strategy_type !== strategyType
  ) {
    return false;
  }

  const search = params.search;
  if (typeof search === 'string' && search.trim()) {
    const haystack = [config.name, config.description, config.strategy_type]
      .join(' ')
      .toLowerCase();
    if (!haystack.includes(search.trim().toLowerCase())) {
      return false;
    }
  }

  return true;
}

function patchListEntry(
  cached: PaginatedResponse<StrategyConfig> | undefined,
  config: StrategyConfig,
  params?: ConfigListParams
): PaginatedResponse<StrategyConfig> | undefined {
  if (!cached) {
    return cached;
  }

  const matches = matchesConfigurationFilter(config, params);
  const index = cached.results.findIndex((entry) => entry.id === config.id);

  if (index >= 0) {
    if (!matches) {
      return {
        ...cached,
        count: Math.max(0, cached.count - 1),
        results: cached.results.filter((entry) => entry.id !== config.id),
      };
    }
    const nextResults = [...cached.results];
    nextResults[index] = { ...nextResults[index], ...config };
    return { ...cached, results: nextResults };
  }

  const page = Number(params?.page ?? 1);
  if (!matches || page > 1) {
    return cached;
  }

  return {
    ...cached,
    count: cached.count + 1,
    results: [config, ...cached.results],
  };
}

export function upsertConfigurationCaches(config: StrategyConfig): void {
  queryClient.setQueryData(queryKeys.configurations.detail(config.id), config);
  for (const query of queryClient
    .getQueryCache()
    .findAll({ queryKey: queryKeys.configurations.lists() })) {
    const params = getListParams(query.queryKey);
    queryClient.setQueryData<PaginatedResponse<StrategyConfig> | undefined>(
      query.queryKey,
      (cached) => patchListEntry(cached, config, params)
    );
  }
}

export function removeConfigurationCaches(id: string): void {
  queryClient.removeQueries({ queryKey: queryKeys.configurations.detail(id) });
  queryClient.removeQueries({ queryKey: queryKeys.configurations.tasks(id) });
  queryClient.setQueriesData<PaginatedResponse<StrategyConfig>>(
    { queryKey: queryKeys.configurations.lists() },
    (cached) => {
      if (!cached) {
        return cached;
      }
      const nextResults = cached.results.filter((entry) => entry.id !== id);
      if (nextResults.length === cached.results.length) {
        return cached;
      }
      return {
        ...cached,
        count: Math.max(0, cached.count - 1),
        results: nextResults,
      };
    }
  );
}
