// Strategy Configuration API service

import { TradingService } from '../../api/generated/services/TradingService';
import { withRetry } from '../../api/client';
import type {
  StrategyConfig,
  StrategyConfigCreateData,
  StrategyConfigUpdateData,
  StrategyConfigListParams,
  ConfigurationTask,
  PaginatedResponse,
} from '../../types';

export const configurationsApi = {
  /**
   * List all strategy configurations for the current user
   */
  list: (
    params?: StrategyConfigListParams
  ): Promise<PaginatedResponse<StrategyConfig>> => {
    return withRetry(() =>
      TradingService.tradingStrategyConfigsList(params?.page, params?.page_size)
    );
  },

  /**
   * Get a single strategy configuration by ID
   */
  get: (id: string): Promise<StrategyConfig> => {
    // Validate ID before making API call
    if (!id || typeof id !== 'string' || id.trim() === '') {
      return Promise.reject(new Error('Invalid configuration ID'));
    }
    return withRetry(() => TradingService.tradingStrategyConfigsRetrieve(id));
  },

  /**
   * Create a new strategy configuration
   */
  create: (data: StrategyConfigCreateData): Promise<StrategyConfig> => {
    return withRetry(() => TradingService.tradingStrategyConfigsCreate(data));
  },

  /**
   * Update an existing strategy configuration
   */
  update: (
    id: string,
    data: StrategyConfigUpdateData
  ): Promise<StrategyConfig> => {
    // Validate ID before making API call
    if (!id || typeof id !== 'string' || id.trim() === '') {
      return Promise.reject(new Error('Invalid configuration ID'));
    }
    return withRetry(() =>
      TradingService.tradingStrategyConfigsUpdate(id, data)
    );
  },

  /**
   * Delete a strategy configuration
   * Note: Will fail if configuration is in use by active tasks
   */
  delete: (id: string): Promise<void> => {
    // Validate ID before making API call
    if (!id || typeof id !== 'string' || id.trim() === '') {
      return Promise.reject(new Error('Invalid configuration ID'));
    }
    return withRetry(() => TradingService.tradingStrategyConfigsDestroy(id));
  },

  /**
   * List tasks using a strategy configuration.
   * This is implemented by filtering both trading and backtest task lists.
   */
  getTasks: async (
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    _id: string
  ): Promise<ConfigurationTask[]> => {
    const [tradingTasks, backtestTasks] = await Promise.all([
      withRetry(() => TradingService.tradingTasksTradingList()),
      withRetry(() => TradingService.tradingTasksBacktestList()),
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

    // TODO: Filter by config_id on client side once we have the data
    return [...trading, ...backtest];
  },
};
