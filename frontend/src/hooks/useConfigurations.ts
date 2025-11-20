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

// Track retry attempts per key
const retryAttempts = new Map<string, number>();
const MAX_RETRIES = 3;
const BASE_RETRY_DELAY = 1000; // 1 second

// Listeners for cache invalidation
type InvalidationListener = () => void;
const invalidationListeners = new Set<InvalidationListener>();

function getCachedData<T>(key: string): T | null {
  const cached = cache.get(key);
  if (cached && Date.now() - cached.timestamp < CACHE_DURATION) {
    return cached.data as T;
  }
  return null;
}

function setCachedData(key: string, data: unknown): void {
  cache.set(key, { data, timestamp: Date.now() });
  // Reset retry count on successful fetch
  retryAttempts.delete(key);
}

/**
 * Subscribe to cache invalidation events
 */
function subscribeToInvalidation(listener: InvalidationListener): () => void {
  invalidationListeners.add(listener);
  return () => {
    invalidationListeners.delete(listener);
  };
}

/**
 * Notify all listeners that cache has been invalidated
 */
function notifyInvalidation(): void {
  invalidationListeners.forEach((listener) => listener());
}

/**
 * Invalidate all configuration-related cache entries
 */
export function invalidateConfigurationsCache(): void {
  // Clear all cache entries
  cache.clear();
  // Don't clear retry attempts - let them naturally expire
  // Notify all listeners to refetch
  notifyInvalidation();
}

/**
 * Check if we should retry based on error and attempt count
 */
function shouldRetry(error: Error, key: string): boolean {
  const attempts = retryAttempts.get(key) || 0;

  // Don't retry if we've exceeded max attempts
  if (attempts >= MAX_RETRIES) {
    return false;
  }

  const errorMessage = error.message.toLowerCase();

  // Never retry on connection refused or other fatal errors
  if (
    errorMessage.includes('connection refused') ||
    errorMessage.includes('err_connection_refused') ||
    errorMessage.includes('network error') ||
    errorMessage.includes('failed to fetch')
  ) {
    return false;
  }

  // Only retry on specific retryable errors (5xx, 429, timeout)
  const isRetryable =
    errorMessage.includes('timeout') ||
    errorMessage.includes('429') ||
    errorMessage.includes('too many requests') ||
    errorMessage.includes('502') ||
    errorMessage.includes('503') ||
    errorMessage.includes('504');

  return isRetryable;
}

/**
 * Get retry delay with exponential backoff
 */
function getRetryDelay(key: string): number {
  const attempts = retryAttempts.get(key) || 0;
  return BASE_RETRY_DELAY * Math.pow(2, attempts);
}

/**
 * Sleep for specified milliseconds
 */
function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
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
      setError(null);
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
      const error = err as Error;

      if (error.name !== 'AbortError') {
        // Check if we should retry
        if (shouldRetry(error, cacheKey)) {
          const currentAttempts = retryAttempts.get(cacheKey) || 0;
          retryAttempts.set(cacheKey, currentAttempts + 1);

          const delay = getRetryDelay(cacheKey);
          console.log(
            `Retrying configurations fetch in ${delay}ms (attempt ${currentAttempts + 1}/${MAX_RETRIES})`
          );

          // Wait and retry
          await sleep(delay);

          // Only retry if component is still mounted
          if (abortControllerRef.current) {
            return fetchData();
          }
        } else {
          // Max retries exceeded or non-retryable error
          setError(error);
          retryAttempts.delete(cacheKey);
        }
      }
    } finally {
      setIsLoading(false);
      abortControllerRef.current = null;
    }
  }, [paramsKey, params]);

  useEffect(() => {
    fetchData();

    // Subscribe to cache invalidation events
    const unsubscribe = subscribeToInvalidation(() => {
      fetchData();
    });

    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      unsubscribe();
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
export function useConfiguration(id?: number): UseConfigurationResult {
  const [data, setData] = useState<StrategyConfig | null>(null);
  const [isLoading, setIsLoading] = useState(true); // Start as true to prevent premature redirects
  const [error, setError] = useState<Error | null>(null);
  const isMountedRef = useRef(true);
  const requestIdRef = useRef(0);

  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  const fetchData = useCallback(async () => {
    // Skip fetching if no valid ID
    if (!id || id === 0) {
      setIsLoading(false);
      return;
    }

    const currentRequestId = requestIdRef.current + 1;
    requestIdRef.current = currentRequestId;

    const hasValidId = typeof id === 'number' && Number.isFinite(id) && id > 0;

    if (!hasValidId) {
      if (isMountedRef.current && currentRequestId === requestIdRef.current) {
        setData(null);
        setError(null);
        setIsLoading(false);
      }
      return;
    }

    if (isMountedRef.current && currentRequestId === requestIdRef.current) {
      setIsLoading(true);
      setError(null);
    }

    try {
      const result = await configurationsApi.get(id);
      if (isMountedRef.current && currentRequestId === requestIdRef.current) {
        setData(result);
      }
    } catch (err) {
      if (isMountedRef.current && currentRequestId === requestIdRef.current) {
        setError(err as Error);
      }
    } finally {
      if (isMountedRef.current && currentRequestId === requestIdRef.current) {
        setIsLoading(false);
      }
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
