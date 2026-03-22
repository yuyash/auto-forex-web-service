import { queryClient, queryKeys } from '../config/reactQuery';
import type { PaginatedResponse, StrategyConfig } from '../types';
import {
  patchListQueries,
  removePaginatedEntity,
  removeFromListQueries,
  upsertFilteredPaginatedEntity,
} from './listCacheUtils';
import { matchesExactFilter, matchesSearchFilter } from './listFilterUtils';

type ConfigListParams = Record<string, unknown> | undefined;

function matchesConfigurationFilter(
  config: StrategyConfig,
  params?: ConfigListParams
): boolean {
  if (!matchesExactFilter(params, 'strategy_type', config.strategy_type)) {
    return false;
  }
  if (
    !matchesSearchFilter(params, [
      config.name,
      config.description,
      config.strategy_type,
    ])
  ) {
    return false;
  }

  return true;
}

export function upsertConfigurationCaches(config: StrategyConfig): void {
  queryClient.setQueryData(queryKeys.configurations.detail(config.id), config);
  patchListQueries<PaginatedResponse<StrategyConfig>>(
    queryKeys.configurations.lists(),
    (cached, params) =>
      upsertFilteredPaginatedEntity(cached, config, params, {
        matches: matchesConfigurationFilter,
      })
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
