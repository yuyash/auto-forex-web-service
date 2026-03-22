import { queryClient, queryKeys } from '../config/reactQuery';
import { accountsApi } from '../services/api';
import type { Account, AccountUpsertData } from '../types/strategy';
import { useWrappedMutation } from './useWrappedMutation';

function upsertAccountCaches(account: Account): void {
  queryClient.setQueryData(queryKeys.accounts.detail(account.id), account);
  queryClient.setQueriesData<Account[] | undefined>(
    { queryKey: queryKeys.accounts.lists() },
    (cached) => {
      if (!cached) {
        return cached;
      }
      const existing = cached.find((entry) => entry.id === account.id);
      if (existing) {
        return cached.map((entry) =>
          entry.id === account.id ? { ...entry, ...account } : entry
        );
      }
      return [account, ...cached];
    }
  );
}

function removeAccountCaches(accountId: number): void {
  queryClient.removeQueries({ queryKey: queryKeys.accounts.detail(accountId) });
  queryClient.setQueriesData<Account[] | undefined>(
    { queryKey: queryKeys.accounts.lists() },
    (cached) => cached?.filter((entry) => entry.id !== accountId) ?? cached
  );
}

export function useCreateAccount(options?: {
  onSuccess?: (data: Account) => void;
  onError?: (error: Error) => void;
}) {
  return useWrappedMutation(
    (variables: AccountUpsertData) => accountsApi.create(variables),
    {
      onSuccess: async (data) => {
        upsertAccountCaches(data);
        options?.onSuccess?.(data);
      },
      onError: (error) => options?.onError?.(error),
    }
  );
}

export function useUpdateAccount(options?: {
  onSuccess?: (data: Account) => void;
  onError?: (error: Error) => void;
}) {
  return useWrappedMutation(
    (variables: { id: number; data: AccountUpsertData }) =>
      accountsApi.update(variables.id, variables.data),
    {
      onSuccess: async (data) => {
        upsertAccountCaches(data);
        options?.onSuccess?.(data);
      },
      onError: (error) => options?.onError?.(error),
    }
  );
}

export function useDeleteAccount(options?: {
  onSuccess?: () => void;
  onError?: (error: Error) => void;
}) {
  return useWrappedMutation((id: number) => accountsApi.delete(id), {
    onSuccess: async (_, id) => {
      removeAccountCaches(id);
      options?.onSuccess?.();
    },
    onError: (error) => options?.onError?.(error),
  });
}
