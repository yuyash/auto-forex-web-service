// Strategy API service
import { api } from '../../api/apiClient';
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
    const data = await withRetry(() =>
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      api.get<any>('/api/trading/strategies/')
    );
    if (Array.isArray(data)) {
      return { strategies: data, count: data.length };
    }
    if (data.strategies) {
      return data as StrategyListResponse;
    }
    return { strategies: [data], count: 1 };
  },

  /**
   * Fetch default parameters for a strategy
   */
  defaults: async (strategyId: string): Promise<StrategyDefaultsResponse> => {
    const data = await withRetry(() =>
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      api.get<any>(`/api/trading/strategies/${strategyId}/defaults/`)
    );
    if (data.strategy_id && data.defaults) {
      return data as StrategyDefaultsResponse;
    }
    return { strategy_id: strategyId, defaults: data };
  },
};
