import { describe, expect, it } from 'vitest';
import { orderConfigEntries } from '../../../src/utils/configFieldOrder';

describe('orderConfigEntries', () => {
  it('puts the stop-loss rebuild toggle before refill limit options', () => {
    const ordered = orderConfigEntries([
      { key: 'refill_limit_enabled' },
      { key: 'refill_up_to' },
      { key: 'rebuild_entry_price_mode' },
      { key: 'rebuild_enabled' },
    ]).map(({ key }) => key);

    expect(ordered).toEqual([
      'rebuild_enabled',
      'rebuild_entry_price_mode',
      'refill_limit_enabled',
      'refill_up_to',
    ]);
  });
});
