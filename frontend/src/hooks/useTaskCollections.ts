import { useQuery, type UseQueryOptions } from '@tanstack/react-query';
import { useSequentialPolling } from './useSequentialPolling';

export interface QueryStateResult<TData> {
  data: TData | null;
  isLoading: boolean;
  error: Error | null;
  refresh: () => Promise<unknown>;
  refetch: () => Promise<unknown>;
}

export function useTaskList<TData>(
  queryOptions: UseQueryOptions<TData>,
  refresh: () => Promise<unknown>
): QueryStateResult<TData> {
  const query = useQuery(queryOptions);
  return {
    data: query.data ?? null,
    isLoading: query.isLoading,
    error: (query.error as Error | null) ?? null,
    refresh,
    refetch: refresh,
  };
}

export function useTaskDetail<TData>(
  queryOptions: UseQueryOptions<TData>,
  refresh: () => Promise<unknown>
): QueryStateResult<TData> {
  const query = useQuery(queryOptions);
  return {
    data: query.data ?? null,
    isLoading: query.isLoading,
    error: (query.error as Error | null) ?? null,
    refresh,
    refetch: refresh,
  };
}

export function usePolledTaskResource<TData>(
  queryOptions: UseQueryOptions<TData>,
  refresh: () => Promise<unknown>,
  options?: { pollingEnabled?: boolean; intervalMs?: number }
): QueryStateResult<TData> {
  const query = useQuery(queryOptions);

  useSequentialPolling(
    () => {
      if (!query.isFetching) {
        return query.refetch();
      }
      return Promise.resolve();
    },
    {
      enabled: options?.pollingEnabled === true,
      intervalMs: options?.intervalMs ?? 10_000,
    }
  );

  return {
    data: query.data ?? null,
    isLoading: query.isLoading,
    error: (query.error as Error | null) ?? null,
    refresh,
    refetch: refresh,
  };
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
  return {
    data: state.items,
    items: state.items,
    totalCount: state.totalCount,
    hasNext: state.hasNext,
    hasPrevious: state.hasPrevious,
    isLoading: state.isLoading,
    error: state.error,
    refresh: state.refresh,
    refetch: state.refetch,
  };
}
