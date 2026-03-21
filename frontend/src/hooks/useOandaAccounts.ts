import { useCallback } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useAuth } from '../contexts/AuthContext';
import { queryKeys } from '../config/reactQuery';
import { accountsApi } from '../services/api';

export interface OandaAccount {
  id: number;
  account_id: string;
  name?: string;
  api_type?: 'practice' | 'live';
  is_practice?: boolean;
  is_active: boolean;
  is_default?: boolean;
  balance?: number;
  margin_used?: string;
  margin_available?: string;
  unrealized_pnl?: string;
  currency?: string;
}

interface UseOandaAccountsResult {
  accounts: OandaAccount[];
  isLoading: boolean;
  error: Error | null;
  refetch: () => Promise<void>;
  hasAccounts: boolean;
}

function normalizeAccount(account: Record<string, unknown>): OandaAccount {
  const apiType =
    account.api_type === 'practice' || account.api_type === 'live'
      ? account.api_type
      : undefined;
  const isPractice =
    typeof account.is_practice === 'boolean'
      ? account.is_practice
      : apiType === 'practice';

  return {
    id: Number(account.id),
    account_id: String(account.account_id),
    name: typeof account.name === 'string' ? account.name : undefined,
    api_type: apiType,
    is_practice: isPractice,
    is_active: Boolean(account.is_active),
    is_default:
      typeof account.is_default === 'boolean' ? account.is_default : undefined,
    balance:
      typeof account.balance === 'number'
        ? account.balance
        : typeof account.balance === 'string'
          ? Number(account.balance)
          : undefined,
    margin_used:
      typeof account.margin_used === 'string' ? account.margin_used : undefined,
    margin_available:
      typeof account.margin_available === 'string'
        ? account.margin_available
        : undefined,
    unrealized_pnl:
      typeof account.unrealized_pnl === 'string'
        ? account.unrealized_pnl
        : undefined,
    currency:
      typeof account.currency === 'string' ? account.currency : undefined,
  };
}

export function useOandaAccounts(): UseOandaAccountsResult {
  const { isAuthenticated } = useAuth();

  const query = useQuery({
    queryKey: queryKeys.accounts.list(),
    queryFn: () => accountsApi.list(),
    enabled: isAuthenticated,
    staleTime: 60_000,
    select: (data) =>
      data.map((account) =>
        normalizeAccount(account as Record<string, unknown>)
      ),
  });

  const refetch = useCallback(async () => {
    await query.refetch();
  }, [query]);

  const accounts = isAuthenticated ? (query.data ?? []) : [];

  return {
    accounts,
    isLoading: query.isLoading,
    error: query.error as Error | null,
    refetch,
    hasAccounts: accounts.length > 0,
  };
}
