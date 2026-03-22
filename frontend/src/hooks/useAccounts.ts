// React Query hooks for accounts
import { useQuery } from '@tanstack/react-query';
import { queryClient, queryKeys } from '../config/reactQuery';
import { accountsApi, type AccountListParams } from '../services/api/accounts';

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

  return {
    ...query,
    refresh: () =>
      queryClient.invalidateQueries({
        queryKey: queryKeys.accounts.all,
      }),
  };
}

// Get single account
export function useAccount(id: number, options?: { enabled?: boolean }) {
  const query = useQuery({
    queryKey: queryKeys.accounts.detail(id),
    queryFn: () => accountsApi.get(id),
    enabled: options?.enabled !== false && id > 0,
  });

  return {
    ...query,
    refresh: () =>
      queryClient.invalidateQueries({
        queryKey: queryKeys.accounts.detail(id),
      }),
  };
}
