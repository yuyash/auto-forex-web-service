import { backtestTasksApi } from '../services/api';
import type { BackendTaskStopResponse } from '../services/api/contracts';
import type {
  BacktestBalanceAdjustmentData,
  BacktestBalanceAdjustmentResult,
  BacktestTask,
  BacktestTaskCreateData,
  BacktestTaskUpdateData,
} from '../types';
import { TaskStatus, TaskType } from '../types/common';
import {
  beginTaskStatusTransition,
  clearTaskStatusTransitionByKind,
  invalidateTaskDerivedCaches,
  patchTaskDerivedCaches,
  patchTaskStatusCache,
  refreshTaskStatusCaches,
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
import { refreshTaskExecution, refreshTaskSummary } from './taskResourceCache';
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

function optimisticStopStatus(mode?: StopMode): TaskStatus {
  return mode === 'drain' ? TaskStatus.DRAINING : TaskStatus.STOPPING;
}

function stopSettleStatuses(mode?: StopMode): TaskStatus[] {
  return mode === 'drain'
    ? [
        TaskStatus.DRAINING,
        TaskStatus.STOPPING,
        TaskStatus.STOPPED,
        TaskStatus.COMPLETED,
        TaskStatus.FAILED,
      ]
    : [
        TaskStatus.STOPPING,
        TaskStatus.STOPPED,
        TaskStatus.COMPLETED,
        TaskStatus.FAILED,
      ];
}

export function useStopBacktestTask(options?: {
  onSuccess?: (data: BackendTaskStopResponse) => void;
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
      onMutate: (variables) => {
        beginTaskStatusTransition(
          'backtest',
          variables.id,
          optimisticStopStatus(variables.mode),
          stopSettleStatuses(variables.mode)
        );
      },
      onSuccess: async (data, variables) => {
        // The optimistic status depends on the stop mode: DRAIN keeps
        // the task running in DRAINING state; everything else
        // transitions to STOPPING → STOPPED.
        const fallbackStatus =
          variables.mode === 'drain' ? 'draining' : 'stopping';
        const nextStatus =
          (data.next_status ?? data.status).toLowerCase() || fallbackStatus;
        await patchTaskStatusCache('backtest', variables.id, nextStatus);
        await invalidateTaskDerivedCaches('backtest', variables.id);
        options?.onSuccess?.(data);
      },
      onError: (error, variables) => {
        clearTaskStatusTransitionByKind('backtest', variables.id);
        void refreshTaskStatusCaches('backtest', variables.id);
        options?.onError?.(error);
      },
    }
  );
}

export function useAdjustBacktestBalance(options?: {
  onSuccess?: (data: BacktestBalanceAdjustmentResult) => void;
  onError?: (error: Error) => void;
}) {
  return useWrappedMutation(
    (variables: { id: string; data: BacktestBalanceAdjustmentData }) =>
      backtestTasksApi.adjustBalance(variables.id, variables.data),
    {
      onSuccess: async (data, variables) => {
        await Promise.all([
          invalidateTaskDerivedCaches('backtest', variables.id),
          refreshTaskSummary(
            variables.id,
            TaskType.BACKTEST,
            data.execution_id
          ),
          refreshTaskExecution(
            variables.id,
            data.execution_id,
            TaskType.BACKTEST
          ),
        ]);
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
