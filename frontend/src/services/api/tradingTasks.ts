import { api } from '../../api/apiClient';
import { withRetry } from '../../api/client';
import type {
  PaginatedResponse,
  TaskExecution,
  TradingTask,
  TradingTaskListParams,
} from '../../types';
import type {
  ExecutionMetricsCheckpoint,
  EquityPoint,
  Trade,
  BacktestStrategyEvent,
} from '../../types/execution';
import type {
  BackendPaginatedTradingTasks,
  BackendTradingTask,
} from './contracts';
import type { PaginatedApiResponse } from './pagination';

const BASE = '/api/trading/tasks/trading';

interface TradingTaskCreateRequest {
  config: string;
  oanda_account: string;
  name: string;
  description?: string;
  sell_on_stop?: boolean;
}

interface TradingTaskUpdateRequest {
  config?: string;
  oanda_account?: string;
  name?: string;
  description?: string;
  sell_on_stop?: boolean;
}

function toTradingTask(task: BackendTradingTask): TradingTask {
  return {
    ...task,
    account_id: String(task.account_id),
    status: task.status as TradingTask['status'],
    pip_size: task.pip_size ?? undefined,
    execution_id: task.execution_id ?? undefined,
    started_at: task.started_at ?? undefined,
    completed_at: task.completed_at ?? undefined,
    error_message: task.error_message ?? undefined,
  };
}

function toPaginatedResponse(
  result: BackendPaginatedTradingTasks
): PaginatedResponse<TradingTask> {
  return {
    count: result.count,
    next: result.next ?? null,
    previous: result.previous ?? null,
    results: result.results.map(toTradingTask),
  };
}

export const tradingTasksApi = {
  list: async (
    params?: TradingTaskListParams
  ): Promise<PaginatedResponse<TradingTask>> => {
    const result = await withRetry(() =>
      api.get<BackendPaginatedTradingTasks>(`${BASE}/`, {
        account_id: params?.account_id ? Number(params.account_id) : undefined,
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

  get: async (id: string): Promise<TradingTask> => {
    return toTradingTask(
      await withRetry(() => api.get<BackendTradingTask>(`${BASE}/${id}/`))
    );
  },

  create: async (data: TradingTaskCreateRequest): Promise<TradingTask> => {
    return toTradingTask(
      await withRetry(() => api.post<BackendTradingTask>(`${BASE}/`, data))
    );
  },

  update: async (
    id: string,
    data: TradingTaskCreateRequest
  ): Promise<TradingTask> => {
    return toTradingTask(
      await withRetry(() => api.put<BackendTradingTask>(`${BASE}/${id}/`, data))
    );
  },

  partialUpdate: async (
    id: string,
    data: TradingTaskUpdateRequest
  ): Promise<TradingTask> => {
    return toTradingTask(
      await withRetry(() =>
        api.patch<BackendTradingTask>(`${BASE}/${id}/`, data)
      )
    );
  },

  delete: async (id: string): Promise<void> => {
    return withRetry(() => api.delete(`${BASE}/${id}/`));
  },

  start: async (id: string): Promise<TradingTask> => {
    return toTradingTask(
      await api.post<BackendTradingTask>(`${BASE}/${id}/start/`, {})
    );
  },

  stop: async (
    id: string,
    mode: 'immediate' | 'graceful' | 'graceful_close' = 'graceful'
  ): Promise<Record<string, unknown>> => {
    return api.post<Record<string, unknown>>(`${BASE}/${id}/stop/`, { mode });
  },

  pause: async (id: string): Promise<TradingTask> => {
    return toTradingTask(
      await api.post<BackendTradingTask>(`${BASE}/${id}/pause/`, {})
    );
  },

  resume: async (id: string): Promise<TradingTask> => {
    return toTradingTask(
      await api.post<BackendTradingTask>(`${BASE}/${id}/resume/`, {})
    );
  },

  restart: async (id: string): Promise<TradingTask> => {
    return toTradingTask(
      await api.post<BackendTradingTask>(`${BASE}/${id}/restart/`, {})
    );
  },

  copy: async (
    id: string,
    data: { new_name: string }
  ): Promise<TradingTask> => {
    const result = await withRetry(() =>
      api.post<BackendTradingTask>(`${BASE}/${id}/copy/`, data)
    );
    return toTradingTask(result);
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

  getMetricsCheckpoint: async (
    id: string
  ): Promise<{ checkpoint: ExecutionMetricsCheckpoint | null }> => {
    const task = await withRetry(() =>
      api.get<BackendTradingTask>(`${BASE}/${id}/`)
    );
    return {
      checkpoint: task.error_message
        ? { timestamp: task.updated_at, total_pnl: undefined }
        : null,
    };
  },

  getEquityCurve: async (): Promise<{ equity_curve: EquityPoint[] }> => {
    return { equity_curve: [] };
  },

  getTradeLogs: async (): Promise<{ trade_logs: Trade[] }> => {
    return { trade_logs: [] };
  },

  getStrategyEvents: async (): Promise<{
    strategy_events: BacktestStrategyEvent[];
  }> => {
    return { strategy_events: [] };
  },
};
