/**
 * Backtest Task API service using generated OpenAPI client
 */

import { TradingService } from '../../api/generated/services/TradingService';
import { withRetry } from '../../api/client';
import type {
  BacktestTaskRequest,
  PatchedBacktestTaskCreateRequest,
} from '../../api/generated';

// Alias for backward compatibility after OpenAPI regeneration
type PatchedBacktestTaskRequest = PatchedBacktestTaskCreateRequest;
import type {
  BacktestTask,
  BacktestTaskListParams,
  PaginatedResponse,
} from '../../types';

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const toLocal = (task: any): BacktestTask => task as BacktestTask;

export const backtestTasksApi = {
  list: async (
    params?: BacktestTaskListParams
  ): Promise<PaginatedResponse<BacktestTask>> => {
    const result = await withRetry(() =>
      TradingService.tradingTasksBacktestList(
        params?.config_id,
        params?.ordering,
        params?.page,
        params?.page_size,
        params?.search,
        params?.status
      )
    );
    return {
      count: result.count,
      next: result.next ?? null,
      previous: result.previous ?? null,
      results: result.results.map(toLocal),
    };
  },

  get: async (id: string): Promise<BacktestTask> => {
    const result = await withRetry(() =>
      TradingService.tradingTasksBacktestRetrieve(id)
    );
    return toLocal(result);
  },

  create: async (data: BacktestTaskRequest): Promise<BacktestTask> => {
    const result = await withRetry(() =>
      TradingService.tradingTasksBacktestCreate(data)
    );
    return toLocal(result);
  },

  update: async (
    id: string,
    data: BacktestTaskRequest
  ): Promise<BacktestTask> => {
    const result = await withRetry(() =>
      TradingService.tradingTasksBacktestUpdate(id, data)
    );
    return toLocal(result);
  },

  partialUpdate: async (
    id: string,
    data: PatchedBacktestTaskRequest
  ): Promise<BacktestTask> => {
    const result = await withRetry(() =>
      TradingService.tradingTasksBacktestPartialUpdate(id, data)
    );
    return toLocal(result);
  },

  delete: async (id: string): Promise<void> => {
    return withRetry(() => TradingService.tradingTasksBacktestDestroy(id));
  },

  start: async (id: string): Promise<BacktestTask> => {
    // Do NOT use withRetry — start is not idempotent (dispatches a Celery task).
    const result = await TradingService.tradingTasksBacktestStartCreate(
      id,
      {} as Record<string, unknown>
    );
    return toLocal(result);
  },

  stop: async (id: string): Promise<Record<string, unknown>> => {
    // Do NOT use withRetry — stop dispatches a Celery task.
    return TradingService.tradingTasksBacktestStopCreate(
      id,
      {} as Record<string, unknown>
    );
  },

  pause: async (id: string): Promise<BacktestTask> => {
    const result = await TradingService.tradingTasksBacktestPauseCreate(
      id,
      {} as Record<string, unknown>
    );
    return toLocal(result);
  },

  resume: async (id: string): Promise<BacktestTask> => {
    // Do NOT use withRetry — resume dispatches a Celery task.
    const result = await TradingService.tradingTasksBacktestResumeCreate(
      id,
      {} as Record<string, unknown>
    );
    return toLocal(result);
  },

  restart: async (
    id: string,
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    _clearState?: boolean
  ): Promise<BacktestTask> => {
    // Do NOT use withRetry for restart — it is not idempotent.
    // Retrying a restart dispatches duplicate Celery tasks.
    const result = await TradingService.tradingTasksBacktestRestartCreate(
      id,
      {} as Record<string, unknown>
    );
    return toLocal(result);
  },

  copy: async (
    id: string,

    _data: { new_name: string }
  ): Promise<BacktestTask> => {
    const original = await withRetry(() =>
      TradingService.tradingTasksBacktestRetrieve(id)
    );
    const result = await withRetry(() =>
      TradingService.tradingTasksBacktestCreate({
        name: _data.new_name,
        config: original.config,
        start_time: original.start_time,
        end_time: original.end_time,
        description: original.description,
        data_source: original.data_source,
        initial_balance: original.initial_balance,
        commission_per_trade: original.commission_per_trade,
        instrument: original.instrument,
        trading_mode: original.trading_mode,
      })
    );
    return toLocal(result);
  },

  getExecutions: async (
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    _id: string,
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    _params?: { page?: number; page_size?: number; include_metrics?: boolean }
  ): Promise<PaginatedResponse<import('../../types').TaskExecution>> => {
    // Executions are not yet supported in the generated API
    // Return empty paginated response
    return { count: 0, next: null, previous: null, results: [] };
  },
};
