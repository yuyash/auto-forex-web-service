import { describe, expect, it } from 'vitest';
import { applyItemOrder } from '../../../src/hooks/useItemOrder';

describe('applyItemOrder', () => {
  it('orders known items and appends newly available items', () => {
    const items = [
      { id: 'a', label: 'A' },
      { id: 'b', label: 'B' },
      { id: 'c', label: 'C' },
      { id: 'd', label: 'D' },
    ];

    const ordered = applyItemOrder(items, ['c', 'a', 'missing']);

    expect(ordered.map((item) => item.id)).toEqual(['c', 'a', 'b', 'd']);
  });

  it('ignores duplicate saved ids', () => {
    const items = [
      { id: 'a', label: 'A' },
      { id: 'b', label: 'B' },
    ];

    const ordered = applyItemOrder(items, ['b', 'b', 'a']);

    expect(ordered.map((item) => item.id)).toEqual(['b', 'a']);
  });
});
