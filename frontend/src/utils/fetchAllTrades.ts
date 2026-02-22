/**
 * Utility to fetch all trade pages from the paginated trades API.
 *
 * Used by useOverviewPnl and TaskReplayPanel where the full trade set
 * is needed for PnL calculation and chart markers.
 */

import { TradingService } from '../api/generated/services/TradingService';
import { TaskType } from '../types/common';

const MAX_PAGE_SIZE = 1000;
const MAX_PAGES = 50; // safety limit

export async function fetchAllTrades(
  taskId: string,
  taskType: TaskType
): Promise<Array<Record<string, unknown>>> {
  const fetcher =
    taskType === TaskType.BACKTEST
      ? TradingService.tradingTasksBacktestTradesList
      : TradingService.tradingTasksTradingTradesList;

  let allResults: Array<Record<string, unknown>> = [];
  let page = 1;

  while (page <= MAX_PAGES) {
    const response = await fetcher(
      taskId,
      undefined, // celeryTaskId
      undefined, // direction
      undefined, // ordering
      page,
      MAX_PAGE_SIZE
    );

    const results = (response.results || []) as Array<Record<string, unknown>>;
    allResults = allResults.concat(results);

    if (!response.next) break;
    page++;
  }

  return allResults;
}
