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
      TradingService.tradingStrategyConfigsList(params?.page, params?.page_size)
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
  get: async (id: string | number): Promise<StrategyConfig> => {
    if (!id) {
      return Promise.reject(new Error('Invalid configuration ID'));
    }
    const result = await withRetry(() =>
      TradingService.tradingStrategyConfigsRetrieve(Number(id))
    );
    return toLocal(result);
  },

  /**
   * Create a new strategy configuration
   */
  create: async (data: StrategyConfigCreateData): Promise<StrategyConfig> => {
    const result = await withRetry(() =>
      TradingService.tradingStrategyConfigsCreate(data)
    );
    return toLocal(result);
  },

  /**
   * Update an existing strategy configuration
   */
  update: async (
    id: string | number,
    data: StrategyConfigUpdateData
  ): Promise<StrategyConfig> => {
    if (!id) {
      return Promise.reject(new Error('Invalid configuration ID'));
    }
    const result = await withRetry(() =>
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      TradingService.tradingStrategyConfigsUpdate(Number(id), data as any)
    );
    return toLocal(result);
  },

  /**
   * Delete a strategy configuration
   */
  delete: async (id: string | number): Promise<void> => {
    if (!id) {
      return Promise.reject(new Error('Invalid configuration ID'));
    }
    return withRetry(() =>
      TradingService.tradingStrategyConfigsDestroy(Number(id))
    );
  },

  /**
   * List tasks using a strategy configuration.
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

    return [...trading, ...backtest];
  },
};
