// React Query hooks for accounts
import { type AccountListParams } from '../services/api/accounts';
import { createAccountQuery, createAccountsQuery } from './accountQueries';
import { useTaskDetail, useTaskList } from './useTaskCollections';

// List accounts
export function useAccounts(
  params?: AccountListParams,
  options?: { enabled?: boolean }
) {
  return useTaskList(createAccountsQuery(params, options));
}

// Get single account
export function useAccount(id: number, options?: { enabled?: boolean }) {
  return useTaskDetail(createAccountQuery(id, options));
}
