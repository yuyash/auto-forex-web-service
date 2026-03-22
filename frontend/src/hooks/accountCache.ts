import { queryClient, queryKeys } from '../config/reactQuery';
import type { Account } from '../types/strategy';

function mergeAccountListEntry(
  cached: Account[] | undefined,
  account: Account
): Account[] | undefined {
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

export function upsertAccountCaches(account: Account): void {
  queryClient.setQueryData(queryKeys.accounts.detail(account.id), account);
  queryClient.setQueriesData<Account[] | undefined>(
    { queryKey: queryKeys.accounts.lists() },
    (cached) => mergeAccountListEntry(cached, account)
  );
}

export function removeAccountCaches(accountId: number): void {
  queryClient.removeQueries({ queryKey: queryKeys.accounts.detail(accountId) });
  queryClient.setQueriesData<Account[] | undefined>(
    { queryKey: queryKeys.accounts.lists() },
    (cached) => cached?.filter((entry) => entry.id !== accountId) ?? cached
  );
}
