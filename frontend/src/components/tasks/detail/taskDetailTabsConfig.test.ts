import { describe, expect, it } from 'vitest';
import type { TabItem } from '../../../hooks/useTabConfig';
import { visibleTabsForStrategy } from './taskDetailTabsConfig';

const tabs: TabItem[] = [
  { id: 'overview', label: 'Overview', visible: true },
  { id: 'strategy', label: 'Strategy', visible: true },
  { id: 'positions', label: 'Positions', visible: true },
  { id: 'trades', label: 'Trades', visible: true },
];

describe('visibleTabsForStrategy', () => {
  it('keeps positions for all strategy types', () => {
    expect(
      visibleTabsForStrategy(tabs, 'unknown').map((tab) => tab.id)
    ).toContain('positions');
  });
});
