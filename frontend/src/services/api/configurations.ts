import { api } from '../../api/apiClient';
import { withRetry } from '../../api/client';
import type {
  ConfigurationTask,
  PaginatedResponse,
  StrategyConfig,
  StrategyConfigCreateData,
  StrategyConfigListParams,
  StrategyConfigUpdateData,
} from '../../types';
import type {
  BackendConfigurationTaskList,
  BackendPaginatedConfigurations,
  BackendStrategyConfig,
} from './contracts';

function toStrategyConfig(config: BackendStrategyConfig): StrategyConfig {
  return {
    ...config,
    parameters: config.parameters ?? {},
  };
}

function toPaginatedResponse(
  result: BackendPaginatedConfigurations
): PaginatedResponse<StrategyConfig> {
  return {
    count: result.count,
    next: result.next ?? null,
    previous: result.previous ?? null,
    results: result.results.map(toStrategyConfig),
  };
}

export const configurationsApi = {
  list: async (
    params?: StrategyConfigListParams
  ): Promise<PaginatedResponse<StrategyConfig>> => {
    const result = await withRetry(() =>
      api.get<BackendPaginatedConfigurations>(
        '/api/trading/strategy-configs/',
        {
          page: params?.page,
          page_size: params?.page_size,
          search: params?.search,
          strategy_type: params?.strategy_type,
        }
      )
    );
    return toPaginatedResponse(result);
  },

  get: async (id: string): Promise<StrategyConfig> => {
    if (!id) {
      return Promise.reject(new Error('Invalid configuration ID'));
    }
    return toStrategyConfig(
      await withRetry(() =>
        api.get<BackendStrategyConfig>(`/api/trading/strategy-configs/${id}/`)
      )
    );
  },

  create: async (data: StrategyConfigCreateData): Promise<StrategyConfig> => {
    return toStrategyConfig(
      await withRetry(() =>
        api.post<BackendStrategyConfig>('/api/trading/strategy-configs/', data)
      )
    );
  },

  update: async (
    id: string,
    data: StrategyConfigUpdateData
  ): Promise<StrategyConfig> => {
    if (!id) {
      return Promise.reject(new Error('Invalid configuration ID'));
    }
    return toStrategyConfig(
      await withRetry(() =>
        api.put<BackendStrategyConfig>(
          `/api/trading/strategy-configs/${id}/`,
          data
        )
      )
    );
  },

  delete: async (id: string): Promise<void> => {
    if (!id) {
      return Promise.reject(new Error('Invalid configuration ID'));
    }
    return withRetry(() => api.delete(`/api/trading/strategy-configs/${id}/`));
  },

  getTasks: async (id: string): Promise<ConfigurationTask[]> => {
    if (!id) {
      return Promise.reject(new Error('Invalid configuration ID'));
    }
    const result = await withRetry(() =>
      api.get<BackendConfigurationTaskList>(
        `/api/trading/strategy-configs/${id}/tasks/`
      )
    );
    return result.results;
  },
};
