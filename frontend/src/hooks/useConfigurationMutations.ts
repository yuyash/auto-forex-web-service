// Configuration mutation hooks
import { useState, useCallback } from 'react';
import { configurationsApi } from '../services/api';
import type {
  StrategyConfig,
  StrategyConfigCreateData,
  StrategyConfigUpdateData,
} from '../types';

interface MutationState<T> {
  data: T | null;
  isLoading: boolean;
  error: Error | null;
}

interface MutationResult<TData, TVariables> extends MutationState<TData> {
  mutate: (variables: TVariables) => Promise<TData>;
  reset: () => void;
}

/**
 * Hook to create a new configuration
 */
export function useCreateConfiguration(options?: {
  onSuccess?: (data: StrategyConfig) => void;
  onError?: (error: Error) => void;
}): MutationResult<StrategyConfig, StrategyConfigCreateData> {
  const [state, setState] = useState<MutationState<StrategyConfig>>({
    data: null,
    isLoading: false,
    error: null,
  });

  const mutate = useCallback(
    async (variables: StrategyConfigCreateData) => {
      try {
        setState({ data: null, isLoading: true, error: null });
        const result = await configurationsApi.create(variables);
        setState({ data: result, isLoading: false, error: null });
        options?.onSuccess?.(result);
        return result;
      } catch (err) {
        const error = err as Error;
        setState({ data: null, isLoading: false, error });
        options?.onError?.(error);
        throw error;
      }
    },
    [options]
  );

  const reset = useCallback(() => {
    setState({ data: null, isLoading: false, error: null });
  }, []);

  return {
    ...state,
    mutate,
    reset,
  };
}

/**
 * Hook to update a configuration
 */
export function useUpdateConfiguration(options?: {
  onSuccess?: (data: StrategyConfig) => void;
  onError?: (error: Error) => void;
}): MutationResult<
  StrategyConfig,
  { id: number; data: StrategyConfigUpdateData }
> {
  const [state, setState] = useState<MutationState<StrategyConfig>>({
    data: null,
    isLoading: false,
    error: null,
  });

  const mutate = useCallback(
    async (variables: { id: number; data: StrategyConfigUpdateData }) => {
      try {
        setState({ data: null, isLoading: true, error: null });
        const result = await configurationsApi.update(
          variables.id,
          variables.data
        );
        setState({ data: result, isLoading: false, error: null });
        options?.onSuccess?.(result);
        return result;
      } catch (err) {
        const error = err as Error;
        setState({ data: null, isLoading: false, error });
        options?.onError?.(error);
        throw error;
      }
    },
    [options]
  );

  const reset = useCallback(() => {
    setState({ data: null, isLoading: false, error: null });
  }, []);

  return {
    ...state,
    mutate,
    reset,
  };
}

/**
 * Hook to delete a configuration
 */
export function useDeleteConfiguration(options?: {
  onSuccess?: () => void;
  onError?: (error: Error) => void;
}): MutationResult<void, number> {
  const [state, setState] = useState<MutationState<void>>({
    data: null,
    isLoading: false,
    error: null,
  });

  const mutate = useCallback(
    async (id: number) => {
      try {
        setState({ data: null, isLoading: true, error: null });
        await configurationsApi.delete(id);
        setState({ data: undefined, isLoading: false, error: null });
        options?.onSuccess?.();
      } catch (err) {
        const error = err as Error;
        setState({ data: null, isLoading: false, error });
        options?.onError?.(error);
        throw error;
      }
    },
    [options]
  );

  const reset = useCallback(() => {
    setState({ data: null, isLoading: false, error: null });
  }, []);

  return {
    ...state,
    mutate,
    reset,
  };
}

/**
 * Combined hook for all configuration mutations
 */
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
