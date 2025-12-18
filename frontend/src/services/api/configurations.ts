// Strategy Configuration API service

import { apiClient } from './client';
import type {
  StrategyConfig,
  StrategyConfigCreateData,
  StrategyConfigUpdateData,
  StrategyConfigListParams,
  ConfigurationTask,
  TradingTask,
  BacktestTask,
  PaginatedResponse,
} from '../../types';

export const configurationsApi = {
  /**
   * List all strategy configurations for the current user
   */
  list: (
    params?: StrategyConfigListParams
  ): Promise<PaginatedResponse<StrategyConfig>> => {
    return apiClient.get<PaginatedResponse<StrategyConfig>>(
      '/trading/strategy-configs/',
      params as Record<string, unknown>
    );
  },

  /**
   * Get a single strategy configuration by ID
   */
  get: (id: number): Promise<StrategyConfig> => {
    return apiClient.get<StrategyConfig>(`/trading/strategy-configs/${id}/`);
  },

  /**
   * Create a new strategy configuration
   */
  create: (data: StrategyConfigCreateData): Promise<StrategyConfig> => {
    return apiClient.post<StrategyConfig>('/trading/strategy-configs/', data);
  },

  /**
   * Update an existing strategy configuration
   */
  update: (
    id: number,
    data: StrategyConfigUpdateData
  ): Promise<StrategyConfig> => {
    return apiClient.put<StrategyConfig>(
      `/trading/strategy-configs/${id}/`,
      data
    );
  },

  /**
   * Delete a strategy configuration
   * Note: Will fail if configuration is in use by active tasks
   */
  delete: (id: number): Promise<void> => {
    return apiClient.delete<void>(`/trading/strategy-configs/${id}/`);
  },

  /**
   * List tasks using a strategy configuration.
   * This is implemented by filtering both trading and backtest task lists.
   */
  getTasks: async (id: number): Promise<ConfigurationTask[]> => {
    const [tradingTasks, backtestTasks] = await Promise.all([
      apiClient.get<PaginatedResponse<TradingTask>>('/trading/trading-tasks/', {
        config_id: id,
        page_size: 200,
      }),
      apiClient.get<PaginatedResponse<BacktestTask>>(
        '/trading/backtest-tasks/',
        {
          config_id: id,
          page_size: 200,
        }
      ),
    ]);

    const trading: ConfigurationTask[] = (tradingTasks.results ?? []).map(
      (task) => ({
        id: task.id,
        task_type: 'trading',
        name: task.name,
        status: task.status,
      })
    );

    const backtest: ConfigurationTask[] = (backtestTasks.results ?? []).map(
      (task) => ({
        id: task.id,
        task_type: 'backtest',
        name: task.name,
        status: task.status,
      })
    );

    return [...trading, ...backtest];
  },
};
