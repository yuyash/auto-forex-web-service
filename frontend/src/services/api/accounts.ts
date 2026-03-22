import { api } from '../../api/apiClient';
import { withRetry } from '../../api/client';
import type { BackendAccount } from './contracts';
import type { Account, AccountUpsertData } from '../../types/strategy';

export interface AccountListParams {
  page?: number;
  page_size?: number;
  search?: string;
}

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
  list: async (params?: AccountListParams) => {
    return (
      await withRetry(() =>
        api.get<BackendAccount[]>('/api/market/accounts/', params)
      )
    ).map(toAccount);
  },

  get: async (id: number) => {
    return toAccount(
      await withRetry(() =>
        api.get<BackendAccount>(`/api/market/accounts/${id}/`)
      )
    );
  },

  create: async (data: AccountUpsertData) => {
    return toAccount(
      await withRetry(() =>
        api.post<BackendAccount>('/api/market/accounts/', data)
      )
    );
  },

  update: async (id: number, data: AccountUpsertData) => {
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
