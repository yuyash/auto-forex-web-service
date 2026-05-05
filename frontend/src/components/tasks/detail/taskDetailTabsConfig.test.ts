import { describe, expect, it } from 'vitest';
import type { TabItem } from '../../../hooks/useTabConfig';
import { visibleTabsForStrategy } from './taskDetailTabsConfig';

const tabs: TabItem[] = [
  { id: 'overview', label: 'Overview', visible: true },
  { id: 'strategy', label: 'Strategy', visible: true },
  { id: 'positions', label: 'Positions', visible: true },
  { id: 'trades', label: 'Trades', visible: true },
  { id: 'metrics', label: 'Metrics', visible: true },
];

describe('visibleTabsForStrategy', () => {
  it('keeps positions and metrics for all strategy types', () => {
    const ids = visibleTabsForStrategy(tabs, 'unknown').map((tab) => tab.id);
    expect(ids).toContain('positions');
    expect(ids).toContain('metrics');
  });

  it('hides positions but keeps metrics for SnowballNet', () => {
    const ids = visibleTabsForStrategy(tabs, 'snowball_net').map(
      (tab) => tab.id
    );
    expect(ids).not.toContain('positions');
    expect(ids).toContain('metrics');
  });
});
