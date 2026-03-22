import { useQuery } from '@tanstack/react-query';
import { queryClient, queryKeys } from '../config/reactQuery';
import { configurationsApi } from '../services/api';
import type {
  ConfigurationTask,
  PaginatedResponse,
  StrategyConfig,
  StrategyConfigListParams,
} from '../types';

interface UseConfigurationsResult {
  data: PaginatedResponse<StrategyConfig> | null;
  isLoading: boolean;
  error: Error | null;
  refetch: () => Promise<unknown>;
}

interface UseConfigurationResult {
  data: StrategyConfig | null;
  isLoading: boolean;
  error: Error | null;
  refetch: () => Promise<unknown>;
}

interface UseConfigurationTasksResult {
  data: ConfigurationTask[] | null;
  isLoading: boolean;
  error: Error | null;
  refetch: () => Promise<unknown>;
}

interface UseAllConfigurationsResult {
  data: StrategyConfig[] | null;
  isLoading: boolean;
  error: Error | null;
  refresh: () => Promise<unknown>;
}

export function invalidateConfigurationsCache(): void {
  void queryClient.invalidateQueries({
    queryKey: queryKeys.configurations.all,
  });
}

export function useConfigurations(
  params?: StrategyConfigListParams
): UseConfigurationsResult {
  const query = useQuery({
    queryKey: queryKeys.configurations.list(params),
    queryFn: () => configurationsApi.list(params),
  });

  return {
    data: query.data ?? null,
    isLoading: query.isLoading,
    error: (query.error as Error | null) ?? null,
    refetch: () =>
      queryClient.invalidateQueries({
        queryKey: queryKeys.configurations.list(params),
      }),
  };
}

export function useConfiguration(id?: string): UseConfigurationResult {
  const query = useQuery({
    queryKey: id
      ? queryKeys.configurations.detail(id)
      : ['configuration', 'empty'],
    queryFn: () => configurationsApi.get(id!),
    enabled: Boolean(id),
  });

  return {
    data: query.data ?? null,
    isLoading: query.isLoading,
    error: (query.error as Error | null) ?? null,
    refetch: () =>
      id
        ? queryClient.invalidateQueries({
            queryKey: queryKeys.configurations.detail(id),
          })
        : Promise.resolve(),
  };
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

  return {
    data: query.data ?? null,
    isLoading: query.isLoading,
    error: (query.error as Error | null) ?? null,
    refetch: () =>
      queryClient.invalidateQueries({
        queryKey: queryKeys.configurations.tasks(id),
      }),
  };
}

export function useAllConfigurations(
  params?: Omit<StrategyConfigListParams, 'page' | 'page_size'>
): UseAllConfigurationsResult {
  const queryKey = [
    ...queryKeys.configurations.lists(),
    'all',
    params,
  ] as const;
  const query = useQuery({
    queryKey,
    queryFn: () => configurationsApi.listAll(params),
  });

  return {
    data: query.data ?? null,
    isLoading: query.isLoading,
    error: (query.error as Error | null) ?? null,
    refresh: () => queryClient.invalidateQueries({ queryKey }),
  };
}
