// Backtest Task API service

import { apiClient } from './client';
import type {
  BacktestTask,
  BacktestTaskCreateData,
  BacktestTaskUpdateData,
  BacktestTaskListParams,
  BacktestTaskCopyData,
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
    return apiClient.post<BacktestTask>('/backtest-tasks/', data);
  },

  /**
   * Update an existing backtest task
   */
  update: (id: number, data: BacktestTaskUpdateData): Promise<BacktestTask> => {
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
};
