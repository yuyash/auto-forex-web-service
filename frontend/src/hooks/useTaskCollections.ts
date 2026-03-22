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
