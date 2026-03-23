import { queryClient, queryKeys } from '../config/reactQuery';
import {
  patchListQueries,
  removeFromListQueries,
  upsertFilteredListEntity,
} from './listCacheUtils';
import {
  matchesEntityFilterSpec,
  type EntityFilterSpec,
} from './listFilterUtils';
import type { Account } from '../types/strategy';

const ACCOUNT_LIST_FILTER_SPEC: EntityFilterSpec<Account> = {
  search: {
    haystack: (account) => [
      account.account_id,
      account.api_type,
      account.currency,
      account.jurisdiction ?? '',
    ],
  },
};

export function upsertAccountCaches(account: Account): void {
  queryClient.setQueryData(queryKeys.accounts.detail(account.id), account);
  patchListQueries<Account[]>(queryKeys.accounts.lists(), (cached, params) =>
    upsertFilteredListEntity(cached, account, params, {
      matches: (entry, queryParams) =>
        matchesEntityFilterSpec(queryParams, entry, ACCOUNT_LIST_FILTER_SPEC),
    })
  );
}

export function removeAccountCaches(accountId: number): void {
  queryClient.removeQueries({ queryKey: queryKeys.accounts.detail(accountId) });
  removeFromListQueries<Account[]>(
    queryKeys.accounts.lists(),
    (cached) => cached?.filter((entry) => entry.id !== accountId) ?? cached
  );
}
