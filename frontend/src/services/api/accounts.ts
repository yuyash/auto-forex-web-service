// OANDA Accounts API service (Market app)
import { MarketAccountsService } from '../../api/generated/services/MarketAccountsService';
import { withRetry } from '../../api/client';
import type { OandaAccountsRequest } from '../../api/generated';

export const accountsApi = {
  // List all accounts for the authenticated user
  list: async () => {
    return withRetry(() => MarketAccountsService.listOandaAccounts());
  },

  // Get a single account by ID
  get: async (id: number) => {
    return withRetry(() => MarketAccountsService.getOandaAccountDetail(id));
  },

  // Create a new account
  create: async (data: OandaAccountsRequest) => {
    return withRetry(() => MarketAccountsService.createOandaAccount(data));
  },

  // Update an existing account
  update: async (id: number, data: OandaAccountsRequest) => {
    return withRetry(() => MarketAccountsService.updateOandaAccount(id, data));
  },

  // Delete an account
  delete: async (id: number) => {
    return withRetry(() => MarketAccountsService.deleteOandaAccount(id));
  },
};
