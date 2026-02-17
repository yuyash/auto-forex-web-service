// Trading Task mutation hooks
import { useState, useCallback } from 'react';
import { tradingTasksApi } from '../services/api';
import { invalidateTradingTasksCache } from './useTradingTasks';
import type {
  TradingTask,
  TradingTaskCreateData,
  TradingTaskUpdateData,
  TradingTaskCopyData,
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
 * Hook to create a new trading task
 */
export function useCreateTradingTask(options?: {
  onSuccess?: (data: TradingTask) => void;
  onError?: (error: Error) => void;
}): MutationResult<TradingTask, TradingTaskCreateData> {
  const [state, setState] = useState<MutationState<TradingTask>>({
    data: null,
    isLoading: false,
    error: null,
  });

  const mutate = useCallback(
    async (variables: TradingTaskCreateData) => {
      try {
        setState({ data: null, isLoading: true, error: null });
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const result = await tradingTasksApi.create(variables as any);
        setState({ data: result, isLoading: false, error: null });
        invalidateTradingTasksCache();
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
 * Hook to update a trading task
 */
export function useUpdateTradingTask(options?: {
  onSuccess?: (data: TradingTask) => void;
  onError?: (error: Error) => void;
}): MutationResult<
  TradingTask,
  { id: number | string; data: TradingTaskUpdateData }
> {
  const [state, setState] = useState<MutationState<TradingTask>>({
    data: null,
    isLoading: false,
    error: null,
  });

  const mutate = useCallback(
    async (variables: { id: number | string; data: TradingTaskUpdateData }) => {
      try {
        setState({ data: null, isLoading: true, error: null });
        const result = await tradingTasksApi.update(
          variables.id,
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          variables.data as any
        );
        setState({ data: result, isLoading: false, error: null });
        invalidateTradingTasksCache();
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
 * Hook to delete a trading task
 */
export function useDeleteTradingTask(options?: {
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
        await tradingTasksApi.delete(id);
        setState({ data: undefined, isLoading: false, error: null });
        invalidateTradingTasksCache();
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
 * Hook to copy a trading task
 */
export function useCopyTradingTask(options?: {
  onSuccess?: (data: TradingTask) => void;
  onError?: (error: Error) => void;
}): MutationResult<
  TradingTask,
  { id: number | string; data: TradingTaskCopyData }
> {
  const [state, setState] = useState<MutationState<TradingTask>>({
    data: null,
    isLoading: false,
    error: null,
  });

  const mutate = useCallback(
    async (variables: { id: number | string; data: TradingTaskCopyData }) => {
      try {
        setState({ data: null, isLoading: true, error: null });
        const result = await tradingTasksApi.copy(variables.id, variables.data);
        setState({ data: result, isLoading: false, error: null });
        invalidateTradingTasksCache();
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
 * Hook to start a trading task
 */
export function useStartTradingTask(options?: {
  onSuccess?: (data: TradingTask) => void;
  onError?: (error: Error) => void;
}): MutationResult<TradingTask, number | string> {
  const [state, setState] = useState<MutationState<TradingTask>>({
    data: null,
    isLoading: false,
    error: null,
  });

  const mutate = useCallback(
    async (id: number | string) => {
      try {
        setState({ data: null, isLoading: true, error: null });
        const result = await tradingTasksApi.start(id);
        setState({ data: result, isLoading: false, error: null });
        invalidateTradingTasksCache();
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
 * Stop mode options for trading tasks
 */
export type StopMode = 'immediate' | 'graceful' | 'graceful_close';

/**
 * Hook to stop a trading task
 */
export function useStopTradingTask(options?: {
  onSuccess?: (data: Record<string, unknown>) => void;
  onError?: (error: Error) => void;
}): MutationResult<
  Record<string, unknown>,
  { id: number | string; mode?: StopMode }
> {
  const [state, setState] = useState<MutationState<Record<string, unknown>>>({
    data: null,
    isLoading: false,
    error: null,
  });

  const mutate = useCallback(
    async (variables: { id: number | string; mode?: StopMode }) => {
      try {
        setState({ data: null, isLoading: true, error: null });
        const result = await tradingTasksApi.stop(
          variables.id,
          variables.mode || 'graceful'
        );
        setState({ data: result, isLoading: false, error: null });
        invalidateTradingTasksCache();
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
 * Hook to pause a trading task
 */
export function usePauseTradingTask(options?: {
  onSuccess?: (data: TradingTask) => void;
  onError?: (error: Error) => void;
}): MutationResult<TradingTask, number | string> {
  const [state, setState] = useState<MutationState<TradingTask>>({
    data: null,
    isLoading: false,
    error: null,
  });

  const mutate = useCallback(
    async (id: number | string) => {
      try {
        setState({ data: null, isLoading: true, error: null });
        const result = await tradingTasksApi.pause(id);
        setState({ data: result, isLoading: false, error: null });
        invalidateTradingTasksCache();
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
 * Hook to resume a trading task
 */
export function useResumeTradingTask(options?: {
  onSuccess?: (data: TradingTask) => void;
  onError?: (error: Error) => void;
}): MutationResult<TradingTask, number | string> {
  const [state, setState] = useState<MutationState<TradingTask>>({
    data: null,
    isLoading: false,
    error: null,
  });

  const mutate = useCallback(
    async (id: number | string) => {
      try {
        setState({ data: null, isLoading: true, error: null });
        const result = await tradingTasksApi.resume(id);
        setState({ data: result, isLoading: false, error: null });
        invalidateTradingTasksCache();
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
 * Hook to rerun a trading task
 */
export function useRerunTradingTask(options?: {
  onSuccess?: (data: TradingTask) => void;
  onError?: (error: Error) => void;
}): MutationResult<TradingTask, number | string> {
  const [state, setState] = useState<MutationState<TradingTask>>({
    data: null,
    isLoading: false,
    error: null,
  });

  const mutate = useCallback(
    async (id: number | string) => {
      try {
        setState({ data: null, isLoading: true, error: null });
        const result = await tradingTasksApi.restart(id, true);
        setState({ data: result, isLoading: false, error: null });
        invalidateTradingTasksCache();
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
 * Hook to restart a trading task with fresh state
 */
export function useRestartTradingTask(options?: {
  onSuccess?: (data: TradingTask) => void;
  onError?: (error: Error) => void;
}): MutationResult<TradingTask, { id: number | string; clearState?: boolean }> {
  const [state, setState] = useState<MutationState<TradingTask>>({
    data: null,
    isLoading: false,
    error: null,
  });

  const mutate = useCallback(
    async (variables: { id: number | string; clearState?: boolean }) => {
      try {
        setState({ data: null, isLoading: true, error: null });
        const result = await tradingTasksApi.restart(
          variables.id,
          variables.clearState ?? true
        );
        setState({ data: result, isLoading: false, error: null });
        invalidateTradingTasksCache();
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
