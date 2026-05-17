import { describe, expect, it } from 'vitest';
import { orderConfigEntries } from '../../../src/utils/configFieldOrder';

describe('orderConfigEntries', () => {
  it('orders counter-side layer settings before stop-loss settings', () => {
    const ordered = orderConfigEntries([
      { key: 'refill_limit_enabled' },
      { key: 'refill_up_to' },
      { key: 'stop_loss_enabled' },
      { key: 'post_r_max_base_factor' },
      { key: 'f_max' },
      { key: 'r_max' },
    ]).map(({ key }) => key);

    expect(ordered).toEqual([
      'r_max',
      'f_max',
      'post_r_max_base_factor',
      'refill_limit_enabled',
      'refill_up_to',
      'stop_loss_enabled',
    ]);
  });
});
