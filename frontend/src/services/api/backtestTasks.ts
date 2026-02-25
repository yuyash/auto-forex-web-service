/**
 * Backtest Task API service using direct axios calls.
 */

import { api } from '../../api/apiClient';
import { withRetry } from '../../api/client';
import type {
  BacktestTaskRequest,
  PatchedBacktestTaskCreateRequest,
  PaginatedApiResponse,
} from '../../api/types';
import type {
  BacktestTask,
  BacktestTaskListParams,
  PaginatedResponse,
} from '../../types';

const BASE = '/api/trading/tasks/backtest';

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const toLocal = (task: any): BacktestTask => task as BacktestTask;

export const backtestTasksApi = {
  list: async (
    params?: BacktestTaskListParams
  ): Promise<PaginatedResponse<BacktestTask>> => {
    const result = await withRetry(() =>
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      api.get<PaginatedApiResponse<any>>(`${BASE}/`, {
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

  get: async (id: string): Promise<BacktestTask> => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const result = await withRetry(() => api.get<any>(`${BASE}/${id}/`));
    return toLocal(result);
  },

  create: async (data: BacktestTaskRequest): Promise<BacktestTask> => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const result = await withRetry(() => api.post<any>(`${BASE}/`, data));
    return toLocal(result);
  },

  update: async (
    id: string,
    data: BacktestTaskRequest
  ): Promise<BacktestTask> => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const result = await withRetry(() => api.put<any>(`${BASE}/${id}/`, data));
    return toLocal(result);
  },

  partialUpdate: async (
    id: string,
    data: PatchedBacktestTaskCreateRequest
  ): Promise<BacktestTask> => {
    const result = await withRetry(() =>
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      api.patch<any>(`${BASE}/${id}/`, data)
    );
    return toLocal(result);
  },

  delete: async (id: string): Promise<void> => {
    return withRetry(() => api.delete(`${BASE}/${id}/`));
  },

  start: async (id: string): Promise<BacktestTask> => {
    // Do NOT use withRetry — start is not idempotent (dispatches a Celery task).
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const result = await api.post<any>(`${BASE}/${id}/start/`, {});
    return toLocal(result);
  },

  stop: async (id: string): Promise<Record<string, unknown>> => {
    // Do NOT use withRetry — stop dispatches a Celery task.
    return api.post<Record<string, unknown>>(`${BASE}/${id}/stop/`, {});
  },

  pause: async (id: string): Promise<BacktestTask> => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const result = await api.post<any>(`${BASE}/${id}/pause/`, {});
    return toLocal(result);
  },

  resume: async (id: string): Promise<BacktestTask> => {
    // Do NOT use withRetry — resume dispatches a Celery task.
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const result = await api.post<any>(`${BASE}/${id}/resume/`, {});
    return toLocal(result);
  },

  restart: async (
    id: string,
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    _clearState?: boolean
  ): Promise<BacktestTask> => {
    // Do NOT use withRetry — restart is not idempotent.
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const result = await api.post<any>(`${BASE}/${id}/restart/`, {});
    return toLocal(result);
  },

  copy: async (
    id: string,
    _data: { new_name: string }
  ): Promise<BacktestTask> => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const original = await withRetry(() => api.get<any>(`${BASE}/${id}/`));
    const result = await withRetry(() =>
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      api.post<any>(`${BASE}/`, {
        name: _data.new_name,
        config: original.config,
        start_time: original.start_time,
        end_time: original.end_time,
        description: original.description,
        data_source: original.data_source,
        initial_balance: original.initial_balance,
        commission_per_trade: original.commission_per_trade,
        instrument: original.instrument,
      })
    );
    return toLocal(result);
  },

  getExecutions: async (
    id: string,
    params?: { page?: number; page_size?: number; include_metrics?: boolean }
  ): Promise<PaginatedResponse<import('../../types').TaskExecution>> => {
    const result = await withRetry(() =>
      api.get<PaginatedApiResponse<import('../../types').TaskExecution>>(
        `${BASE}/${id}/executions/`,
        {
          page: params?.page,
          page_size: params?.page_size,
          include_metrics: params?.include_metrics,
        }
      )
    );
    return {
      count: result.count,
      next: result.next ?? null,
      previous: result.previous ?? null,
      results: result.results ?? [],
    };
  },
};
