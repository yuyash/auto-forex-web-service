import { configurationsApi } from '../services/api';
import type {
  StrategyConfig,
  StrategyConfigCreateData,
  StrategyConfigUpdateData,
} from '../types';
import {
  removeConfigurationCaches,
  upsertConfigurationCaches,
} from './configurationMutationCache';
import { useWrappedMutation } from './useWrappedMutation';

export function useCreateConfiguration(options?: {
  onSuccess?: (data: StrategyConfig) => void;
  onError?: (error: Error) => void;
}) {
  return useWrappedMutation(
    (variables: StrategyConfigCreateData) =>
      configurationsApi.create(variables),
    {
      onSuccess: async (data) => {
        upsertConfigurationCaches(data);
        options?.onSuccess?.(data);
      },
      onError: (error) => options?.onError?.(error),
    }
  );
}

export function useUpdateConfiguration(options?: {
  onSuccess?: (data: StrategyConfig) => void;
  onError?: (error: Error) => void;
}) {
  return useWrappedMutation(
    (variables: { id: string; data: StrategyConfigUpdateData }) =>
      configurationsApi.update(variables.id, variables.data),
    {
      onSuccess: async (data, variables) => {
        upsertConfigurationCaches({ ...data, id: variables.id });
        options?.onSuccess?.(data);
      },
      onError: (error) => options?.onError?.(error),
    }
  );
}

export function useDeleteConfiguration(options?: {
  onSuccess?: () => void;
  onError?: (error: Error) => void;
}) {
  return useWrappedMutation((id: string) => configurationsApi.delete(id), {
    onSuccess: async (_, id) => {
      removeConfigurationCaches(id);
      options?.onSuccess?.();
    },
    onError: (error) => options?.onError?.(error),
  });
}

export function useConfigurationMutations() {
  const createMutation = useCreateConfiguration();
  const updateMutation = useUpdateConfiguration();
  const deleteMutation = useDeleteConfiguration();

  return {
    createConfiguration: createMutation.mutate,
    isCreating: createMutation.isLoading,
    createError: createMutation.error,
    updateConfiguration: updateMutation.mutate,
    isUpdating: updateMutation.isLoading,
    updateError: updateMutation.error,
    deleteConfiguration: deleteMutation.mutate,
    isDeleting: deleteMutation.isLoading,
    deleteError: deleteMutation.error,
  };
}
