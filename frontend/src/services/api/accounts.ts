// OANDA Accounts API service (Market app)
import { api } from '../../api/apiClient';
import { withRetry } from '../../api/client';
import type { OandaAccounts, OandaAccountsRequest } from '../../api/types';

export const accountsApi = {
  // List all accounts for the authenticated user
  list: async () => {
    return withRetry(() => api.get<OandaAccounts[]>('/api/market/accounts/'));
  },

  // Get a single account by ID
  get: async (id: number) => {
    return withRetry(() =>
      api.get<OandaAccounts>(`/api/market/accounts/${id}/`)
    );
  },

  // Create a new account
  create: async (data: OandaAccountsRequest) => {
    return withRetry(() =>
      api.post<OandaAccounts>('/api/market/accounts/', data)
    );
  },

  // Update an existing account
  update: async (id: number, data: OandaAccountsRequest) => {
    return withRetry(() =>
      api.put<OandaAccounts>(`/api/market/accounts/${id}/`, data)
    );
  },

  // Delete an account
  delete: async (id: number) => {
    return withRetry(() => api.delete(`/api/market/accounts/${id}/`));
  },
};
