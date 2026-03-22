import { queryClient, queryKeys } from '../config/reactQuery';
import { patchListQueries, removeFromListQueries } from './listCacheUtils';
import type { Account } from '../types/strategy';

function matchesAccountListFilter(
  account: Account,
  params?: Record<string, unknown>
): boolean {
  if (!params) {
    return true;
  }
  const search = params.search;
  if (typeof search !== 'string' || !search.trim()) {
    return true;
  }
  const normalized = search.trim().toLowerCase();
  const haystack = [
    account.account_id,
    account.api_type,
    account.currency,
    account.jurisdiction ?? '',
  ]
    .join(' ')
    .toLowerCase();
  return haystack.includes(normalized);
}

function mergeAccountListEntry(
  cached: Account[] | undefined,
  account: Account,
  params?: Record<string, unknown>
): Account[] | undefined {
  if (!cached) {
    return cached;
  }
  const matches = matchesAccountListFilter(account, params);
  const existing = cached.find((entry) => entry.id === account.id);
  if (existing) {
    if (!matches) {
      return cached.filter((entry) => entry.id !== account.id);
    }
    return cached.map((entry) =>
      entry.id === account.id ? { ...entry, ...account } : entry
    );
  }
  if (!matches) {
    return cached;
  }
  const page = Number(params?.page ?? 1);
  if (page > 1) {
    return cached;
  }
  return [account, ...cached];
}

export function upsertAccountCaches(account: Account): void {
  queryClient.setQueryData(queryKeys.accounts.detail(account.id), account);
  patchListQueries<Account[]>(queryKeys.accounts.lists(), (cached, params) =>
    mergeAccountListEntry(cached, account, params)
  );
}

export function removeAccountCaches(accountId: number): void {
  queryClient.removeQueries({ queryKey: queryKeys.accounts.detail(accountId) });
  removeFromListQueries<Account[]>(
    queryKeys.accounts.lists(),
    (cached) => cached?.filter((entry) => entry.id !== accountId) ?? cached
  );
}
