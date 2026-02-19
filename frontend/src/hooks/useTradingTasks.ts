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
const CACHE_DURATION = 60000; // 60 seconds (increased from 30)

// Cache errors to prevent retry storms
const errorCache = new Map<string, { error: Error; timestamp: number }>();
const ERROR_CACHE_DURATION = 30000; // 30 seconds - don't retry failed requests for this long

// Track in-flight requests to prevent duplicate API calls
const inflightRequests = new Map<string, Promise<unknown>>();

/**
 * Invalidate all trading task caches
 * Call this after create/update/delete operations
 */
export function invalidateTradingTasksCache(): void {
  cache.clear();
  errorCache.clear();
}

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

function getCachedError(key: string): Error | null {
  const cached = errorCache.get(key);
  if (cached && Date.now() - cached.timestamp < ERROR_CACHE_DURATION) {
    return cached.error;
  }
  return null;
}

function setCachedError(key: string, error: Error): void {
  errorCache.set(key, { error, timestamp: Date.now() });
}

function getInflightRequest<T>(key: string): Promise<T> | null {
  return inflightRequests.get(key) as Promise<T> | null;
}

function setInflightRequest(key: string, promise: Promise<unknown>): void {
  inflightRequests.set(key, promise);
  // Clean up after request completes
  promise.finally(() => {
    inflightRequests.delete(key);
  });
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
    // Skip if params is explicitly undefined
    if (params === undefined) {
      setData(null);
      setIsLoading(false);
      return;
    }

    const cacheKey = paramsKey;

    // Check cache first
    const cachedData = getCachedData<PaginatedResponse<TradingTask>>(cacheKey);
    if (cachedData) {
      setData(cachedData);
      setIsLoading(false);
      setError(null);
      return;
    }

    // Check if there's a cached error - don't retry immediately
    const cachedError = getCachedError(cacheKey);
    if (cachedError) {
      setError(cachedError);
      setIsLoading(false);
      return;
    }

    // Check if there's already a request in flight for this key
    const inflightRequest =
      getInflightRequest<PaginatedResponse<TradingTask>>(cacheKey);
    if (inflightRequest) {
      try {
        const result = await inflightRequest;
        setData(result);
        setIsLoading(false);
        setError(null);
        return;
      } catch (err) {
        if ((err as Error).name !== 'AbortError') {
          const error = err as Error;
          setError(error);
          setCachedError(cacheKey, error);
        }
        setIsLoading(false);
        return;
      }
    }

    // Cancel any pending request from this component
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }

    try {
      setIsLoading(true);
      setError(null);
      abortControllerRef.current = new AbortController();

      // Create and track the request promise
      const requestPromise = tradingTasksApi.list(params);
      setInflightRequest(cacheKey, requestPromise);

      const result = await requestPromise;
      setData(result);
      setCachedData(cacheKey, result);
    } catch (err) {
      if ((err as Error).name !== 'AbortError') {
        const error = err as Error;
        setError(error);
        setCachedError(cacheKey, error);
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
export function useTradingTask(
  id?: string,
  options?: { enabled?: boolean }
): UseTradingTaskResult {
  const [data, setData] = useState<TradingTask | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetchData = useCallback(async () => {
    // Skip fetching if no valid ID or disabled
    if (!id || options?.enabled === false) {
      setIsLoading(false);
      return;
    }

    try {
      // Only show loading spinner on initial fetch (no data yet)
      if (!data) {
        setIsLoading(true);
      }
      setError(null);
      const result = await tradingTasksApi.get(id);
      setData(result);
    } catch (err) {
      setError(err as Error);
    } finally {
      setIsLoading(false);
    }
  }, [id, options?.enabled]); // eslint-disable-line react-hooks/exhaustive-deps

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
  id: string,
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
