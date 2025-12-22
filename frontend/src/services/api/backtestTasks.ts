// Backtest Task API service

import { apiClient } from './client';
import type {
  BacktestTask,
  BacktestTaskCreateData,
  BacktestTaskUpdateData,
  BacktestTaskListParams,
  BacktestTaskCopyData,
  TaskResults,
  TaskEquityCurveResponse,
  TaskStrategyEventsResponse,
  TaskTradeLogsResponse,
  TaskMetricsCheckpointResponse,
  TaskExecution,
  PaginatedResponse,
} from '../../types';

export const backtestTasksApi = {
  /**
   * List all backtest tasks for the current user
   */
  list: (
    params?: BacktestTaskListParams
  ): Promise<PaginatedResponse<BacktestTask>> => {
    return apiClient.get<PaginatedResponse<BacktestTask>>(
      '/trading/backtest-tasks/',
      params as Record<string, unknown>
    );
  },

  /**
   * Get a single backtest task by ID
   */
  get: (id: number): Promise<BacktestTask> => {
    return apiClient.get<BacktestTask>(`/trading/backtest-tasks/${id}/`);
  },

  /**
   * Create a new backtest task
   */
  create: (data: BacktestTaskCreateData): Promise<BacktestTask> => {
    // Transform config_id to config for backend
    const { config_id, ...rest } = data;
    const payload = {
      ...rest,
      config: config_id,
    };
    return apiClient.post<BacktestTask>('/trading/backtest-tasks/', payload);
  },

  /**
   * Get latest metrics checkpoint for the latest backtest execution (best-effort)
   */
  getMetricsCheckpoint: (
    taskId: number
  ): Promise<TaskMetricsCheckpointResponse> => {
    return apiClient.get<TaskMetricsCheckpointResponse>(
      `/trading/backtest-tasks/${taskId}/metrics-checkpoint/`
    );
  },

  /**
   * Update an existing backtest task
   */
  update: (id: number, data: BacktestTaskUpdateData): Promise<BacktestTask> => {
    // No config_id in update data, so just pass through
    return apiClient.put<BacktestTask>(`/trading/backtest-tasks/${id}/`, data);
  },

  /**
   * Delete a backtest task
   */
  delete: (id: number): Promise<void> => {
    return apiClient.delete<void>(`/trading/backtest-tasks/${id}/`);
  },

  /**
   * Copy a backtest task with a new name
   */
  copy: (id: number, data: BacktestTaskCopyData): Promise<BacktestTask> => {
    return apiClient.post<BacktestTask>(
      `/trading/backtest-tasks/${id}/copy/`,
      data
    );
  },

  /**
   * Start a backtest task execution
   */
  start: (id: number): Promise<{ message: string; task_id: number }> => {
    return apiClient.post<{ message: string; task_id: number }>(
      `/trading/backtest-tasks/${id}/start/`
    );
  },

  /**
   * Stop a running backtest task
   */
  stop: (id: number): Promise<{ message: string }> => {
    return apiClient.post<{ message: string }>(
      `/trading/backtest-tasks/${id}/stop/`
    );
  },

  /**
   * Get execution history for a backtest task
   */
  getExecutions: (
    id: number,
    params?: { page?: number; page_size?: number; include_metrics?: boolean }
  ): Promise<PaginatedResponse<TaskExecution>> => {
    return apiClient.get<PaginatedResponse<TaskExecution>>(
      `/trading/backtest-tasks/${id}/executions/`,
      params
    );
  },

  /**
   * Export backtest results as JSON
   */
  exportResults: async (taskId: number, taskName: string): Promise<void> => {
    const token = localStorage.getItem('token');
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
      ...(token && { Authorization: `Bearer ${token}` }),
    };

    const response = await fetch(
      `/api/trading/backtest-tasks/${taskId}/export/`,
      {
        method: 'GET',
        headers,
      }
    );

    if (!response.ok) {
      throw new Error('Failed to export backtest results');
    }

    const data = await response.json();
    const blob = new Blob([JSON.stringify(data, null, 2)], {
      type: 'application/json',
    });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `backtest_${taskId}_${taskName.replace(/\s+/g, '_')}.json`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
  },

  /**
   * Get unified results for a backtest task (running or completed)
   */
  getResults: (taskId: number): Promise<TaskResults> => {
    return apiClient.get<TaskResults>(
      `/trading/backtest-tasks/${taskId}/results/`
    );
  },

  /**
   * Get equity curve for the latest backtest execution
   */
  getEquityCurve: (
    taskId: number,
    params?: { page?: number; page_size?: number }
  ): Promise<TaskEquityCurveResponse> => {
    return apiClient.get<TaskEquityCurveResponse>(
      `/trading/backtest-tasks/${taskId}/equity-curve/`,
      params
    );
  },

  /**
   * Get strategy events for the latest backtest execution
   */
  getStrategyEvents: async (
    taskId: number,
    params?: { page?: number; page_size?: number }
  ): Promise<TaskStrategyEventsResponse> => {
    const pageSize = params?.page_size ?? 1000;
    let page = params?.page ?? 1;

    const allEvents: TaskStrategyEventsResponse['strategy_events'] = [];
    let lastResp: TaskStrategyEventsResponse | null = null;

    // Fetch all pages by default. Hard cap prevents infinite loops.
    for (let i = 0; i < 200; i += 1) {
      const resp = await apiClient.get<TaskStrategyEventsResponse>(
        `/trading/backtest-tasks/${taskId}/strategy-events/`,
        { page, page_size: pageSize }
      );

      lastResp = resp;
      allEvents.push(
        ...(Array.isArray(resp.strategy_events) ? resp.strategy_events : [])
      );

      if (!resp.next) {
        break;
      }

      page += 1;
    }

    if (!lastResp) {
      return {
        task_id: taskId,
        task_type: 'backtest',
        execution_id: null,
        has_metrics: false,
        strategy_events: [],
        count: 0,
        next: null,
        previous: null,
      };
    }

    return {
      ...lastResp,
      strategy_events: allEvents,
      next: null,
      previous: null,
      count: lastResp.count,
    };
  },

  /**
   * Get trade logs for the latest backtest execution
   */
  getTradeLogs: async (
    taskId: number,
    params?: { page?: number; page_size?: number }
  ): Promise<TaskTradeLogsResponse> => {
    const pageSize = params?.page_size ?? 1000;
    let page = params?.page ?? 1;

    const allTrades: TaskTradeLogsResponse['trade_logs'] = [];
    let lastResp: TaskTradeLogsResponse | null = null;

    for (let i = 0; i < 200; i += 1) {
      const resp = await apiClient.get<TaskTradeLogsResponse>(
        `/trading/backtest-tasks/${taskId}/trade-logs/`,
        { page, page_size: pageSize }
      );

      lastResp = resp;
      allTrades.push(
        ...(Array.isArray(resp.trade_logs) ? resp.trade_logs : [])
      );

      if (!resp.next) {
        break;
      }

      page += 1;
    }

    if (!lastResp) {
      return {
        task_id: taskId,
        task_type: 'backtest',
        execution_id: null,
        has_metrics: false,
        trade_logs: [],
        count: 0,
        next: null,
        previous: null,
      };
    }

    return {
      ...lastResp,
      trade_logs: allTrades,
      next: null,
      previous: null,
      count: lastResp.count,
    };
  },
};
