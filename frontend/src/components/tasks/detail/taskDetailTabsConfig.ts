import type { TabItem } from '../../../hooks/useTabConfig';

/**
 * Filter visible tabs based on the active strategy type.
 *
 * - ``snowball_net``: hides the "positions" tab (netting strategies don't
 *   track individual positions) and the "metrics" tab (the strategy tab
 *   already surfaces the same time-series data).
 */
export function visibleTabsForStrategy(
  tabs: TabItem[],
  strategyType?: string
): TabItem[] {
  if (strategyType === 'snowball_net') {
    return tabs.filter((tab) => tab.id !== 'positions' && tab.id !== 'metrics');
  }
  return tabs;
}
