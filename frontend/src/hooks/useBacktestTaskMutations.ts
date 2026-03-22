import { queryClient, queryKeys } from '../config/reactQuery';
import { backtestTasksApi } from '../services/api';
import type {
  BacktestTask,
  BacktestTaskCopyData,
  BacktestTaskCreateData,
  BacktestTaskUpdateData,
} from '../types';
import {
  invalidateTaskDerivedCaches,
  patchTaskStatusCache,
  removeTaskCaches,
  upsertTaskCaches,
} from './taskMutationCache';
import { useWrappedMutation } from './useWrappedMutation';

async function invalidateBacktestQueries(taskId?: string): Promise<void> {
  await queryClient.invalidateQueries({
    queryKey: queryKeys.backtestTasks.lists(),
  });
  if (taskId) {
    await invalidateTaskDerivedCaches('backtest', taskId);
  }
}

export function useCreateBacktestTask(options?: {
  onSuccess?: (data: BacktestTask) => void;
  onError?: (error: Error) => void;
}) {
  return useWrappedMutation(
    (variables: BacktestTaskCreateData) => backtestTasksApi.create(variables),
    {
      onSuccess: async (data) => {
        upsertTaskCaches('backtest', data);
        await invalidateBacktestQueries(data.id);
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
      onSuccess: async (data) => {
        upsertTaskCaches('backtest', data);
        await invalidateTaskDerivedCaches('backtest', data.id);
        options?.onSuccess?.(data);
      },
      onError: (error) => options?.onError?.(error),
    }
  );
}

export function useDeleteBacktestTask(options?: {
  onSuccess?: () => void;
  onError?: (error: Error) => void;
}) {
  return useWrappedMutation((id: string) => backtestTasksApi.delete(id), {
    onSuccess: async (_, id) => {
      removeTaskCaches('backtest', id);
      await queryClient.invalidateQueries({
        queryKey: queryKeys.backtestTasks.lists(),
      });
      options?.onSuccess?.();
    },
    onError: (error) => options?.onError?.(error),
  });
}

export function useCopyBacktestTask(options?: {
  onSuccess?: (data: BacktestTask) => void;
  onError?: (error: Error) => void;
}) {
  return useWrappedMutation(
    (variables: { id: string; data: BacktestTaskCopyData }) =>
      backtestTasksApi.copy(variables.id, variables.data),
    {
      onSuccess: async (data) => {
        upsertTaskCaches('backtest', data);
        await invalidateBacktestQueries(data.id);
        options?.onSuccess?.(data);
      },
      onError: (error) => options?.onError?.(error),
    }
  );
}

export function useStartBacktestTask(options?: {
  onSuccess?: (data: BacktestTask) => void;
  onError?: (error: Error) => void;
}) {
  return useWrappedMutation((id: string) => backtestTasksApi.start(id), {
    onSuccess: async (data) => {
      upsertTaskCaches('backtest', data);
      await invalidateTaskDerivedCaches('backtest', data.id);
      options?.onSuccess?.(data);
    },
    onError: (error) => options?.onError?.(error),
  });
}

export function useStopBacktestTask(options?: {
  onSuccess?: (data: Record<string, unknown>) => void;
  onError?: (error: Error) => void;
}) {
  return useWrappedMutation((id: string) => backtestTasksApi.stop(id), {
    onSuccess: async (data, id) => {
      patchTaskStatusCache('backtest', id, 'stopping');
      await invalidateTaskDerivedCaches('backtest', id);
      options?.onSuccess?.(data);
    },
    onError: (error) => options?.onError?.(error),
  });
}

export function useRerunBacktestTask(options?: {
  onSuccess?: (data: BacktestTask) => void;
  onError?: (error: Error) => void;
}) {
  return useWrappedMutation((id: string) => backtestTasksApi.restart(id), {
    onSuccess: async (data) => {
      upsertTaskCaches('backtest', data);
      await invalidateTaskDerivedCaches('backtest', data.id);
      options?.onSuccess?.(data);
    },
    onError: (error) => options?.onError?.(error),
  });
}

export function usePauseBacktestTask(options?: {
  onSuccess?: (data: BacktestTask) => void;
  onError?: (error: Error) => void;
}) {
  return useWrappedMutation((id: string) => backtestTasksApi.pause(id), {
    onSuccess: async (data) => {
      upsertTaskCaches('backtest', data);
      await invalidateTaskDerivedCaches('backtest', data.id);
      options?.onSuccess?.(data);
    },
    onError: (error) => options?.onError?.(error),
  });
}

export function useResumeBacktestTask(options?: {
  onSuccess?: (data: BacktestTask) => void;
  onError?: (error: Error) => void;
}) {
  return useWrappedMutation((id: string) => backtestTasksApi.resume(id), {
    onSuccess: async (data) => {
      upsertTaskCaches('backtest', data);
      await invalidateTaskDerivedCaches('backtest', data.id);
      options?.onSuccess?.(data);
    },
    onError: (error) => options?.onError?.(error),
  });
}
