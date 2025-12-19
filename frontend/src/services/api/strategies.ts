// Strategy API service
import { apiClient } from './client';

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
    return apiClient.get<StrategyListResponse>('/trading/strategies/');
  },

  /**
   * Fetch default parameters for a strategy
   */
  defaults: async (strategyId: string): Promise<StrategyDefaultsResponse> => {
    const encoded = encodeURIComponent(strategyId);
    return apiClient.get<StrategyDefaultsResponse>(
      `/trading/strategies/${encoded}/defaults/`
    );
  },
};
