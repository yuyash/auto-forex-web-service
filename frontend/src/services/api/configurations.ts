// Strategy Configuration API service

import { apiClient } from './client';
import {
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
    return apiClient.get<PaginatedResponse<StrategyConfig>>(
      '/strategy-configs/',
      params
    );
  },

  /**
   * Get a single strategy configuration by ID
   */
  get: (id: number): Promise<StrategyConfig> => {
    return apiClient.get<StrategyConfig>(`/strategy-configs/${id}/`);
  },

  /**
   * Create a new strategy configuration
   */
  create: (data: StrategyConfigCreateData): Promise<StrategyConfig> => {
    return apiClient.post<StrategyConfig>('/strategy-configs/', data);
  },

  /**
   * Update an existing strategy configuration
   */
  update: (
    id: number,
    data: StrategyConfigUpdateData
  ): Promise<StrategyConfig> => {
    return apiClient.put<StrategyConfig>(`/strategy-configs/${id}/`, data);
  },

  /**
   * Delete a strategy configuration
   * Note: Will fail if configuration is in use by active tasks
   */
  delete: (id: number): Promise<void> => {
    return apiClient.delete<void>(`/strategy-configs/${id}/`);
  },

  /**
   * Get all tasks using this configuration
   */
  getTasks: (id: number): Promise<ConfigurationTask[]> => {
    return apiClient.get<ConfigurationTask[]>(`/strategy-configs/${id}/tasks/`);
  },
};
