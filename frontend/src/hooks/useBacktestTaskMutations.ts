// Backtest Task mutation hooks
import { useState, useCallback } from 'react';
import { backtestTasksApi } from '../services/api';
import { invalidateBacktestTasksCache } from './useBacktestTasks';
import type {
  BacktestTask,
  BacktestTaskCreateData,
  BacktestTaskUpdateData,
  BacktestTaskCopyData,
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
 * Hook to create a new backtest task
 */
export function useCreateBacktestTask(options?: {
  onSuccess?: (data: BacktestTask) => void;
  onError?: (error: Error) => void;
}): MutationResult<BacktestTask, BacktestTaskCreateData> {
  const [state, setState] = useState<MutationState<BacktestTask>>({
    data: null,
    isLoading: false,
    error: null,
  });

  const mutate = useCallback(
    async (variables: BacktestTaskCreateData) => {
      try {
        setState({ data: null, isLoading: true, error: null });
        const result = await backtestTasksApi.create(variables);
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

  return { ...state, mutate, reset };
}

/**
 * Hook to update a backtest task
 */
export function useUpdateBacktestTask(options?: {
  onSuccess?: (data: BacktestTask) => void;
  onError?: (error: Error) => void;
}): MutationResult<BacktestTask, { id: number; data: BacktestTaskUpdateData }> {
  const [state, setState] = useState<MutationState<BacktestTask>>({
    data: null,
    isLoading: false,
    error: null,
  });

  const mutate = useCallback(
    async (variables: { id: number; data: BacktestTaskUpdateData }) => {
      try {
        setState({ data: null, isLoading: true, error: null });
        const result = await backtestTasksApi.update(
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

  return { ...state, mutate, reset };
}

/**
 * Hook to delete a backtest task
 */
export function useDeleteBacktestTask(options?: {
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
        await backtestTasksApi.delete(id);
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

  return { ...state, mutate, reset };
}

/**
 * Hook to copy a backtest task
 */
export function useCopyBacktestTask(options?: {
  onSuccess?: (data: BacktestTask) => void;
  onError?: (error: Error) => void;
}): MutationResult<BacktestTask, { id: number; data: BacktestTaskCopyData }> {
  const [state, setState] = useState<MutationState<BacktestTask>>({
    data: null,
    isLoading: false,
    error: null,
  });

  const mutate = useCallback(
    async (variables: { id: number; data: BacktestTaskCopyData }) => {
      try {
        setState({ data: null, isLoading: true, error: null });
        const result = await backtestTasksApi.copy(
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

  return { ...state, mutate, reset };
}

/**
 * Hook to start a backtest task
 */
export function useStartBacktestTask(options?: {
  onSuccess?: (data: { execution_id: number; message: string }) => void;
  onError?: (error: Error) => void;
}): MutationResult<{ execution_id: number; message: string }, number> {
  const [state, setState] = useState<
    MutationState<{ execution_id: number; message: string }>
  >({
    data: null,
    isLoading: false,
    error: null,
  });

  const mutate = useCallback(
    async (id: number) => {
      try {
        setState({ data: null, isLoading: true, error: null });
        const result = await backtestTasksApi.start(id);
        setState({ data: result, isLoading: false, error: null });
        // Invalidate cache to force refetch
        invalidateBacktestTasksCache();
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

  return { ...state, mutate, reset };
}

/**
 * Hook to stop a backtest task
 */
export function useStopBacktestTask(options?: {
  onSuccess?: (data: { message: string }) => void;
  onError?: (error: Error) => void;
}): MutationResult<{ message: string }, number> {
  const [state, setState] = useState<MutationState<{ message: string }>>({
    data: null,
    isLoading: false,
    error: null,
  });

  const mutate = useCallback(
    async (id: number) => {
      try {
        setState({ data: null, isLoading: true, error: null });
        const result = await backtestTasksApi.stop(id);
        setState({ data: result, isLoading: false, error: null });
        // Invalidate cache to force refetch
        invalidateBacktestTasksCache();
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

  return { ...state, mutate, reset };
}

/**
 * Hook to rerun a backtest task
 */
export function useRerunBacktestTask(options?: {
  onSuccess?: (data: { execution_id: number; message: string }) => void;
  onError?: (error: Error) => void;
}): MutationResult<{ execution_id: number; message: string }, number> {
  const [state, setState] = useState<
    MutationState<{ execution_id: number; message: string }>
  >({
    data: null,
    isLoading: false,
    error: null,
  });

  const mutate = useCallback(
    async (id: number) => {
      try {
        setState({ data: null, isLoading: true, error: null });
        const result = await backtestTasksApi.rerun(id);
        setState({ data: result, isLoading: false, error: null });
        // Invalidate cache to force refetch
        invalidateBacktestTasksCache();
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

  return { ...state, mutate, reset };
}
