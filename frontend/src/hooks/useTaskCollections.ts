import { useQuery, type UseQueryOptions } from '@tanstack/react-query';
import { usePollingPolicy, type PollingPolicyState } from './usePollingPolicy';
import { useTaskQueryPolling } from './useTaskQueryPolling';

export interface QueryStateResult<TData> {
  data: TData | null;
  isLoading: boolean;
  error: Error | null;
  refresh: () => Promise<unknown>;
  refetch: () => Promise<unknown>;
}

interface QueryPollingOptions<TData> {
  policy: PollingPolicyState;
  shouldPoll?: (data: TData | null) => boolean;
}

export function toQueryStateResult<TData>(state: {
  data: TData | undefined;
  isLoading: boolean;
  error: unknown;
  refresh?: () => Promise<unknown>;
  refetch: () => Promise<unknown>;
}): QueryStateResult<TData> {
  const refresh = state.refresh ?? state.refetch;
  return {
    data: state.data ?? null,
    isLoading: state.isLoading,
    error: (state.error as Error | null) ?? null,
    refresh,
    refetch: refresh,
  };
}

export function toRefreshActions<TValue>(refresh: () => Promise<TValue>): {
  refresh: () => Promise<TValue>;
  refetch: () => Promise<TValue>;
} {
  return {
    refresh,
    refetch: refresh,
  };
}

export function useTaskList<TData>(
  queryOptions: UseQueryOptions<TData>,
  refresh?: () => Promise<unknown>,
  polling?: QueryPollingOptions<TData>
): QueryStateResult<TData> {
  const query = useQuery(queryOptions);
  useTaskQueryPolling(query, polling);
  return toQueryStateResult({
    ...query,
    refresh,
    refetch: () => query.refetch(),
  });
}

export function useTaskDetail<TData>(
  queryOptions: UseQueryOptions<TData>,
  refresh?: () => Promise<unknown>,
  polling?: QueryPollingOptions<TData>
): QueryStateResult<TData> {
  const query = useQuery(queryOptions);
  useTaskQueryPolling(query, polling);
  return toQueryStateResult({
    ...query,
    refresh,
    refetch: () => query.refetch(),
  });
}

export function usePolledTaskResource<TData>(
  queryOptions: UseQueryOptions<TData>,
  refresh: () => Promise<unknown>,
  options?: { pollingEnabled?: boolean; intervalMs?: number }
): QueryStateResult<TData> {
  const query = useQuery(queryOptions);
  const pollingPolicy = usePollingPolicy({
    enabled: options?.pollingEnabled === true,
    baseIntervalMs: options?.intervalMs ?? 10_000,
  });
  useTaskQueryPolling(query, { policy: pollingPolicy });
  return toQueryStateResult({
    ...query,
    refresh,
    refetch: refresh,
  });
}

export interface IncrementalCollectionState<TItem>
  extends QueryStateResult<TItem[]> {
  items: TItem[];
  totalCount: number;
  hasNext: boolean;
  hasPrevious: boolean;
}

export function toIncrementalCollectionState<TItem>(state: {
  items: TItem[];
  totalCount: number;
  hasNext: boolean;
  hasPrevious: boolean;
  isLoading: boolean;
  error: Error | null;
  refresh: () => Promise<void>;
  refetch: () => Promise<void>;
}): IncrementalCollectionState<TItem> {
  const refreshActions = toRefreshActions(state.refresh);
  return {
    data: state.items,
    items: state.items,
    totalCount: state.totalCount,
    hasNext: state.hasNext,
    hasPrevious: state.hasPrevious,
    isLoading: state.isLoading,
    error: state.error,
    ...refreshActions,
  };
}
