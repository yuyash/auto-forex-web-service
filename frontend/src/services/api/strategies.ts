// Strategy API service
import { TradingService } from '../../api/generated/services/TradingService';
import { withRetry } from '../../api/client';

export interface Strategy {
  id: string;
  name: string;
  description: string;
  config_schema: Record<string, unknown>;
}

export interface StrategyListResponse {
  strategies: Strategy[];
  count: number;
}

export interface StrategyDefaultsResponse {
  strategy_id: string;
  defaults: Record<string, unknown>;
}

export const strategiesApi = {
  /**
   * List all available strategies
   */
  list: async (): Promise<StrategyListResponse> => {
    const result = await withRetry(() =>
      TradingService.tradingStrategiesRetrieve()
    );
    // The generated API returns a single StrategyList object.
    // Wrap it in the expected response shape.
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const data = result as any;
    if (Array.isArray(data)) {
      return { strategies: data, count: data.length };
    }
    // If it's already in the right shape
    if (data.strategies) {
      return data as StrategyListResponse;
    }
    // Single strategy object - wrap in array
    return { strategies: [data], count: 1 };
  },

  /**
   * Fetch default parameters for a strategy
   */
  defaults: async (strategyId: string): Promise<StrategyDefaultsResponse> => {
    const result = await withRetry(() =>
      TradingService.tradingStrategiesDefaultsRetrieve(strategyId)
    );
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const data = result as any;
    if (data.strategy_id && data.defaults) {
      return data as StrategyDefaultsResponse;
    }
    return { strategy_id: strategyId, defaults: data };
  },
};
