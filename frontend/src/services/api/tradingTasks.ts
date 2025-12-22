// Trading Task API service

import { apiClient } from './client';
import type {
  TradingTask,
  TradingTaskCreateData,
  TradingTaskUpdateData,
  TradingTaskListParams,
  TradingTaskCopyData,
  TaskExecution,
  PaginatedResponse,
  TaskResults,
  TaskEquityCurveResponse,
  TaskStrategyEventsResponse,
  TaskTradeLogsResponse,
  TaskMetricsCheckpointResponse,
} from '../../types';

export const tradingTasksApi = {
  /**
   * List all trading tasks for the current user
   */
  list: (
    params?: TradingTaskListParams
  ): Promise<PaginatedResponse<TradingTask>> => {
    return apiClient.get<PaginatedResponse<TradingTask>>(
      '/trading/trading-tasks/',
      params as Record<string, unknown>
    );
  },

  /**
   * Get a single trading task by ID
   */
  get: (id: number): Promise<TradingTask> => {
    return apiClient.get<TradingTask>(`/trading/trading-tasks/${id}/`);
  },

  /**
   * Create a new trading task
   */
  create: (data: TradingTaskCreateData): Promise<TradingTask> => {
    // Transform config_id and account_id to config and oanda_account for backend
    const { config_id, account_id, ...rest } = data;
    const payload = {
      ...rest,
      config: config_id,
      oanda_account: account_id,
    };
    return apiClient.post<TradingTask>('/trading/trading-tasks/', payload);
  },

  /**
   * Update an existing trading task
   */
  update: (id: number, data: TradingTaskUpdateData): Promise<TradingTask> => {
    // Transform account_id to oanda_account if present
    const { account_id, ...rest } = data;
    const payload = account_id ? { ...rest, oanda_account: account_id } : data;
    return apiClient.put<TradingTask>(`/trading/trading-tasks/${id}/`, payload);
  },

  /**
   * Delete a trading task
   */
  delete: (id: number): Promise<void> => {
    return apiClient.delete<void>(`/trading/trading-tasks/${id}/`);
  },

  /**
   * Copy a trading task with a new name
   */
  copy: (id: number, data: TradingTaskCopyData): Promise<TradingTask> => {
    return apiClient.post<TradingTask>(
      `/trading/trading-tasks/${id}/copy/`,
      data
    );
  },

  /**
   * Start a trading task execution
   */
  start: (id: number): Promise<{ message: string; task_id: number }> => {
    return apiClient.post<{ message: string; task_id: number }>(
      `/trading/trading-tasks/${id}/start/`
    );
  },

  /**
   * Stop a running trading task
   * @param id - Task ID
   * @param mode - Stop mode: 'immediate', 'graceful', or 'graceful_close'
   */
  stop: (
    id: number,
    mode: 'immediate' | 'graceful' | 'graceful_close' = 'graceful'
  ): Promise<{ message: string; task_id: number; stop_mode: string }> => {
    return apiClient.post<{
      message: string;
      task_id: number;
      stop_mode: string;
    }>(`/trading/trading-tasks/${id}/stop/`, { mode });
  },

  /**
   * Pause a running trading task
   */
  pause: (id: number): Promise<{ message: string }> => {
    return apiClient.post<{ message: string }>(
      `/trading/trading-tasks/${id}/pause/`
    );
  },

  /**
   * Resume a paused trading task
   */
  resume: (id: number): Promise<{ message: string }> => {
    return apiClient.post<{ message: string }>(
      `/trading/trading-tasks/${id}/resume/`
    );
  },

  /**
   * Restart a trading task with fresh state
   * @param id - Task ID
   * @param clearState - Whether to clear strategy state (default: true)
   */
  restart: (
    id: number,
    clearState: boolean = true
  ): Promise<{
    message: string;
    task_id: number;
    state_cleared: boolean;
  }> => {
    return apiClient.post<{
      message: string;
      task_id: number;
      state_cleared: boolean;
    }>(`/trading/trading-tasks/${id}/restart/`, { clear_state: clearState });
  },

  /**
   * Get execution history for a trading task
   */
  getExecutions: (
    id: number,
    params?: { page?: number; page_size?: number; include_metrics?: boolean }
  ): Promise<PaginatedResponse<TaskExecution>> => {
    return apiClient.get<PaginatedResponse<TaskExecution>>(
      `/trading/trading-tasks/${id}/executions/`,
      params
    );
  },

  /**
   * Get unified results for a trading task (running or completed)
   */
  getResults: (taskId: number): Promise<TaskResults> => {
    return apiClient.get<TaskResults>(
      `/trading/trading-tasks/${taskId}/results/`
    );
  },

  /**
   * Get equity curve for the latest trading execution
   */
  getEquityCurve: (
    taskId: number,
    params?: { page?: number; page_size?: number }
  ): Promise<TaskEquityCurveResponse> => {
    return apiClient.get<TaskEquityCurveResponse>(
      `/trading/trading-tasks/${taskId}/equity-curve/`,
      params
    );
  },

  /**
   * Get strategy events for the latest trading execution
   */
  getStrategyEvents: async (
    taskId: number,
    params?: { page?: number; page_size?: number }
  ): Promise<TaskStrategyEventsResponse> => {
    const pageSize = params?.page_size ?? 1000;
    let page = params?.page ?? 1;

    const allEvents: TaskStrategyEventsResponse['strategy_events'] = [];
    let lastResp: TaskStrategyEventsResponse | null = null;

    for (let i = 0; i < 200; i += 1) {
      const resp = await apiClient.get<TaskStrategyEventsResponse>(
        `/trading/trading-tasks/${taskId}/strategy-events/`,
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
        task_type: 'trading',
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
   * Get trade logs for the latest trading execution
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
        `/trading/trading-tasks/${taskId}/trade-logs/`,
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
        task_type: 'trading',
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

  /**
   * Get latest metrics checkpoint for the latest trading execution (best-effort)
   */
  getMetricsCheckpoint: (
    taskId: number
  ): Promise<TaskMetricsCheckpointResponse> => {
    return apiClient.get<TaskMetricsCheckpointResponse>(
      `/trading/trading-tasks/${taskId}/metrics-checkpoint/`
    );
  },
};
