// Configuration hooks for data fetching and mutations
import { useState, useEffect, useCallback } from 'react';
import { configurationsApi } from '../services/api';
import type {
  StrategyConfig,
  StrategyConfigListParams,
  PaginatedResponse,
  ConfigurationTask,
} from '../types';

interface UseConfigurationsResult {
  data: PaginatedResponse<StrategyConfig> | null;
  isLoading: boolean;
  error: Error | null;
  refetch: () => Promise<void>;
}

/**
 * Hook to fetch list of strategy configurations
 */
export function useConfigurations(
  params?: StrategyConfigListParams
): UseConfigurationsResult {
  const [data, setData] = useState<PaginatedResponse<StrategyConfig> | null>(
    null
  );
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetchData = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);
      const result = await configurationsApi.list(params);
      setData(result);
    } catch (err) {
      setError(err as Error);
    } finally {
      setIsLoading(false);
    }
  }, [params]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return {
    data,
    isLoading,
    error,
    refetch: fetchData,
  };
}

interface UseConfigurationResult {
  data: StrategyConfig | null;
  isLoading: boolean;
  error: Error | null;
  refetch: () => Promise<void>;
}

/**
 * Hook to fetch a single strategy configuration
 */
export function useConfiguration(id: number): UseConfigurationResult {
  const [data, setData] = useState<StrategyConfig | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetchData = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);
      const result = await configurationsApi.get(id);
      setData(result);
    } catch (err) {
      setError(err as Error);
    } finally {
      setIsLoading(false);
    }
  }, [id]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return {
    data,
    isLoading,
    error,
    refetch: fetchData,
  };
}

interface UseConfigurationTasksResult {
  data: ConfigurationTask[] | null;
  isLoading: boolean;
  error: Error | null;
  refetch: () => Promise<void>;
}

/**
 * Hook to fetch tasks using a configuration
 */
export function useConfigurationTasks(id: number): UseConfigurationTasksResult {
  const [data, setData] = useState<ConfigurationTask[] | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetchData = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);
      const result = await configurationsApi.getTasks(id);
      setData(result);
    } catch (err) {
      setError(err as Error);
    } finally {
      setIsLoading(false);
    }
  }, [id]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return {
    data,
    isLoading,
    error,
    refetch: fetchData,
  };
}
