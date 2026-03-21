// React Query hooks for accounts
import { useQuery } from '@tanstack/react-query';
import { queryKeys } from '../config/reactQuery';
import { accountsApi, type AccountListParams } from '../services/api/accounts';

// List accounts
export function useAccounts(params?: AccountListParams) {
  return useQuery({
    queryKey: queryKeys.accounts.list(params),
    queryFn: () => accountsApi.list(params),
  });
}

// Get single account
export function useAccount(id: number, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: queryKeys.accounts.detail(id),
    queryFn: () => accountsApi.get(id),
    enabled: options?.enabled !== false && id > 0,
  });
}
