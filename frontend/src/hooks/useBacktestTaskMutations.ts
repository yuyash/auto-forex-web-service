import { backtestTasksApi } from '../services/api';
import type {
  BacktestTask,
  BacktestTaskCreateData,
  BacktestTaskUpdateData,
} from '../types';
import {
  invalidateTaskDerivedCaches,
  patchTaskDerivedCaches,
  patchTaskStatusCache,
  upsertTaskCaches,
} from './taskMutationCache';
import {
  createCopyHook,
  createDeleteHook,
  createPauseHook,
  createRestartHook,
  createResumeHook,
  createStartHook,
} from './useTaskMutationFactory';
import { useWrappedMutation } from './useWrappedMutation';

// --- hooks that need custom create/update logic (not generic) -------------

export function useCreateBacktestTask(options?: {
  onSuccess?: (data: BacktestTask) => void;
  onError?: (error: Error) => void;
}) {
  return useWrappedMutation(
    (variables: BacktestTaskCreateData) => backtestTasksApi.create(variables),
    {
      onSuccess: async (data) => {
        upsertTaskCaches('backtest', data);
        patchTaskDerivedCaches('backtest', data);
        await invalidateTaskDerivedCaches('backtest', data.id);
        options?.onSuccess?.(data);
      },
      onError: (error) => options?.onError?.(error),
    }
  );
}

export function useUpdateBacktestTask(options?: {
  onSuccess?: (data: BacktestTask) => void;
  onError?: (error: Error) => void;
}) {
  return useWrappedMutation(
    (variables: { id: string; data: BacktestTaskUpdateData }) =>
      backtestTasksApi.partialUpdate(variables.id, variables.data),
    {
      onSuccess: async (data, variables) => {
        let nextTask = data;
        try {
          nextTask = await backtestTasksApi.get(variables.id);
        } catch {
          nextTask = data;
        }

        upsertTaskCaches('backtest', nextTask);
        patchTaskDerivedCaches('backtest', nextTask);
        await invalidateTaskDerivedCaches('backtest', nextTask.id);
        options?.onSuccess?.(nextTask);
      },
      onError: (error) => options?.onError?.(error),
    }
  );
}

// --- stop needs a custom status-patch pattern -----------------------------

export type StopMode = 'immediate' | 'graceful' | 'graceful_close' | 'drain';

export function useStopBacktestTask(options?: {
  onSuccess?: (data: Record<string, unknown>) => void;
  onError?: (error: Error) => void;
}) {
  return useWrappedMutation(
    (variables: {
      id: string;
      mode?: StopMode;
      drainDurationMinutes?: number;
    }) =>
      backtestTasksApi.stop(
        variables.id,
        variables.mode ?? 'graceful',
        variables.drainDurationMinutes
      ),
    {
      onSuccess: async (data, variables) => {
        // The optimistic status depends on the stop mode: DRAIN keeps
        // the task running in DRAINING state; everything else
        // transitions to STOPPING → STOPPED.
        const nextStatus = variables.mode === 'drain' ? 'draining' : 'stopping';
        await patchTaskStatusCache('backtest', variables.id, nextStatus);
        await invalidateTaskDerivedCaches('backtest', variables.id);
        options?.onSuccess?.(data);
      },
      onError: (error) => options?.onError?.(error),
    }
  );
}

// --- lifecycle hooks via factory ------------------------------------------

export const useDeleteBacktestTask = createDeleteHook<BacktestTask>(
  'backtest',
  backtestTasksApi
);

export const useCopyBacktestTask = createCopyHook<BacktestTask>(
  'backtest',
  backtestTasksApi as Parameters<typeof createCopyHook<BacktestTask>>[1]
);

export const useStartBacktestTask = createStartHook<BacktestTask>(
  'backtest',
  backtestTasksApi
);

export const useRerunBacktestTask = createRestartHook<BacktestTask>(
  'backtest',
  backtestTasksApi
);

export const usePauseBacktestTask = createPauseHook<BacktestTask>(
  'backtest',
  backtestTasksApi
);

export const useResumeBacktestTask = createResumeHook<BacktestTask>(
  'backtest',
  backtestTasksApi
);
