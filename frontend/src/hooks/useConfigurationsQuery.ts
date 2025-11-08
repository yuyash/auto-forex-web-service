// React Query hooks for strategy configurations with optimized caching
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { configurationsApi } from '../services/api';
import { queryKeys, cacheInvalidation } from '../config/reactQuery';
import type {
  StrategyConfig,
  StrategyConfigListParams,
  StrategyConfigCreateData,
  StrategyConfigUpdateData,
  PaginatedResponse,
  ConfigurationTask,
} from '../types';

/**
 * Hook to fetch list of strategy configurations with React Query
 * Features:
 * - Automatic caching with 5-minute stale time
 * - Background refetching on mount
 * - Optimistic updates on mutations
 */
export function useConfigurationsQuery(params?: StrategyConfigListParams) {
  return useQuery<PaginatedResponse<StrategyConfig>>({
    queryKey: queryKeys.configurations.list(
      params as Record<string, unknown> | undefined
    ),
    queryFn: () => configurationsApi.list(params),
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

/**
 * Hook to fetch a single strategy configuration
 * Features:
 * - Longer stale time (10 minutes) for detail views
 * - Automatic cache invalidation on updates
 */
export function useConfigurationQuery(id: number) {
  return useQuery<StrategyConfig>({
    queryKey: queryKeys.configurations.detail(id),
    queryFn: () => configurationsApi.get(id),
    staleTime: 10 * 60 * 1000, // 10 minutes
    enabled: !!id, // Only fetch if id is provided
  });
}

/**
 * Hook to fetch tasks using a configuration
 */
export function useConfigurationTasksQuery(id: number) {
  return useQuery<ConfigurationTask[]>({
    queryKey: queryKeys.configurations.tasks(id),
    queryFn: () => configurationsApi.getTasks(id),
    staleTime: 2 * 60 * 1000, // 2 minutes
    enabled: !!id,
  });
}

/**
 * Hook to create a new configuration with optimistic updates
 */
export function useCreateConfigurationMutation() {
  return useMutation({
    mutationFn: (data: StrategyConfigCreateData) =>
      configurationsApi.create(data),
    onSuccess: () => {
      // Invalidate and refetch configurations list
      cacheInvalidation.invalidateConfigurations();
    },
  });
}

/**
 * Hook to update a configuration with optimistic updates
 */
export function useUpdateConfigurationMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      id,
      data,
    }: {
      id: number;
      data: StrategyConfigUpdateData;
    }) => configurationsApi.update(id, data),
    onMutate: async ({ id, data }) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries({
        queryKey: queryKeys.configurations.detail(id),
      });

      // Snapshot previous value
      const previousConfig = queryClient.getQueryData<StrategyConfig>(
        queryKeys.configurations.detail(id)
      );

      // Optimistically update cache
      if (previousConfig) {
        queryClient.setQueryData<StrategyConfig>(
          queryKeys.configurations.detail(id),
          {
            ...previousConfig,
            ...data,
            updated_at: new Date().toISOString(),
          }
        );
      }

      return { previousConfig };
    },
    onError: (_err, { id }, context) => {
      // Rollback on error
      if (context?.previousConfig) {
        queryClient.setQueryData(
          queryKeys.configurations.detail(id),
          context.previousConfig
        );
      }
    },
    onSettled: (_data, _error, { id }) => {
      // Refetch to ensure consistency
      cacheInvalidation.invalidateConfiguration(id);
      cacheInvalidation.invalidateConfigurations();
    },
  });
}

/**
 * Hook to delete a configuration
 */
export function useDeleteConfigurationMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: number) => configurationsApi.delete(id),
    onSuccess: (_data, id) => {
      // Remove from cache
      queryClient.removeQueries({
        queryKey: queryKeys.configurations.detail(id),
      });
      // Invalidate list
      cacheInvalidation.invalidateConfigurations();
    },
  });
}
