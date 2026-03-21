import { api } from '../../api/apiClient';
import { withRetry } from '../../api/client';
import type { OandaAccountsRequest } from '../../api/types';
import type { BackendAccount } from './contracts';
import type { Account } from '../../types/strategy';

function toAccount(account: BackendAccount): Account {
  return {
    ...account,
    id: account.id ?? 0,
    account_id: account.account_id,
    api_type: account.api_type ?? 'practice',
    currency: account.currency ?? 'USD',
    balance: account.balance ?? '0',
    margin_used: account.margin_used ?? '0',
    margin_available: account.margin_available ?? '0',
    unrealized_pnl: account.unrealized_pnl ?? '0',
    is_active: account.is_active ?? false,
  };
}

export const accountsApi = {
  list: async () => {
    return (
      await withRetry(() => api.get<BackendAccount[]>('/api/market/accounts/'))
    ).map(toAccount);
  },

  get: async (id: number) => {
    return toAccount(
      await withRetry(() =>
        api.get<BackendAccount>(`/api/market/accounts/${id}/`)
      )
    );
  },

  create: async (data: OandaAccountsRequest) => {
    return toAccount(
      await withRetry(() =>
        api.post<BackendAccount>('/api/market/accounts/', data)
      )
    );
  },

  update: async (id: number, data: OandaAccountsRequest) => {
    return toAccount(
      await withRetry(() =>
        api.put<BackendAccount>(`/api/market/accounts/${id}/`, data)
      )
    );
  },

  delete: async (id: number) => {
    return withRetry(() => api.delete(`/api/market/accounts/${id}/`));
  },
};
