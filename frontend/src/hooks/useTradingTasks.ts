// Trading Task hooks for data fetching
import { useState, useEffect, useCallback, useRef } from 'react';
import { tradingTasksApi } from '../services/api';
import type {
  TradingTask,
  TradingTaskListParams,
  PaginatedResponse,
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

interface UseTradingTasksResult {
  data: PaginatedResponse<TradingTask> | null;
  isLoading: boolean;
  error: Error | null;
  refetch: () => Promise<void>;
}

/**
 * Hook to fetch list of trading tasks with caching
 */
export function useTradingTasks(
  params?: TradingTaskListParams
): UseTradingTasksResult {
  const [data, setData] = useState<PaginatedResponse<TradingTask> | null>(null);
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
    const cachedData = getCachedData<PaginatedResponse<TradingTask>>(cacheKey);

    if (cachedData) {
      setData(cachedData);
      setIsLoading(false);
      return;
    }

    try {
      setIsLoading(true);
      setError(null);
      abortControllerRef.current = new AbortController();

      const result = await tradingTasksApi.list(params);
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

interface UseTradingTaskResult {
  data: TradingTask | null;
  isLoading: boolean;
  error: Error | null;
  refetch: () => Promise<void>;
}

/**
 * Hook to fetch a single trading task
 */
export function useTradingTask(id: number): UseTradingTaskResult {
  const [data, setData] = useState<TradingTask | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetchData = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);
      const result = await tradingTasksApi.get(id);
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

/**
 * Hook to poll trading task status for running tasks
 */
export function useTradingTaskPolling(
  id: number,
  enabled: boolean = true,
  interval: number = 5000
): UseTradingTaskResult {
  const [data, setData] = useState<TradingTask | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetchData = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);
      const result = await tradingTasksApi.get(id);
      setData(result);
    } catch (err) {
      setError(err as Error);
    } finally {
      setIsLoading(false);
    }
  }, [id]);

  useEffect(() => {
    if (!enabled) return;

    fetchData();
    const intervalId = setInterval(fetchData, interval);

    return () => clearInterval(intervalId);
  }, [fetchData, enabled, interval]);

  return {
    data,
    isLoading,
    error,
    refetch: fetchData,
  };
}
