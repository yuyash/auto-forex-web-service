/**
 * Backtest Task API service using generated OpenAPI client
 */

import { TradingService } from '../../api/generated/services/TradingService';
import { withRetry } from '../../api/client';
import type {
  BacktestTaskRequest,
  PatchedBacktestTaskRequest,
} from '../../api/generated';
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
        params?.status,
        params?.config_id,
        params?.ordering,
        params?.page,
        params?.page_size,
        params?.search
      )
    );
    return {
      count: result.count,
      next: result.next ?? null,
      previous: result.previous ?? null,
      results: result.results.map(toLocal),
    };
  },

  get: async (id: number | string): Promise<BacktestTask> => {
    const result = await withRetry(() =>
      TradingService.tradingTasksBacktestRetrieve(String(id))
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
    id: number | string,
    data: BacktestTaskRequest
  ): Promise<BacktestTask> => {
    const result = await withRetry(() =>
      TradingService.tradingTasksBacktestUpdate(String(id), data)
    );
    return toLocal(result);
  },

  partialUpdate: async (
    id: number | string,
    data: PatchedBacktestTaskRequest
  ): Promise<BacktestTask> => {
    const result = await withRetry(() =>
      TradingService.tradingTasksBacktestPartialUpdate(String(id), data)
    );
    return toLocal(result);
  },

  delete: async (id: number | string): Promise<void> => {
    return withRetry(() =>
      TradingService.tradingTasksBacktestDestroy(String(id))
    );
  },

  start: async (id: number | string): Promise<BacktestTask> => {
    const result = await withRetry(() =>
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      TradingService.tradingTasksBacktestStartCreate(String(id), {} as any)
    );
    return toLocal(result);
  },

  stop: async (
    id: number | string
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
  ): Promise<Record<string, any>> => {
    return withRetry(() =>
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      TradingService.tradingTasksBacktestStopCreate(String(id), {} as any)
    );
  },

  pause: async (id: number | string): Promise<BacktestTask> => {
    const result = await withRetry(() =>
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      TradingService.tradingTasksBacktestPauseCreate(String(id), {} as any)
    );
    return toLocal(result);
  },

  resume: async (id: number | string): Promise<BacktestTask> => {
    const result = await withRetry(() =>
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      TradingService.tradingTasksBacktestResumeCreate(String(id), {} as any)
    );
    return toLocal(result);
  },

  restart: async (
    id: number | string,
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    _clearState?: boolean
  ): Promise<BacktestTask> => {
    const result = await withRetry(() =>
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      TradingService.tradingTasksBacktestRestartCreate(String(id), {} as any)
    );
    return toLocal(result);
  },

  copy: async (
    id: number | string,

    _data: { new_name: string }
  ): Promise<BacktestTask> => {
    const original = await withRetry(() =>
      TradingService.tradingTasksBacktestRetrieve(String(id))
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
    _id: number | string,
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    _params?: { page?: number; page_size?: number; include_metrics?: boolean }
  ): Promise<PaginatedResponse<import('../../types').TaskExecution>> => {
    // Executions are not yet supported in the generated API
    // Return empty paginated response
    return { count: 0, next: null, previous: null, results: [] };
  },
};
