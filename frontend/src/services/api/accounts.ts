// OANDA Accounts API service (Market app)
import { apiClient } from './client';
import type { Account } from '../../types/strategy';

export interface AccountListParams {
  page?: number;
  page_size?: number;
  [key: string]: unknown;
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
      '/market/accounts/',
      params
    );
    return response;
  },

  // Get a single account by ID
  get: async (id: number): Promise<Account> => {
    const response = await apiClient.get<Account>(`/market/accounts/${id}/`);
    return response;
  },

  // Create a new account
  create: async (data: {
    account_id: string;
    api_token: string;
    api_type?: 'practice' | 'live';
    jurisdiction?: string;
    is_default?: boolean;
  }): Promise<Account> => {
    return apiClient.post<Account>('/market/accounts/', data);
  },

  // Update an existing account (partial)
  update: async (
    id: number,
    data: Partial<{
      account_id: string;
      api_token: string;
      api_type: 'practice' | 'live';
      jurisdiction: string;
      is_default: boolean;
      is_active: boolean;
    }>
  ): Promise<Account> => {
    return apiClient.put<Account>(`/market/accounts/${id}/`, data);
  },

  // Delete an account
  delete: async (id: number): Promise<void> => {
    return apiClient.delete<void>(`/market/accounts/${id}/`);
  },
};
