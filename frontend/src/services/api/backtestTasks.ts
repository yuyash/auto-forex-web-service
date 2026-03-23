import { api } from '../../api/apiClient';
import { withRetry } from '../../api/client';
import type {
  BacktestTask,
  BacktestTaskCreateData,
  BacktestTaskListParams,
  BacktestTaskUpdateData,
  PaginatedResponse,
  TaskExecution,
} from '../../types';
import type {
  BackendBacktestTask,
  BackendPaginatedBacktestTasks,
} from './contracts';
import type { PaginatedApiResponse } from './pagination';

const BASE = '/api/trading/tasks/backtest';

function toBacktestTask(task: BackendBacktestTask): BacktestTask {
  return {
    ...task,
    data_source: task.data_source as BacktestTask['data_source'],
    status: task.status as BacktestTask['status'],
    sell_at_completion: false,
    pip_size: task.pip_size ?? undefined,
    execution_id: task.execution_id ?? undefined,
    started_at: task.started_at ?? undefined,
    completed_at: task.completed_at ?? undefined,
    error_message: task.error_message ?? undefined,
  };
}

function toPaginatedResponse(
  result: BackendPaginatedBacktestTasks
): PaginatedResponse<BacktestTask> {
  return {
    count: result.count,
    next: result.next ?? null,
    previous: result.previous ?? null,
    results: result.results.map(toBacktestTask),
  };
}

export const backtestTasksApi = {
  list: async (
    params?: BacktestTaskListParams
  ): Promise<PaginatedResponse<BacktestTask>> => {
    const result = await withRetry(() =>
      api.get<BackendPaginatedBacktestTasks>(`${BASE}/`, {
        config_id: params?.config_id,
        ordering: params?.ordering,
        page: params?.page,
        page_size: params?.page_size,
        search: params?.search,
        status: params?.status,
      })
    );
    return toPaginatedResponse(result);
  },

  get: async (id: string): Promise<BacktestTask> => {
    const result = await withRetry(() =>
      api.get<BackendBacktestTask>(`${BASE}/${id}/`)
    );
    return toBacktestTask(result);
  },

  create: async (data: BacktestTaskCreateData): Promise<BacktestTask> => {
    const result = await withRetry(() =>
      api.post<BackendBacktestTask>(`${BASE}/`, data)
    );
    return toBacktestTask(result);
  },

  update: async (
    id: string,
    data: BacktestTaskCreateData
  ): Promise<BacktestTask> => {
    const result = await withRetry(() =>
      api.put<BackendBacktestTask>(`${BASE}/${id}/`, data)
    );
    return toBacktestTask(result);
  },

  partialUpdate: async (
    id: string,
    data: BacktestTaskUpdateData
  ): Promise<BacktestTask> => {
    const result = await withRetry(() =>
      api.patch<BackendBacktestTask>(`${BASE}/${id}/`, data)
    );
    return toBacktestTask(result);
  },

  delete: async (id: string): Promise<void> => {
    return withRetry(() => api.delete(`${BASE}/${id}/`));
  },

  start: async (id: string): Promise<BacktestTask> => {
    return toBacktestTask(
      await api.post<BackendBacktestTask>(`${BASE}/${id}/start/`, {})
    );
  },

  stop: async (id: string): Promise<Record<string, unknown>> => {
    return api.post<Record<string, unknown>>(`${BASE}/${id}/stop/`, {});
  },

  pause: async (id: string): Promise<BacktestTask> => {
    return toBacktestTask(
      await api.post<BackendBacktestTask>(`${BASE}/${id}/pause/`, {})
    );
  },

  resume: async (id: string): Promise<BacktestTask> => {
    return toBacktestTask(
      await api.post<BackendBacktestTask>(`${BASE}/${id}/resume/`, {})
    );
  },

  restart: async (id: string): Promise<BacktestTask> => {
    return toBacktestTask(
      await api.post<BackendBacktestTask>(`${BASE}/${id}/restart/`, {})
    );
  },

  copy: async (
    id: string,
    data: { new_name: string }
  ): Promise<BacktestTask> => {
    const original = await withRetry(() =>
      api.get<BackendBacktestTask>(`${BASE}/${id}/`)
    );
    const result = await withRetry(() =>
      api.post<BackendBacktestTask>(`${BASE}/`, {
        name: data.new_name,
        config: original.config_id,
        start_time: original.start_time,
        end_time: original.end_time,
        description: original.description,
        data_source: original.data_source,
        initial_balance: original.initial_balance,
        commission_per_trade: original.commission_per_trade,
        instrument: original.instrument,
        hedging_enabled: original.hedging_enabled,
      })
    );
    return toBacktestTask(result);
  },

  getExecutions: async (
    id: string,
    params?: { page?: number; page_size?: number; include_metrics?: boolean }
  ): Promise<PaginatedResponse<TaskExecution>> => {
    const result = await withRetry(() =>
      api.get<PaginatedApiResponse<TaskExecution>>(
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

  getExecution: async (
    id: string,
    executionId: string,
    params?: { include_metrics?: boolean }
  ): Promise<TaskExecution> => {
    return withRetry(() =>
      api.get<TaskExecution>(`${BASE}/${id}/executions/${executionId}/`, {
        include_metrics: params?.include_metrics,
      })
    );
  },
};
