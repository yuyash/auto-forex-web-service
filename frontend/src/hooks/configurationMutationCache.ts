import { queryClient, queryKeys } from '../config/reactQuery';
import type { PaginatedResponse, StrategyConfig } from '../types';
import {
  patchListQueries,
  removePaginatedEntity,
  removeFromListQueries,
  upsertPaginatedEntity,
} from './listCacheUtils';

type ConfigListParams = Record<string, unknown> | undefined;

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
  return upsertPaginatedEntity(cached, config, {
    matches: matchesConfigurationFilter(config, params),
    page: Number(params?.page ?? 1),
  });
}

export function upsertConfigurationCaches(config: StrategyConfig): void {
  queryClient.setQueryData(queryKeys.configurations.detail(config.id), config);
  patchListQueries<PaginatedResponse<StrategyConfig>>(
    queryKeys.configurations.lists(),
    (cached, params) => patchListEntry(cached, config, params)
  );
}

export function removeConfigurationCaches(id: string): void {
  queryClient.removeQueries({ queryKey: queryKeys.configurations.detail(id) });
  queryClient.removeQueries({ queryKey: queryKeys.configurations.tasks(id) });
  removeFromListQueries<PaginatedResponse<StrategyConfig>>(
    queryKeys.configurations.lists(),
    (cached) => removePaginatedEntity(cached, id)
  );
}

export function clearConfigurationTasksCache(id: string): void {
  queryClient.removeQueries({ queryKey: queryKeys.configurations.tasks(id) });
}
