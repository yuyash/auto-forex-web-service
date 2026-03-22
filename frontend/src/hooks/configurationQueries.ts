import type { UseQueryOptions } from '@tanstack/react-query';
import { queryKeys } from '../config/reactQuery';
import { configurationsApi } from '../services/api';
import type {
  ConfigurationTask,
  PaginatedResponse,
  StrategyConfig,
  StrategyConfigListParams,
} from '../types';

export function createConfigurationsQuery(
  params?: StrategyConfigListParams
): UseQueryOptions<PaginatedResponse<StrategyConfig>> {
  return {
    queryKey: queryKeys.configurations.list(params),
    queryFn: () => configurationsApi.list(params),
  };
}

export function createConfigurationQuery(
  id?: string
): UseQueryOptions<StrategyConfig> {
  return {
    queryKey: id
      ? queryKeys.configurations.detail(id)
      : ['configuration', 'empty'],
    queryFn: () => configurationsApi.get(id!),
    enabled: Boolean(id),
  };
}

export function createConfigurationTasksQuery(
  id: string,
  options?: { enabled?: boolean }
): UseQueryOptions<ConfigurationTask[]> {
  return {
    queryKey: queryKeys.configurations.tasks(id),
    queryFn: () => configurationsApi.getTasks(String(id)),
    enabled: Boolean(id) && options?.enabled !== false,
  };
}
