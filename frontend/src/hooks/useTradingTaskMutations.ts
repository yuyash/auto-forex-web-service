import { tradingTasksApi } from '../services/api';
import type {
  TradingTask,
  TradingTaskCopyData,
  TradingTaskCreateData,
  TradingTaskUpdateData,
} from '../types';
import {
  invalidateTaskDerivedCaches,
  patchTaskStatusCache,
  removeTaskCaches,
  removeTaskListEntry,
  upsertTaskCaches,
} from './taskMutationCache';
import { useWrappedMutation } from './useWrappedMutation';

export type StopMode = 'immediate' | 'graceful' | 'graceful_close';

export function useCreateTradingTask(options?: {
  onSuccess?: (data: TradingTask) => void;
  onError?: (error: Error) => void;
}) {
  return useWrappedMutation(
    (variables: TradingTaskCreateData) =>
      tradingTasksApi.create({
        config: variables.config_id,
        oanda_account: variables.account_id,
        name: variables.name,
        description: variables.description,
        sell_on_stop: variables.sell_on_stop,
      }),
    {
      onSuccess: async (data) => {
        upsertTaskCaches('trading', data);
        await invalidateTaskDerivedCaches('trading', data.id);
        options?.onSuccess?.(data);
      },
      onError: (error) => options?.onError?.(error),
    }
  );
}

export function useUpdateTradingTask(options?: {
  onSuccess?: (data: TradingTask) => void;
  onError?: (error: Error) => void;
}) {
  return useWrappedMutation(
    (variables: { id: string; data: TradingTaskUpdateData }) =>
      tradingTasksApi.partialUpdate(variables.id, {
        config: variables.data.config,
        oanda_account: variables.data.account_id,
        name: variables.data.name,
        description: variables.data.description,
        sell_on_stop: variables.data.sell_on_stop,
      }),
    {
      onSuccess: async (data) => {
        upsertTaskCaches('trading', data);
        await invalidateTaskDerivedCaches('trading', data.id);
        options?.onSuccess?.(data);
      },
      onError: (error) => options?.onError?.(error),
    }
  );
}

export function useDeleteTradingTask(options?: {
  onSuccess?: () => void;
  onError?: (error: Error) => void;
}) {
  return useWrappedMutation((id: string) => tradingTasksApi.delete(id), {
    onSuccess: async (_, id) => {
      removeTaskCaches('trading', id);
      removeTaskListEntry('trading', id);
      options?.onSuccess?.();
    },
    onError: (error) => options?.onError?.(error),
  });
}

export function useCopyTradingTask(options?: {
  onSuccess?: (data: TradingTask) => void;
  onError?: (error: Error) => void;
}) {
  return useWrappedMutation(
    (variables: { id: string; data: TradingTaskCopyData }) =>
      tradingTasksApi.copy(variables.id, variables.data),
    {
      onSuccess: async (data) => {
        upsertTaskCaches('trading', data);
        await invalidateTaskDerivedCaches('trading', data.id);
        options?.onSuccess?.(data);
      },
      onError: (error) => options?.onError?.(error),
    }
  );
}

export function useStartTradingTask(options?: {
  onSuccess?: (data: TradingTask) => void;
  onError?: (error: Error) => void;
}) {
  return useWrappedMutation((id: string) => tradingTasksApi.start(id), {
    onSuccess: async (data) => {
      upsertTaskCaches('trading', data);
      await invalidateTaskDerivedCaches('trading', data.id);
      options?.onSuccess?.(data);
    },
    onError: (error) => options?.onError?.(error),
  });
}

export function useStopTradingTask(options?: {
  onSuccess?: (data: Record<string, unknown>) => void;
  onError?: (error: Error) => void;
}) {
  return useWrappedMutation(
    (variables: { id: string; mode?: StopMode }) =>
      tradingTasksApi.stop(variables.id, variables.mode ?? 'graceful'),
    {
      onSuccess: async (data, variables) => {
        patchTaskStatusCache('trading', variables.id, 'stopping');
        await invalidateTaskDerivedCaches('trading', variables.id);
        options?.onSuccess?.(data);
      },
      onError: (error) => options?.onError?.(error),
    }
  );
}

export function usePauseTradingTask(options?: {
  onSuccess?: (data: TradingTask) => void;
  onError?: (error: Error) => void;
}) {
  return useWrappedMutation((id: string) => tradingTasksApi.pause(id), {
    onSuccess: async (data) => {
      upsertTaskCaches('trading', data);
      await invalidateTaskDerivedCaches('trading', data.id);
      options?.onSuccess?.(data);
    },
    onError: (error) => options?.onError?.(error),
  });
}

export function useResumeTradingTask(options?: {
  onSuccess?: (data: TradingTask) => void;
  onError?: (error: Error) => void;
}) {
  return useWrappedMutation((id: string) => tradingTasksApi.resume(id), {
    onSuccess: async (data) => {
      upsertTaskCaches('trading', data);
      await invalidateTaskDerivedCaches('trading', data.id);
      options?.onSuccess?.(data);
    },
    onError: (error) => options?.onError?.(error),
  });
}

export function useRestartTradingTask(options?: {
  onSuccess?: (data: TradingTask) => void;
  onError?: (error: Error) => void;
}) {
  return useWrappedMutation((id: string) => tradingTasksApi.restart(id), {
    onSuccess: async (data) => {
      upsertTaskCaches('trading', data);
      await invalidateTaskDerivedCaches('trading', data.id);
      options?.onSuccess?.(data);
    },
    onError: (error) => options?.onError?.(error),
  });
}
