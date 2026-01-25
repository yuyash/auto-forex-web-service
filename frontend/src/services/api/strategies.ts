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
    return withRetry(() => TradingService.tradingStrategiesRetrieve());
  },

  /**
   * Fetch default parameters for a strategy
   */
  defaults: async (strategyId: string): Promise<StrategyDefaultsResponse> => {
    return withRetry(() =>
      TradingService.tradingStrategiesDefaultsRetrieve(strategyId)
    );
  },
};
