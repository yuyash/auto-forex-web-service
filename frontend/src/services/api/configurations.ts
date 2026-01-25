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
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    _params?: StrategyConfigListParams
  ): Promise<PaginatedResponse<StrategyConfig>> => {
    return withRetry(() => TradingService.tradingStrategyConfigsRetrieve());
  },

  /**
   * Get a single strategy configuration by ID
   */
  get: (id: number): Promise<StrategyConfig> => {
    return withRetry(() => TradingService.tradingStrategyConfigsRetrieve2(id));
  },

  /**
   * Create a new strategy configuration
   */
  create: (
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    _data: StrategyConfigCreateData
  ): Promise<StrategyConfig> => {
    return withRetry(() => TradingService.tradingStrategyConfigsCreate());
  },

  /**
   * Update an existing strategy configuration
   */
  update: (
    id: number,
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    _data: StrategyConfigUpdateData
  ): Promise<StrategyConfig> => {
    return withRetry(() => TradingService.tradingStrategyConfigsUpdate(id));
  },

  /**
   * Delete a strategy configuration
   * Note: Will fail if configuration is in use by active tasks
   */
  delete: (id: number): Promise<void> => {
    return withRetry(() => TradingService.tradingStrategyConfigsDestroy(id));
  },

  /**
   * List tasks using a strategy configuration.
   * This is implemented by filtering both trading and backtest task lists.
   */
  getTasks: async (
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    _id: number
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
