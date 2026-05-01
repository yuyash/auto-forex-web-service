import type { TabItem } from '../../../hooks/useTabConfig';

export function visibleTabsForStrategy(
  tabs: TabItem[],
  _strategyType?: string
): TabItem[] {
  void _strategyType;
  return tabs;
}
