// Strategy Configuration API service

import { api } from '../../api/apiClient';
import { withRetry } from '../../api/client';
import type {
  StrategyConfig,
  StrategyConfigCreateData,
  StrategyConfigUpdateData,
  StrategyConfigListParams,
  ConfigurationTask,
  PaginatedResponse,
} from '../../types';
import type { PaginatedApiResponse } from '../../api/types';

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const toLocal = (config: any): StrategyConfig => ({
  ...config,
  parameters: config.parameters ?? {},
});

export const configurationsApi = {
  /**
   * List all strategy configurations for the current user
   */
  list: async (
    params?: StrategyConfigListParams
  ): Promise<PaginatedResponse<StrategyConfig>> => {
    const result = await withRetry(() =>
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      api.get<PaginatedApiResponse<any>>('/api/trading/strategy-configs/', {
        page: params?.page,
        page_size: params?.page_size,
      })
    );
    return {
      count: result.count,
      next: result.next ?? null,
      previous: result.previous ?? null,
      results: result.results.map(toLocal),
    };
  },

  /**
   * Get a single strategy configuration by ID
   */
  get: async (id: string): Promise<StrategyConfig> => {
    if (!id) {
      return Promise.reject(new Error('Invalid configuration ID'));
    }
    const result = await withRetry(() =>
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      api.get<any>(`/api/trading/strategy-configs/${id}/`)
    );
    return toLocal(result);
  },

  /**
   * Create a new strategy configuration
   */
  create: async (data: StrategyConfigCreateData): Promise<StrategyConfig> => {
    const result = await withRetry(() =>
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      api.post<any>('/api/trading/strategy-configs/', data)
    );
    return toLocal(result);
  },

  /**
   * Update an existing strategy configuration
   */
  update: async (
    id: string,
    data: StrategyConfigUpdateData
  ): Promise<StrategyConfig> => {
    if (!id) {
      return Promise.reject(new Error('Invalid configuration ID'));
    }
    const result = await withRetry(() =>
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      api.put<any>(`/api/trading/strategy-configs/${id}/`, data)
    );
    return toLocal(result);
  },

  /**
   * Delete a strategy configuration
   */
  delete: async (id: string): Promise<void> => {
    if (!id) {
      return Promise.reject(new Error('Invalid configuration ID'));
    }
    return withRetry(() => api.delete(`/api/trading/strategy-configs/${id}/`));
  },

  /**
   * List tasks using a strategy configuration.
   */
  getTasks: async (
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    _id: string
  ): Promise<ConfigurationTask[]> => {
    const [tradingTasks, backtestTasks] = await Promise.all([
      withRetry(() =>
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        api.get<PaginatedApiResponse<any>>('/api/trading/tasks/trading/')
      ),
      withRetry(() =>
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        api.get<PaginatedApiResponse<any>>('/api/trading/tasks/backtest/')
      ),
    ]);

    const trading: ConfigurationTask[] = (tradingTasks.results ?? []).map(
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (task: any) => ({
        id: task.id,
        task_type: 'trading',
        name: task.name,
        status: task.status,
      })
    );

    const backtest: ConfigurationTask[] = (backtestTasks.results ?? []).map(
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (task: any) => ({
        id: task.id,
        task_type: 'backtest',
        name: task.name,
        status: task.status,
      })
    );

    return [...trading, ...backtest];
  },
};
