import { api } from '../../api/apiClient';
import { withRetry } from '../../api/client';
import type { OandaAccounts, OandaAccountsRequest } from '../../api/types';
import type { BackendAccount } from './contracts';

function toAccount(account: BackendAccount): OandaAccounts {
  return {
    ...account,
    id: account.id,
    api_type: account.api_type,
    jurisdiction: account.jurisdiction as OandaAccounts['jurisdiction'],
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
