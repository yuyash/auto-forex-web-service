import { beforeEach, describe, expect, it } from 'vitest';
import { queryClient, queryKeys } from '../../../src/config/reactQuery';
import {
  removeAccountCaches,
  upsertAccountCaches,
} from '../../../src/hooks/accountCache';
import type { Account } from '../../../src/types/strategy';

function buildAccount(overrides?: Partial<Account>): Account {
  return {
    id: 1,
    account_id: 'ACC-001',
    api_type: 'practice',
    currency: 'USD',
    balance: '1000',
    margin_used: '0',
    margin_available: '1000',
    unrealized_pnl: '0',
    is_active: true,
    ...overrides,
  };
}

describe('accountCache', () => {
  beforeEach(() => {
    queryClient.clear();
  });

  it('patches matching list caches and leaves non-matching search caches untouched', () => {
    const matchingKey = queryKeys.accounts.list({ search: 'acc' });
    const nonMatchingKey = queryKeys.accounts.list({ search: 'live only' });
    const detailKey = queryKeys.accounts.detail(1);
    queryClient.setQueryData<Account[]>(matchingKey, []);
    queryClient.setQueryData<Account[]>(nonMatchingKey, []);
    queryClient.setQueryData<Account | null>(detailKey, null);

    upsertAccountCaches(buildAccount());

    expect(queryClient.getQueryData<Account[]>(matchingKey)).toEqual([
      expect.objectContaining({ account_id: 'ACC-001' }),
    ]);
    expect(queryClient.getQueryData<Account[]>(nonMatchingKey)).toEqual([]);
    expect(queryClient.getQueryData<Account>(detailKey)).toEqual(
      expect.objectContaining({ account_id: 'ACC-001' })
    );
  });

  it('removes deleted accounts from cached lists and detail cache', () => {
    const listKey = queryKeys.accounts.list();
    const detailKey = queryKeys.accounts.detail(1);
    queryClient.setQueryData<Account[]>(listKey, [
      buildAccount(),
      buildAccount({ id: 2, account_id: 'ACC-002' }),
    ]);
    queryClient.setQueryData<Account>(detailKey, buildAccount());

    removeAccountCaches(1);

    expect(queryClient.getQueryData<Account[]>(listKey)).toEqual([
      expect.objectContaining({ id: 2 }),
    ]);
    expect(queryClient.getQueryData(detailKey)).toBeUndefined();
  });

  it('does not prepend new accounts into page>1 caches', () => {
    const pageTwoKey = queryKeys.accounts.list({ search: 'acc', page: 2 });
    queryClient.setQueryData<Account[]>(pageTwoKey, [
      buildAccount({ id: 2, account_id: 'ACC-002' }),
    ]);

    upsertAccountCaches(buildAccount());

    expect(queryClient.getQueryData<Account[]>(pageTwoKey)).toEqual([
      expect.objectContaining({ id: 2, account_id: 'ACC-002' }),
    ]);
  });

  it('removes updated accounts from caches whose search no longer matches', () => {
    const listKey = queryKeys.accounts.list({ search: 'acc-001' });
    queryClient.setQueryData<Account[]>(listKey, [buildAccount()]);

    upsertAccountCaches(buildAccount({ account_id: 'LIVE-002' }));

    expect(queryClient.getQueryData<Account[]>(listKey)).toEqual([]);
  });

  it('re-inserts updated accounts into matching first-page caches', () => {
    const listKey = queryKeys.accounts.list({ search: 'live-002' });
    queryClient.setQueryData<Account[]>(listKey, []);

    upsertAccountCaches(buildAccount({ account_id: 'LIVE-002' }));

    expect(queryClient.getQueryData<Account[]>(listKey)).toEqual([
      expect.objectContaining({ account_id: 'LIVE-002' }),
    ]);
  });
});
