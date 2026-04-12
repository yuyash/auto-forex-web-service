// React Query configuration with optimized caching settings
import { QueryClient } from '@tanstack/react-query';
import { backtestTasksApi } from '../services/api/backtestTasks';
import { configurationsApi } from '../services/api/configurations';
import { tradingTasksApi } from '../services/api/tradingTasks';

/** Default options shared by every QueryClient instance. */
const defaultQueryClientOptions = {
  queries: {
    // Stale time: how long data is considered fresh
    staleTime: 5 * 60 * 1000, // 5 minutes for most queries

    // Cache time: how long inactive data stays in cache
    gcTime: 10 * 60 * 1000, // 10 minutes (formerly cacheTime)

    // Retry configuration - disabled to prevent 429 errors when server is down
    retry: false as const, // Don't retry failed requests
    retryDelay: (attemptIndex: number) =>
      Math.min(1000 * 2 ** attemptIndex, 30000),

    // Refetch configuration
    refetchOnWindowFocus: false, // Don't refetch on window focus by default
    refetchOnReconnect: false, // Don't refetch when reconnecting to prevent 429
    refetchOnMount: true as const, // Refetch on component mount

    // Background refetching
    refetchInterval: false as const, // No automatic background refetching by default

    // Error handling
    throwOnError: false, // Don't throw errors, handle them in components
  },
  mutations: {
    // Retry configuration for mutations
    retry: 0, // Don't retry mutations by default

    // Error handling
    throwOnError: false,
  },
} as const;

function createQueryClient(): QueryClient {
  return new QueryClient({ defaultOptions: defaultQueryClientOptions });
}

/**
 * The active QueryClient instance.
 *
 * This is replaced with a fresh instance whenever the authenticated user
 * changes (login / logout) so that one user's cached data can never leak
 * into another user's session — even if `queryClient.clear()` is somehow
 * skipped.
 *
 * Code that runs *outside* React components (e.g. mutation-cache helpers)
 * imports this mutable binding.  React components should prefer the
 * `useQueryClient()` hook which reads from the nearest
 * `<QueryClientProvider>`.
 */
export let queryClient: QueryClient = createQueryClient();

/** Subscribers notified when the active QueryClient is replaced. */
type Listener = (client: QueryClient) => void;
const listeners = new Set<Listener>();

/** Subscribe to QueryClient replacements. Returns an unsubscribe function. */
export function onQueryClientChange(listener: Listener): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

/**
 * Replace the active QueryClient with a brand-new instance.
 *
 * Call this on login and logout so that:
 * - The old user's cached data is discarded (the old client is GC'd).
 * - The new user starts with a completely empty cache.
 *
 * The QueryProvider subscribes to this change and re-renders with the new
 * client, so all downstream `useQueryClient()` consumers automatically
 * pick up the new instance.
 */
export function resetQueryClient(): void {
  queryClient = createQueryClient();
  listeners.forEach((fn) => fn(queryClient));
}

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
    executions: (id: string, params?: Record<string, unknown>) =>
      [...queryKeys.backtestTasks.detail(id), 'executions', params] as const,
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
    executions: (id: string, params?: Record<string, unknown>) =>
      [...queryKeys.tradingTasks.detail(id), 'executions', params] as const,
    execution: (taskId: string, executionId: string) =>
      [...queryKeys.tradingTasks.executions(taskId), executionId] as const,
  },

  // Account keys
  accounts: {
    all: ['accounts'] as const,
    lists: () => [...queryKeys.accounts.all, 'list'] as const,
    list: (params?: Record<string, unknown>) =>
      [...queryKeys.accounts.lists(), params] as const,
    details: () => [...queryKeys.accounts.all, 'detail'] as const,
    detail: (id: number) => [...queryKeys.accounts.details(), id] as const,
  },

  health: {
    all: ['health'] as const,
    backend: () => [...queryKeys.health.all, 'backend'] as const,
    oanda: () => [...queryKeys.health.all, 'oanda'] as const,
  },

  strategies: {
    all: ['strategies'] as const,
    list: () => [...queryKeys.strategies.all, 'list'] as const,
    defaults: (id: string) =>
      [...queryKeys.strategies.all, 'defaults', id] as const,
  },

  taskResources: {
    all: ['task-resources'] as const,
    summary: (taskType: string, taskId: string, executionRunId?: string) =>
      [
        ...queryKeys.taskResources.all,
        taskType,
        taskId,
        'summary',
        executionRunId ?? null,
      ] as const,
    strategyEvents: (
      taskType: string,
      taskId: string,
      executionRunId?: string,
      cycleId?: string
    ) =>
      [
        ...queryKeys.taskResources.all,
        taskType,
        taskId,
        'strategy-events',
        executionRunId ?? null,
        cycleId ?? null,
      ] as const,
    logComponents: (
      taskType: string,
      taskId: string,
      executionRunId?: string
    ) =>
      [
        ...queryKeys.taskResources.all,
        taskType,
        taskId,
        'log-components',
        executionRunId ?? null,
      ] as const,
  },

  // System settings keys
  systemSettings: {
    all: ['system-settings'] as const,
    detail: () => [...queryKeys.systemSettings.all, 'detail'] as const,
  },

  userSettings: {
    all: ['user-settings'] as const,
    detail: () => [...queryKeys.userSettings.all, 'detail'] as const,
  },

  marketConfig: {
    all: ['market-config'] as const,
    instruments: () => [...queryKeys.marketConfig.all, 'instruments'] as const,
    granularities: () =>
      [...queryKeys.marketConfig.all, 'granularities'] as const,
    tickDataRange: (instrument: string) =>
      [...queryKeys.marketConfig.all, 'tick-data-range', instrument] as const,
  },
};

export const prefetchHelpers = {
  prefetchConfiguration: (id: string) =>
    queryClient.prefetchQuery({
      queryKey: queryKeys.configurations.detail(id),
      queryFn: () => configurationsApi.get(id),
    }),

  prefetchBacktestTask: (id: string) =>
    queryClient.prefetchQuery({
      queryKey: queryKeys.backtestTasks.detail(id),
      queryFn: () => backtestTasksApi.get(id),
    }),

  prefetchTradingTask: (id: string) =>
    queryClient.prefetchQuery({
      queryKey: queryKeys.tradingTasks.detail(id),
      queryFn: () => tradingTasksApi.get(id),
    }),
};

export default queryClient;
