// Accounts API service
import { apiClient } from './client';
import type { Account } from '../../types/strategy';

export interface AccountListParams {
  page?: number;
  page_size?: number;
}

export interface AccountListResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: Account[];
}

export const accountsApi = {
  // List all accounts for the authenticated user
  list: async (params?: AccountListParams): Promise<AccountListResponse> => {
    const response = await apiClient.get<AccountListResponse>(
      '/api/accounts/',
      {
        params,
      }
    );
    return response;
  },

  // Get a single account by ID
  get: async (id: number): Promise<Account> => {
    const response = await apiClient.get<Account>(`/api/accounts/${id}/`);
    return response;
  },
};
