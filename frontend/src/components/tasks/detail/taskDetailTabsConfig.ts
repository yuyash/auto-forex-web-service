import type { TabItem } from '../../../hooks/useTabConfig';

/**
 * Filter visible tabs based on the active strategy type.
 *
 * - ``snowball_net``: hides the "positions" tab because netting strategies
 *   do not track independent hedge-side positions.
 */
export function visibleTabsForStrategy(
  tabs: TabItem[],
  strategyType?: string
): TabItem[] {
  if (strategyType === 'snowball_net') {
    return tabs.filter((tab) => tab.id !== 'positions');
  }
  return tabs;
}
