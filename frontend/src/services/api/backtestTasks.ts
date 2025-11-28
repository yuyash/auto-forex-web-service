// Backtest Task API service

import { apiClient } from './client';
import type {
  BacktestTask,
  BacktestTaskCreateData,
  BacktestTaskUpdateData,
  BacktestTaskListParams,
  BacktestTaskCopyData,
  BacktestLiveResults,
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
      '/backtest-tasks/',
      params as Record<string, unknown>
    );
  },

  /**
   * Get a single backtest task by ID
   */
  get: (id: number): Promise<BacktestTask> => {
    return apiClient.get<BacktestTask>(`/backtest-tasks/${id}/`);
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
    return apiClient.post<BacktestTask>('/backtest-tasks/', payload);
  },

  /**
   * Update an existing backtest task
   */
  update: (id: number, data: BacktestTaskUpdateData): Promise<BacktestTask> => {
    // No config_id in update data, so just pass through
    return apiClient.put<BacktestTask>(`/backtest-tasks/${id}/`, data);
  },

  /**
   * Delete a backtest task
   */
  delete: (id: number): Promise<void> => {
    return apiClient.delete<void>(`/backtest-tasks/${id}/`);
  },

  /**
   * Copy a backtest task with a new name
   */
  copy: (id: number, data: BacktestTaskCopyData): Promise<BacktestTask> => {
    return apiClient.post<BacktestTask>(`/backtest-tasks/${id}/copy/`, data);
  },

  /**
   * Start a backtest task execution
   */
  start: (id: number): Promise<{ execution_id: number; message: string }> => {
    return apiClient.post<{ execution_id: number; message: string }>(
      `/backtest-tasks/${id}/start/`
    );
  },

  /**
   * Stop a running backtest task
   */
  stop: (id: number): Promise<{ message: string }> => {
    return apiClient.post<{ message: string }>(`/backtest-tasks/${id}/stop/`);
  },

  /**
   * Rerun a backtest task from the beginning
   */
  rerun: (id: number): Promise<{ execution_id: number; message: string }> => {
    return apiClient.post<{ execution_id: number; message: string }>(
      `/backtest-tasks/${id}/rerun/`
    );
  },

  /**
   * Get execution history for a backtest task
   */
  getExecutions: (
    id: number,
    params?: { page?: number; page_size?: number }
  ): Promise<PaginatedResponse<TaskExecution>> => {
    return apiClient.get<PaginatedResponse<TaskExecution>>(
      `/backtest-tasks/${id}/executions/`,
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
      `/backtest-tasks/${taskId}/executions/${executionId}/`
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

    const response = await fetch(`/api/backtest-tasks/${taskId}/export/`, {
      method: 'GET',
      headers,
    });

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
   * Get live/intermediate results during backtest execution
   * Returns cached results from the running backtest task
   */
  getLiveResults: (taskId: number): Promise<BacktestLiveResults> => {
    return apiClient.get<BacktestLiveResults>(
      `/backtest-tasks/${taskId}/live-results/`
    );
  },
};
