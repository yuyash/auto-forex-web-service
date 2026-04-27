import { describe, expect, it } from 'vitest';
import type { TabItem } from '../../../hooks/useTabConfig';
import { visibleTabsForStrategy } from './taskDetailTabs';

const tabs: TabItem[] = [
  { id: 'overview', label: 'Overview', visible: true },
  { id: 'strategy', label: 'Strategy', visible: true },
  { id: 'positions', label: 'Positions', visible: true },
  { id: 'trades', label: 'Trades', visible: true },
];

describe('visibleTabsForStrategy', () => {
  it('hides positions for net_grid', () => {
    expect(
      visibleTabsForStrategy(tabs, 'net_grid').map((tab) => tab.id)
    ).toEqual(['overview', 'strategy', 'trades']);
  });

  it('keeps positions for snowball', () => {
    expect(
      visibleTabsForStrategy(tabs, 'snowball').map((tab) => tab.id)
    ).toContain('positions');
  });
});
