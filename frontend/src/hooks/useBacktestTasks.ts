// Backtest Task hooks for data fetching
import { useState, useEffect, useCallback, useRef } from 'react';
import { backtestTasksApi } from '../services/api';
import type {
  BacktestTask,
  BacktestTaskListParams,
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

/**
 * Invalidate all cached backtest tasks data
 * Call this after create/update/delete operations
 */
export function invalidateBacktestTasksCache(): void {
  cache.clear();
  errorCache.clear();
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

interface UseBacktestTasksResult {
  data: PaginatedResponse<BacktestTask> | null;
  isLoading: boolean;
  error: Error | null;
  refetch: () => Promise<void>;
}

/**
 * Hook to fetch list of backtest tasks with caching
 */
export function useBacktestTasks(
  params?: BacktestTaskListParams
): UseBacktestTasksResult {
  const [data, setData] = useState<PaginatedResponse<BacktestTask> | null>(
    null
  );
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  // Stabilize params to prevent unnecessary re-fetches
  const paramsKey = JSON.stringify(params || {});

  const fetchData = useCallback(async () => {
    const cacheKey = paramsKey;

    // Check cache first
    const cachedData = getCachedData<PaginatedResponse<BacktestTask>>(cacheKey);
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
      getInflightRequest<PaginatedResponse<BacktestTask>>(cacheKey);
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
      const requestPromise = backtestTasksApi.list(params);
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

interface UseBacktestTaskResult {
  data: BacktestTask | null;
  isLoading: boolean;
  error: Error | null;
  refetch: () => Promise<void>;
}

/**
 * Hook to fetch a single backtest task
 */
export function useBacktestTask(id?: number): UseBacktestTaskResult {
  const [data, setData] = useState<BacktestTask | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const fetchData = useCallback(async () => {
    // Skip fetching if no valid ID
    if (!id || id === 0) {
      setIsLoading(false);
      return;
    }

    // Cancel any pending request
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }

    try {
      setIsLoading(true);
      setError(null);
      abortControllerRef.current = new AbortController();

      // Add cache-busting query parameter when force is true
      const result = await backtestTasksApi.get(id);
      setData(result);
    } catch (err) {
      if ((err as Error).name !== 'AbortError') {
        setError(err as Error);
      }
    } finally {
      setIsLoading(false);
      abortControllerRef.current = null;
    }
  }, [id]);

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
    refetch: () => fetchData(true),
  };
}

/**
 * Hook to poll backtest task status for running tasks
 */
export function useBacktestTaskPolling(
  id: number,
  enabled: boolean = true,
  interval: number = 10000
): UseBacktestTaskResult {
  const [data, setData] = useState<BacktestTask | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetchData = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);
      const result = await backtestTasksApi.get(id);
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
