// React Query hooks for accounts
import { useQuery } from '@tanstack/react-query';
import { queryKeys } from '../config/reactQuery';
import { accountsApi, type AccountListParams } from '../services/api/accounts';
import { toQueryStateResult } from './useTaskCollections';

// List accounts
export function useAccounts(
  params?: AccountListParams,
  options?: { enabled?: boolean }
) {
  const query = useQuery({
    queryKey: queryKeys.accounts.list(params),
    queryFn: () => accountsApi.list(params),
    enabled: options?.enabled !== false,
  });
  return toQueryStateResult({
    ...query,
    refresh: () => query.refetch(),
    refetch: () => query.refetch(),
  });
}

// Get single account
export function useAccount(id: number, options?: { enabled?: boolean }) {
  const query = useQuery({
    queryKey: queryKeys.accounts.detail(id),
    queryFn: () => accountsApi.get(id),
    enabled: options?.enabled !== false && id > 0,
  });
  return toQueryStateResult({
    ...query,
    refresh: () => query.refetch(),
    refetch: () => query.refetch(),
  });
}
