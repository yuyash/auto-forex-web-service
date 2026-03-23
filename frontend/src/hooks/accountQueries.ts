import type { UseQueryOptions } from '@tanstack/react-query';
import { queryKeys } from '../config/reactQuery';
import { accountsApi, type AccountListParams } from '../services/api/accounts';
import type { Account } from '../types/strategy';

export function createAccountsQuery(
  params?: AccountListParams,
  options?: { enabled?: boolean }
): UseQueryOptions<Account[]> {
  return {
    queryKey: queryKeys.accounts.list(params as Record<string, unknown>),
    queryFn: () => accountsApi.list(params),
    enabled: options?.enabled !== false,
  };
}

export function createAccountQuery(
  id: number,
  options?: { enabled?: boolean }
): UseQueryOptions<Account> {
  return {
    queryKey: queryKeys.accounts.detail(id),
    queryFn: () => accountsApi.get(id),
    enabled: options?.enabled !== false && id > 0,
  };
}
