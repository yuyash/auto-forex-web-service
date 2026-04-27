import type { TabItem } from '../../../hooks/useTabConfig';

export function visibleTabsForStrategy(
  tabs: TabItem[],
  strategyType?: string | null
): TabItem[] {
  if (strategyType !== 'net_grid') return tabs;
  return tabs.filter((tab) => tab.id !== 'positions');
}
