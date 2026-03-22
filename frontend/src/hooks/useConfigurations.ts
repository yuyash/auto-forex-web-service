import { useQuery } from '@tanstack/react-query';
import { queryKeys } from '../config/reactQuery';
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
  refresh: () => Promise<unknown>;
  refetch: () => Promise<unknown>;
}

interface UseConfigurationResult {
  data: StrategyConfig | null;
  isLoading: boolean;
  error: Error | null;
  refresh: () => Promise<unknown>;
  refetch: () => Promise<unknown>;
}

interface UseConfigurationTasksResult {
  data: ConfigurationTask[] | null;
  isLoading: boolean;
  error: Error | null;
  refresh: () => Promise<unknown>;
  refetch: () => Promise<unknown>;
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
    refresh: () => query.refetch(),
    refetch: () => query.refetch(),
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
    refresh: () => (id ? query.refetch() : Promise.resolve()),
    refetch: () => (id ? query.refetch() : Promise.resolve()),
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
    refresh: () => query.refetch(),
    refetch: () => query.refetch(),
  };
}
