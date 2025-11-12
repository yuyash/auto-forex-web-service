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

export const strategiesApi = {
  /**
   * List all available strategies
   */
  list: async (): Promise<StrategyListResponse> => {
    return apiClient.get<StrategyListResponse>('/strategies/');
  },
};
