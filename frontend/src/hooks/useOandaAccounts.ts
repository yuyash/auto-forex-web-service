import { useCallback } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useAuth } from '../contexts/AuthContext';
import { queryKeys } from '../config/reactQuery';
import { accountsApi } from '../services/api';
import type { Account } from '../types/strategy';

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

function normalizeAccount(account: Account): OandaAccount {
  const apiType =
    account.api_type === 'practice' || account.api_type === 'live'
      ? account.api_type
      : undefined;
  const isPractice = apiType === 'practice';

  return {
    id: account.id,
    account_id: account.account_id,
    name: undefined,
    api_type: apiType,
    is_practice: isPractice,
    is_active: account.is_active,
    is_default: account.is_default,
    balance:
      typeof account.balance === 'string' ? Number(account.balance) : undefined,
    margin_used: account.margin_used,
    margin_available: account.margin_available,
    unrealized_pnl: account.unrealized_pnl,
    currency: account.currency,
  };
}

export function useOandaAccounts(): UseOandaAccountsResult {
  const { isAuthenticated } = useAuth();

  const query = useQuery({
    queryKey: queryKeys.accounts.list(),
    queryFn: () => accountsApi.list(),
    enabled: isAuthenticated,
    staleTime: 60_000,
    select: (data) => data.map(normalizeAccount),
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
