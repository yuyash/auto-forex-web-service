import type { TabItem } from '../../../hooks/useTabConfig';

export function visibleTabsForStrategy(
  tabs: TabItem[],
  strategyType?: string
): TabItem[] {
  if (strategyType === 'snowball_net') {
    return tabs.filter((tab) => tab.id !== 'positions');
  }
  return tabs;
}
