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
      '/trading-tasks/',
      params as Record<string, unknown>
    );
  },

  /**
   * Get a single trading task by ID
   */
  get: (id: number): Promise<TradingTask> => {
    return apiClient.get<TradingTask>(`/trading-tasks/${id}/`);
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
    return apiClient.post<TradingTask>('/trading-tasks/', payload);
  },

  /**
   * Update an existing trading task
   */
  update: (id: number, data: TradingTaskUpdateData): Promise<TradingTask> => {
    // Transform account_id to oanda_account if present
    const { account_id, ...rest } = data;
    const payload = account_id ? { ...rest, oanda_account: account_id } : data;
    return apiClient.put<TradingTask>(`/trading-tasks/${id}/`, payload);
  },

  /**
   * Delete a trading task
   */
  delete: (id: number): Promise<void> => {
    return apiClient.delete<void>(`/trading-tasks/${id}/`);
  },

  /**
   * Copy a trading task with a new name
   */
  copy: (id: number, data: TradingTaskCopyData): Promise<TradingTask> => {
    return apiClient.post<TradingTask>(`/trading-tasks/${id}/copy/`, data);
  },

  /**
   * Start a trading task execution
   */
  start: (id: number): Promise<{ execution_id: number; message: string }> => {
    return apiClient.post<{ execution_id: number; message: string }>(
      `/trading-tasks/${id}/start/`
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
    }>(`/trading-tasks/${id}/stop/`, { mode });
  },

  /**
   * Pause a running trading task
   */
  pause: (id: number): Promise<{ message: string }> => {
    return apiClient.post<{ message: string }>(`/trading-tasks/${id}/pause/`);
  },

  /**
   * Resume a paused trading task
   */
  resume: (id: number): Promise<{ message: string }> => {
    return apiClient.post<{ message: string }>(`/trading-tasks/${id}/resume/`);
  },

  /**
   * Rerun a trading task from the beginning
   */
  rerun: (id: number): Promise<{ execution_id: number; message: string }> => {
    return apiClient.post<{ execution_id: number; message: string }>(
      `/trading-tasks/${id}/rerun/`
    );
  },

  /**
   * Get execution history for a trading task
   */
  getExecutions: (
    id: number,
    params?: { page?: number; page_size?: number }
  ): Promise<PaginatedResponse<TaskExecution>> => {
    return apiClient.get<PaginatedResponse<TaskExecution>>(
      `/trading-tasks/${id}/executions/`,
      params
    );
  },

  /**
   * Get a specific execution by ID
   */
  getExecution: (
    taskId: number,
    executionId: number
  ): Promise<TaskExecution> => {
    return apiClient.get<TaskExecution>(
      `/trading-tasks/${taskId}/executions/${executionId}/`
    );
  },
};
