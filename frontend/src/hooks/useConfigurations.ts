// Configuration hooks for data fetching and mutations
import { useState, useEffect, useCallback, useRef } from 'react';
import { configurationsApi } from '../services/api';
import type {
  StrategyConfig,
  StrategyConfigListParams,
  PaginatedResponse,
  ConfigurationTask,
} from '../types';

// Simple in-memory cache with timestamps
const cache = new Map<string, { data: unknown; timestamp: number }>();
const CACHE_DURATION = 30000; // 30 seconds

function getCachedData<T>(key: string): T | null {
  const cached = cache.get(key);
  if (cached && Date.now() - cached.timestamp < CACHE_DURATION) {
    return cached.data as T;
  }
  return null;
}

function setCachedData(key: string, data: unknown): void {
  cache.set(key, { data, timestamp: Date.now() });
}

interface UseConfigurationsResult {
  data: PaginatedResponse<StrategyConfig> | null;
  isLoading: boolean;
  error: Error | null;
  refetch: () => Promise<void>;
}

/**
 * Hook to fetch list of strategy configurations with caching
 */
export function useConfigurations(
  params?: StrategyConfigListParams
): UseConfigurationsResult {
  const [data, setData] = useState<PaginatedResponse<StrategyConfig> | null>(
    null
  );
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  // Stabilize params to prevent unnecessary re-fetches
  const paramsKey = JSON.stringify(params || {});

  const fetchData = useCallback(async () => {
    // Cancel any pending request
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }

    const cacheKey = paramsKey;
    const cachedData =
      getCachedData<PaginatedResponse<StrategyConfig>>(cacheKey);

    if (cachedData) {
      setData(cachedData);
      setIsLoading(false);
      return;
    }

    try {
      setIsLoading(true);
      setError(null);
      abortControllerRef.current = new AbortController();

      const result = await configurationsApi.list(params);
      setData(result);
      setCachedData(cacheKey, result);
    } catch (err) {
      if ((err as Error).name !== 'AbortError') {
        setError(err as Error);
      }
    } finally {
      setIsLoading(false);
      abortControllerRef.current = null;
    }
  }, [paramsKey, params]);

  useEffect(() => {
    fetchData();

    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
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
