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
import type { PatchedBacktestTaskRequest } from '../api/generated';

interface MutationState<T> {
  data: T | null;
  isLoading: boolean;
  error: Error | null;
}

interface MutationResult<TData, TVariables> extends MutationState<TData> {
  mutate: (variables: TVariables) => Promise<TData>;
  reset: () => void;
}

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
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const result = await backtestTasksApi.create(variables as any);
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

export function useUpdateBacktestTask(options?: {
  onSuccess?: (data: BacktestTask) => void;
  onError?: (error: Error) => void;
}): MutationResult<
  BacktestTask,
  { id: number | string; data: BacktestTaskUpdateData }
> {
  const [state, setState] = useState<MutationState<BacktestTask>>({
    data: null,
    isLoading: false,
    error: null,
  });

  const mutate = useCallback(
    async (variables: {
      id: number | string;
      data: BacktestTaskUpdateData;
    }) => {
      try {
        setState({ data: null, isLoading: true, error: null });

        const result = await backtestTasksApi.partialUpdate(
          variables.id,
          variables.data as PatchedBacktestTaskRequest
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

export function useDeleteBacktestTask(options?: {
  onSuccess?: () => void;
  onError?: (error: Error) => void;
}): MutationResult<void, number | string> {
  const [state, setState] = useState<MutationState<void>>({
    data: null,
    isLoading: false,
    error: null,
  });

  const mutate = useCallback(
    async (id: number | string) => {
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

export function useCopyBacktestTask(options?: {
  onSuccess?: (data: BacktestTask) => void;
  onError?: (error: Error) => void;
}): MutationResult<
  BacktestTask,
  { id: number | string; data: BacktestTaskCopyData }
> {
  const [state, setState] = useState<MutationState<BacktestTask>>({
    data: null,
    isLoading: false,
    error: null,
  });

  const mutate = useCallback(
    async (variables: { id: number | string; data: BacktestTaskCopyData }) => {
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

export function useStartBacktestTask(options?: {
  onSuccess?: (data: BacktestTask) => void;
  onError?: (error: Error) => void;
}): MutationResult<BacktestTask, number | string> {
  const [state, setState] = useState<MutationState<BacktestTask>>({
    data: null,
    isLoading: false,
    error: null,
  });

  const mutate = useCallback(
    async (id: number | string) => {
      try {
        setState({ data: null, isLoading: true, error: null });
        const result = await backtestTasksApi.start(id);
        setState({ data: result, isLoading: false, error: null });
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

export function useStopBacktestTask(options?: {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  onSuccess?: (data: Record<string, any>) => void;
  onError?: (error: Error) => void;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
}): MutationResult<Record<string, any>, number | string> {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [state, setState] = useState<MutationState<Record<string, any>>>({
    data: null,
    isLoading: false,
    error: null,
  });

  const mutate = useCallback(
    async (id: number | string) => {
      try {
        setState({ data: null, isLoading: true, error: null });
        const result = await backtestTasksApi.stop(id);
        setState({ data: result, isLoading: false, error: null });
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

export function useRerunBacktestTask(options?: {
  onSuccess?: (data: BacktestTask) => void;
  onError?: (error: Error) => void;
}): MutationResult<BacktestTask, number | string> {
  const [state, setState] = useState<MutationState<BacktestTask>>({
    data: null,
    isLoading: false,
    error: null,
  });

  const mutate = useCallback(
    async (id: number | string) => {
      try {
        setState({ data: null, isLoading: true, error: null });
        const result = await backtestTasksApi.start(id);
        setState({ data: result, isLoading: false, error: null });
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
