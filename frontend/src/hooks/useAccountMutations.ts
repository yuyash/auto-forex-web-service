import { queryClient, queryKeys } from '../config/reactQuery';
import { accountsApi } from '../services/api';
import type { Account, AccountUpsertData } from '../types/strategy';
import { useWrappedMutation } from './useWrappedMutation';

async function invalidateAccountQueries(accountId?: number): Promise<void> {
  await queryClient.invalidateQueries({ queryKey: queryKeys.accounts.all });
  if (accountId != null) {
    await queryClient.invalidateQueries({
      queryKey: queryKeys.accounts.detail(accountId),
    });
  }
}

export function useCreateAccount(options?: {
  onSuccess?: (data: Account) => void;
  onError?: (error: Error) => void;
}) {
  return useWrappedMutation(
    (variables: AccountUpsertData) => accountsApi.create(variables),
    {
      onSuccess: async (data) => {
        await invalidateAccountQueries(data.id);
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
        await invalidateAccountQueries(data.id);
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
    onSuccess: async () => {
      await invalidateAccountQueries();
      options?.onSuccess?.();
    },
    onError: (error) => options?.onError?.(error),
  });
}
