/**
 * Trading Task API service using direct axios calls.
 */

import { api } from '../../api/apiClient';
import { withRetry } from '../../api/client';
import type {
  TradingTaskRequest,
  PatchedTradingTaskCreateRequest,
  PaginatedApiResponse,
} from '../../api/types';
import type {
  TradingTask,
  TradingTaskListParams,
  PaginatedResponse,
} from '../../types';
import type {
  ExecutionMetricsCheckpoint,
  EquityPoint,
  Trade,
  BacktestStrategyEvent,
} from '../../types/execution';

const BASE = '/api/trading/tasks/trading';

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const toLocal = (task: any): TradingTask => task as TradingTask;

export const tradingTasksApi = {
  list: async (
    params?: TradingTaskListParams
  ): Promise<PaginatedResponse<TradingTask>> => {
    const result = await withRetry(() =>
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      api.get<PaginatedApiResponse<any>>(`${BASE}/`, {
        account_id: params?.account_id ? Number(params.account_id) : undefined,
        config_id: params?.config_id,
        ordering: params?.ordering,
        page: params?.page,
        page_size: params?.page_size,
        search: params?.search,
        status: params?.status,
      })
    );
    return {
      count: result.count,
      next: result.next ?? null,
      previous: result.previous ?? null,
      results: result.results.map(toLocal),
    };
  },

  get: async (id: string): Promise<TradingTask> => {
    const result = await withRetry(() =>
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      api.get<any>(`${BASE}/${id}/`)
    );
    return toLocal(result);
  },

  create: async (data: TradingTaskRequest): Promise<TradingTask> => {
    const result = await withRetry(() =>
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      api.post<any>(`${BASE}/`, data)
    );
    return toLocal(result);
  },

  update: async (
    id: string,
    data: TradingTaskRequest
  ): Promise<TradingTask> => {
    const result = await withRetry(() =>
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      api.put<any>(`${BASE}/${id}/`, data)
    );
    return toLocal(result);
  },

  partialUpdate: async (
    id: string,
    data: PatchedTradingTaskCreateRequest
  ): Promise<TradingTask> => {
    const result = await withRetry(() =>
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      api.patch<any>(`${BASE}/${id}/`, data)
    );
    return toLocal(result);
  },

  delete: async (id: string): Promise<void> => {
    return withRetry(() => api.delete(`${BASE}/${id}/`));
  },

  start: async (id: string): Promise<TradingTask> => {
    // Do NOT use withRetry — start is not idempotent (dispatches a Celery task).
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const result = await api.post<any>(`${BASE}/${id}/start/`, {});
    return toLocal(result);
  },

  stop: async (
    id: string,
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    _mode?: 'immediate' | 'graceful' | 'graceful_close'
  ): Promise<Record<string, unknown>> => {
    // Do NOT use withRetry — stop dispatches a Celery task.
    return api.post<Record<string, unknown>>(`${BASE}/${id}/stop/`, {});
  },

  pause: async (id: string): Promise<TradingTask> => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const result = await api.post<any>(`${BASE}/${id}/pause/`, {});
    return toLocal(result);
  },

  resume: async (id: string): Promise<TradingTask> => {
    // Do NOT use withRetry — resume dispatches a Celery task.
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const result = await api.post<any>(`${BASE}/${id}/resume/`, {});
    return toLocal(result);
  },

  restart: async (
    id: string,
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    _clearState?: boolean
  ): Promise<TradingTask> => {
    // Do NOT use withRetry — restart is not idempotent.
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const result = await api.post<any>(`${BASE}/${id}/restart/`, {});
    return toLocal(result);
  },

  getExecutions: async (
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    _id: string,
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    _params?: { page?: number; page_size?: number; include_metrics?: boolean }
  ): Promise<PaginatedResponse<import('../../types').TaskExecution>> => {
    return { count: 0, next: null, previous: null, results: [] };
  },

  copy: async (
    id: string,
    _data: { new_name: string }
  ): Promise<TradingTask> => {
    const original = await withRetry(() =>
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      api.get<any>(`${BASE}/${id}/`)
    );
    const result = await withRetry(() =>
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      api.post<any>(`${BASE}/`, {
        name: _data.new_name,
        config: original.config,
        oanda_account: original.oanda_account,
        description: original.description,
        sell_on_stop: original.sell_on_stop,
      })
    );
    return toLocal(result);
  },

  getMetricsCheckpoint: async (
    id: string
  ): Promise<{ checkpoint: ExecutionMetricsCheckpoint | null }> => {
    const task = await withRetry(() =>
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      api.get<any>(`${BASE}/${id}/`)
    );
    const execution = (task as unknown as TradingTask).latest_execution;
    return {
      checkpoint: execution
        ? ({
            total_return: execution.total_return,
            total_pnl: execution.total_pnl,
            total_trades: execution.total_trades,
            winning_trades: execution.winning_trades,
            losing_trades: execution.losing_trades,
            win_rate: execution.win_rate,
          } as ExecutionMetricsCheckpoint)
        : null,
    };
  },

  getEquityCurve: async (
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    _id: string
  ): Promise<{ equity_curve: EquityPoint[] }> => {
    return { equity_curve: [] };
  },

  getTradeLogs: async (
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    _id: string
  ): Promise<{ trade_logs: Trade[] }> => {
    return { trade_logs: [] };
  },

  getStrategyEvents: async (
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    _id: string
  ): Promise<{ strategy_events: BacktestStrategyEvent[] }> => {
    return { strategy_events: [] };
  },
};
