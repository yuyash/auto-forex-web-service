import { useQuery, type UseQueryOptions } from '@tanstack/react-query';

interface QueryStateResult<TData> {
  data: TData | null;
  isLoading: boolean;
  error: Error | null;
  refresh: () => Promise<unknown>;
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
  };
}
