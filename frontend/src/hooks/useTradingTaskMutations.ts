import { tradingTasksApi } from '../services/api';
import type {
  TradingTask,
  TradingTaskCreateData,
  TradingTaskUpdateData,
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

export type StopMode = 'immediate' | 'graceful' | 'graceful_close';

// --- hooks that need custom create/update logic (not generic) -------------

export function useCreateTradingTask(options?: {
  onSuccess?: (data: TradingTask) => void;
  onError?: (error: Error) => void;
}) {
  return useWrappedMutation(
    (variables: TradingTaskCreateData) =>
      tradingTasksApi.create({
        config_id: variables.config_id,
        account_id: variables.account_id,
        name: variables.name,
        description: variables.description,
        sell_on_stop: variables.sell_on_stop,
      }),
    {
      onSuccess: async (data) => {
        upsertTaskCaches('trading', data);
        patchTaskDerivedCaches('trading', data);
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
        config_id: variables.data.config,
        account_id: variables.data.account_id,
        name: variables.data.name,
        description: variables.data.description,
        sell_on_stop: variables.data.sell_on_stop,
      }),
    {
      onSuccess: async (data) => {
        upsertTaskCaches('trading', data);
        patchTaskDerivedCaches('trading', data);
        await invalidateTaskDerivedCaches('trading', data.id);
        options?.onSuccess?.(data);
      },
      onError: (error) => options?.onError?.(error),
    }
  );
}

// --- stop needs a custom status-patch + mode parameter --------------------

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

// --- lifecycle hooks via factory ------------------------------------------

export const useDeleteTradingTask = createDeleteHook<TradingTask>(
  'trading',
  tradingTasksApi
);

export const useCopyTradingTask = createCopyHook<TradingTask>(
  'trading',
  tradingTasksApi as Parameters<typeof createCopyHook<TradingTask>>[1]
);

export const useStartTradingTask = createStartHook<TradingTask>(
  'trading',
  tradingTasksApi
);

export const usePauseTradingTask = createPauseHook<TradingTask>(
  'trading',
  tradingTasksApi
);

export const useResumeTradingTask = createResumeHook<TradingTask>(
  'trading',
  tradingTasksApi
);

export const useRestartTradingTask = createRestartHook<TradingTask>(
  'trading',
  tradingTasksApi
);
