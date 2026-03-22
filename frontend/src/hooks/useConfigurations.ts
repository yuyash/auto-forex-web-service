import { useQuery } from '@tanstack/react-query';
import { queryKeys } from '../config/reactQuery';
import { configurationsApi } from '../services/api';
import type {
  ConfigurationTask,
  PaginatedResponse,
  StrategyConfig,
  StrategyConfigListParams,
} from '../types';
import {
  toQueryStateResult,
  type QueryStateResult,
} from './useTaskCollections';

type UseConfigurationsResult = QueryStateResult<
  PaginatedResponse<StrategyConfig>
>;
type UseConfigurationResult = QueryStateResult<StrategyConfig>;
type UseConfigurationTasksResult = QueryStateResult<ConfigurationTask[]>;

export function useConfigurations(
  params?: StrategyConfigListParams
): UseConfigurationsResult {
  const query = useQuery({
    queryKey: queryKeys.configurations.list(params),
    queryFn: () => configurationsApi.list(params),
  });
  return toQueryStateResult({
    ...query,
    refetch: () => query.refetch(),
  });
}

export function useConfiguration(id?: string): UseConfigurationResult {
  const query = useQuery({
    queryKey: id
      ? queryKeys.configurations.detail(id)
      : ['configuration', 'empty'],
    queryFn: () => configurationsApi.get(id!),
    enabled: Boolean(id),
  });
  return toQueryStateResult({
    ...query,
    refetch: () => (id ? query.refetch() : Promise.resolve()),
  });
}

export function useConfigurationTasks(
  id: string,
  options?: { enabled?: boolean }
): UseConfigurationTasksResult {
  const query = useQuery({
    queryKey: queryKeys.configurations.tasks(id),
    queryFn: () => configurationsApi.getTasks(String(id)),
    enabled: Boolean(id) && options?.enabled !== false,
  });
  return toQueryStateResult({
    ...query,
    refetch: () => query.refetch(),
  });
}
