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
  refetch: () => Promise<void>;
}

interface UseConfigurationResult {
  data: StrategyConfig | null;
  isLoading: boolean;
  error: Error | null;
  refetch: () => Promise<void>;
}

interface UseConfigurationTasksResult {
  data: ConfigurationTask[] | null;
  isLoading: boolean;
  error: Error | null;
  refetch: () => Promise<void>;
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
    refetch: async () => {
      await query.refetch();
    },
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
    refetch: async () => {
      await query.refetch();
    },
  };
}

export function useConfigurationTasks(id: string): UseConfigurationTasksResult {
  const query = useQuery({
    queryKey: queryKeys.configurations.tasks(id),
    queryFn: () => configurationsApi.getTasks(String(id)),
    enabled: Boolean(id),
  });

  return {
    data: query.data ?? null,
    isLoading: query.isLoading,
    error: (query.error as Error | null) ?? null,
    refetch: async () => {
      await query.refetch();
    },
  };
}
