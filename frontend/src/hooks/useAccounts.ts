// React Query hooks for accounts
import { useQuery } from '@tanstack/react-query';
import { accountsApi } from '../services/api/accounts';

export interface AccountListParams {
  page?: number;
  page_size?: number;
  search?: string;
}

// Query keys
export const accountKeys = {
  all: ['accounts'] as const,
  lists: () => [...accountKeys.all, 'list'] as const,
  list: (params?: AccountListParams) =>
    [...accountKeys.lists(), params] as const,
  details: () => [...accountKeys.all, 'detail'] as const,
  detail: (id: number) => [...accountKeys.details(), id] as const,
};

// List accounts
export function useAccounts(params?: AccountListParams) {
  return useQuery({
    queryKey: accountKeys.list(params),
    queryFn: () => accountsApi.list(),
  });
}

// Get single account
export function useAccount(id: number, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: accountKeys.detail(id),
    queryFn: () => accountsApi.get(id),
    enabled: options?.enabled !== false && id > 0,
  });
}
