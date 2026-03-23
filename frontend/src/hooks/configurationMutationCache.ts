import { queryClient, queryKeys } from '../config/reactQuery';
import type { PaginatedResponse, StrategyConfig } from '../types';
import {
  patchListQueries,
  removePaginatedEntity,
  removeFromListQueries,
  upsertFilteredPaginatedEntity,
} from './listCacheUtils';
import {
  matchesEntityFilterSpec,
  type EntityFilterSpec,
} from './listFilterUtils';

const CONFIGURATION_LIST_FILTER_SPEC: EntityFilterSpec<StrategyConfig> = {
  exact: [
    {
      key: 'strategy_type',
      value: (config) => config.strategy_type,
    },
  ],
  search: {
    haystack: (config) => [
      config.name,
      config.description,
      config.strategy_type,
    ],
  },
};

export function upsertConfigurationCaches(config: StrategyConfig): void {
  queryClient.setQueryData(queryKeys.configurations.detail(config.id), config);
  patchListQueries<PaginatedResponse<StrategyConfig>>(
    queryKeys.configurations.lists(),
    (cached, params) =>
      upsertFilteredPaginatedEntity(cached, config, params, {
        matches: (entry, queryParams) =>
          matchesEntityFilterSpec(
            queryParams,
            entry,
            CONFIGURATION_LIST_FILTER_SPEC
          ),
      })
  );
  void queryClient.invalidateQueries({
    queryKey: queryKeys.configurations.lists(),
  });
}

export function removeConfigurationCaches(id: string): void {
  queryClient.removeQueries({ queryKey: queryKeys.configurations.detail(id) });
  queryClient.removeQueries({ queryKey: queryKeys.configurations.tasks(id) });
  removeFromListQueries<PaginatedResponse<StrategyConfig>>(
    queryKeys.configurations.lists(),
    (cached) => removePaginatedEntity(cached, id)
  );
  void queryClient.invalidateQueries({
    queryKey: queryKeys.configurations.lists(),
  });
}

export function clearConfigurationTasksCache(id: string): void {
  queryClient.removeQueries({ queryKey: queryKeys.configurations.tasks(id) });
}
