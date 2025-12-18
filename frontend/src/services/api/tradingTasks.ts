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
    params?: { page?: number; page_size?: number }
  ): Promise<PaginatedResponse<TaskExecution>> => {
    return apiClient.get<PaginatedResponse<TaskExecution>>(
      `/trading/trading-tasks/${id}/executions/`,
      params
    );
  },
};
