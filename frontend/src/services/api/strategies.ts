import { api } from '../../api/apiClient';
import { withRetry } from '../../api/client';
import type {
  BackendStrategyDefaultsResponse,
  BackendStrategyListResponse,
} from './contracts';

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
  list: async (): Promise<StrategyListResponse> => {
    return withRetry(() =>
      api.get<BackendStrategyListResponse>('/api/trading/strategies/')
    );
  },

  defaults: async (strategyId: string): Promise<StrategyDefaultsResponse> => {
    return withRetry(() =>
      api.get<BackendStrategyDefaultsResponse>(
        `/api/trading/strategies/${strategyId}/defaults/`
      )
    );
  },
};
