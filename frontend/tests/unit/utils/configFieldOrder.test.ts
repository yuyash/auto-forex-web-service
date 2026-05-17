import { describe, expect, it } from 'vitest';
import { orderConfigEntries } from '../../../src/utils/configFieldOrder';

describe('orderConfigEntries', () => {
  it('puts refill limit options below the pending re-seed option', () => {
    const ordered = orderConfigEntries([
      { key: 'refill_limit_enabled' },
      { key: 'refill_up_to' },
      { key: 'reseed_on_all_pending' },
      { key: 'rebuild_entry_price_mode' },
      { key: 'rebuild_enabled' },
    ]).map(({ key }) => key);

    expect(ordered).toEqual([
      'rebuild_enabled',
      'rebuild_entry_price_mode',
      'reseed_on_all_pending',
      'refill_limit_enabled',
      'refill_up_to',
    ]);
  });
});
