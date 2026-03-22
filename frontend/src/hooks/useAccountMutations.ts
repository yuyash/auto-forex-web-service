import { accountsApi } from '../services/api';
import type { Account, AccountUpsertData } from '../types/strategy';
import { removeAccountCaches, upsertAccountCaches } from './accountCache';
import { useWrappedMutation } from './useWrappedMutation';

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
