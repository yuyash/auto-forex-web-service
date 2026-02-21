// React Query configuration with optimized caching settings
import { QueryClient } from '@tanstack/react-query';

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Stale time: how long data is considered fresh
      staleTime: 5 * 60 * 1000, // 5 minutes for most queries

      // Cache time: how long inactive data stays in cache
      gcTime: 10 * 60 * 1000, // 10 minutes (formerly cacheTime)

      // Retry configuration - disabled to prevent 429 errors when server is down
      retry: false, // Don't retry failed requests
      retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),

      // Refetch configuration
      refetchOnWindowFocus: false, // Don't refetch on window focus by default
      refetchOnReconnect: false, // Don't refetch when reconnecting to prevent 429
      refetchOnMount: true, // Refetch on component mount

      // Background refetching
      refetchInterval: false, // No automatic background refetching by default

      // Error handling
      throwOnError: false, // Don't throw errors, handle them in components
    },
    mutations: {
      // Retry configuration for mutations
      retry: 0, // Don't retry mutations by default

      // Error handling
      throwOnError: false,
    },
  },
});

// Query key factory for consistent cache keys
export const queryKeys = {
  // Configuration keys
  configurations: {
    all: ['configurations'] as const,
    lists: () => [...queryKeys.configurations.all, 'list'] as const,
    list: (params?: Record<string, unknown>) =>
      [...queryKeys.configurations.lists(), params] as const,
    details: () => [...queryKeys.configurations.all, 'detail'] as const,
    detail: (id: string) =>
      [...queryKeys.configurations.details(), id] as const,
    tasks: (id: string) =>
      [...queryKeys.configurations.detail(id), 'tasks'] as const,
  },

  // Backtest task keys
  backtestTasks: {
    all: ['backtest-tasks'] as const,
    lists: () => [...queryKeys.backtestTasks.all, 'list'] as const,
    list: (params?: Record<string, unknown>) =>
      [...queryKeys.backtestTasks.lists(), params] as const,
    details: () => [...queryKeys.backtestTasks.all, 'detail'] as const,
    detail: (id: string) => [...queryKeys.backtestTasks.details(), id] as const,
    executions: (id: string) =>
      [...queryKeys.backtestTasks.detail(id), 'executions'] as const,
    execution: (taskId: string, executionId: string) =>
      [...queryKeys.backtestTasks.executions(taskId), executionId] as const,
  },

  // Trading task keys
  tradingTasks: {
    all: ['trading-tasks'] as const,
    lists: () => [...queryKeys.tradingTasks.all, 'list'] as const,
    list: (params?: Record<string, unknown>) =>
      [...queryKeys.tradingTasks.lists(), params] as const,
    details: () => [...queryKeys.tradingTasks.all, 'detail'] as const,
    detail: (id: string) => [...queryKeys.tradingTasks.details(), id] as const,
    executions: (id: string) =>
      [...queryKeys.tradingTasks.detail(id), 'executions'] as const,
    execution: (taskId: string, executionId: string) =>
      [...queryKeys.tradingTasks.executions(taskId), executionId] as const,
  },

  // Task execution keys
  executions: {
    all: ['executions'] as const,
    lists: () => [...queryKeys.executions.all, 'list'] as const,
    list: (taskType: string, taskId: string) =>
      [...queryKeys.executions.lists(), taskType, taskId] as const,
    details: () => [...queryKeys.executions.all, 'detail'] as const,
    detail: (id: string) => [...queryKeys.executions.details(), id] as const,
    metrics: (id: string) =>
      [...queryKeys.executions.detail(id), 'metrics'] as const,
  },

  // Account keys
  accounts: {
    all: ['accounts'] as const,
    lists: () => [...queryKeys.accounts.all, 'list'] as const,
    list: () => [...queryKeys.accounts.lists()] as const,
    details: () => [...queryKeys.accounts.all, 'detail'] as const,
    detail: (id: number) => [...queryKeys.accounts.details(), id] as const,
  },

  // System settings keys
  systemSettings: {
    all: ['system-settings'] as const,
    detail: () => [...queryKeys.systemSettings.all, 'detail'] as const,
  },
};

// Cache invalidation helpers
export const cacheInvalidation = {
  // Invalidate all configuration queries
  invalidateConfigurations: () => {
    return queryClient.invalidateQueries({
      queryKey: queryKeys.configurations.all,
    });
  },

  // Invalidate specific configuration
  invalidateConfiguration: (id: string) => {
    return queryClient.invalidateQueries({
      queryKey: queryKeys.configurations.detail(id),
    });
  },

  // Invalidate all backtest task queries
  invalidateBacktestTasks: () => {
    return queryClient.invalidateQueries({
      queryKey: queryKeys.backtestTasks.all,
    });
  },

  // Invalidate specific backtest task
  invalidateBacktestTask: (id: string) => {
    return queryClient.invalidateQueries({
      queryKey: queryKeys.backtestTasks.detail(id),
    });
  },

  // Invalidate all trading task queries
  invalidateTradingTasks: () => {
    return queryClient.invalidateQueries({
      queryKey: queryKeys.tradingTasks.all,
    });
  },

  // Invalidate specific trading task
  invalidateTradingTask: (id: string) => {
    return queryClient.invalidateQueries({
      queryKey: queryKeys.tradingTasks.detail(id),
    });
  },

  // Invalidate task executions
  invalidateExecutions: (taskType: string, taskId: string) => {
    return queryClient.invalidateQueries({
      queryKey: queryKeys.executions.list(taskType, taskId),
    });
  },
};

// Prefetch helpers for optimistic loading
// These will be implemented when converting hooks to React Query
export const prefetchHelpers = {
  // Prefetch configuration details
  prefetchConfiguration: () => {
    // TODO: Implementation when we convert hooks to React Query
  },

  // Prefetch backtest task details
  prefetchBacktestTask: () => {
    // TODO: Implementation when we convert hooks to React Query
  },

  // Prefetch trading task details
  prefetchTradingTask: () => {
    // TODO: Implementation when we convert hooks to React Query
  },
};

export default queryClient;
