/**
 * Generic factory for task mutation hooks.
 *
 * Both backtest and trading tasks share identical cache-invalidation patterns.
 * This factory eliminates the duplication by parameterising on task kind and
 * the concrete API object.
 */
import type { BackendTaskStopResponse } from '../services/api/contracts';
import type { BacktestTask, TradingTask } from '../types';
import {
  invalidateTaskDerivedCaches,
  patchTaskDerivedCaches,
  removeTaskCaches,
  removeTaskListEntry,
  upsertTaskCaches,
} from './taskMutationCache';
import { useWrappedMutation } from './useWrappedMutation';

// ---- shared types --------------------------------------------------------

type TaskEntity = BacktestTask | TradingTask;
type TaskKind = 'backtest' | 'trading';

interface MutationOptions<T> {
  onSuccess?: (data: T) => void;
  onError?: (error: Error) => void;
}

/** Minimal contract every task API must satisfy for the lifecycle hooks. */
interface TaskLifecycleApi<TTask extends TaskEntity> {
  start: (id: string) => Promise<TTask>;
  stop: (...args: never[]) => Promise<BackendTaskStopResponse>;
  pause: (id: string) => Promise<TTask>;
  resume: (id: string) => Promise<TTask>;
  restart: (id: string) => Promise<TTask>;
  delete: (id: string) => Promise<void>;
  copy: (id: string, data: { new_name: string }) => Promise<TTask>;
}

// ---- helpers -------------------------------------------------------------

/** Standard onSuccess: upsert + patch derived + invalidate. */
async function standardSuccess<TTask extends TaskEntity>(
  kind: TaskKind,
  data: TTask,
  cb?: (d: TTask) => void
): Promise<void> {
  upsertTaskCaches(kind, data);
  patchTaskDerivedCaches(kind, data);
  await invalidateTaskDerivedCaches(kind, data.id);
  cb?.(data);
}

// ---- factory -------------------------------------------------------------

export function createStartHook<TTask extends TaskEntity>(
  kind: TaskKind,
  api: TaskLifecycleApi<TTask>
) {
  return function useStartTask(options?: MutationOptions<TTask>) {
    return useWrappedMutation((id: string) => api.start(id), {
      onSuccess: async (data) => {
        await standardSuccess(kind, data, options?.onSuccess);
      },
      onError: (error) => options?.onError?.(error),
    });
  };
}

export function createPauseHook<TTask extends TaskEntity>(
  kind: TaskKind,
  api: TaskLifecycleApi<TTask>
) {
  return function usePauseTask(options?: MutationOptions<TTask>) {
    return useWrappedMutation((id: string) => api.pause(id), {
      onSuccess: async (data) => {
        await standardSuccess(kind, data, options?.onSuccess);
      },
      onError: (error) => options?.onError?.(error),
    });
  };
}

export function createResumeHook<TTask extends TaskEntity>(
  kind: TaskKind,
  api: TaskLifecycleApi<TTask>
) {
  return function useResumeTask(options?: MutationOptions<TTask>) {
    return useWrappedMutation((id: string) => api.resume(id), {
      onSuccess: async (data) => {
        await standardSuccess(kind, data, options?.onSuccess);
      },
      onError: (error) => options?.onError?.(error),
    });
  };
}

export function createRestartHook<TTask extends TaskEntity>(
  kind: TaskKind,
  api: TaskLifecycleApi<TTask>
) {
  return function useRestartTask(options?: MutationOptions<TTask>) {
    return useWrappedMutation((id: string) => api.restart(id), {
      onSuccess: async (data) => {
        await standardSuccess(kind, data, options?.onSuccess);
      },
      onError: (error) => options?.onError?.(error),
    });
  };
}

export function createDeleteHook<TTask extends TaskEntity>(
  kind: TaskKind,
  api: TaskLifecycleApi<TTask>
) {
  return function useDeleteTask(options?: MutationOptions<void>) {
    return useWrappedMutation((id: string) => api.delete(id), {
      onSuccess: async (_, id) => {
        await removeTaskCaches(kind, id);
        removeTaskListEntry(kind, id);
        options?.onSuccess?.();
      },
      onError: (error) => options?.onError?.(error),
    });
  };
}

export function createCopyHook<TTask extends TaskEntity>(
  kind: TaskKind,
  api: TaskLifecycleApi<TTask>
) {
  return function useCopyTask(options?: MutationOptions<TTask>) {
    return useWrappedMutation(
      (variables: { id: string; data: { new_name: string } }) =>
        api.copy(variables.id, variables.data),
      {
        onSuccess: async (data) => {
          await standardSuccess(kind, data, options?.onSuccess);
        },
        onError: (error) => options?.onError?.(error),
      }
    );
  };
}
