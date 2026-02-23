/**
 * Utility to fetch all trade pages from the paginated trades API.
 *
 * Used by TaskReplayPanel where the full trade set is needed for chart markers.
 * Supports incremental fetching via the `since` parameter so that polling
 * cycles only retrieve new/updated records.
 */

import { TradingService } from '../api/generated/services/TradingService';
import { TaskType } from '../types/common';
import axios from 'axios';
import { OpenAPI } from '../api/generated/core/OpenAPI';

const MAX_PAGE_SIZE = 1000;
const MAX_PAGES = 50; // safety limit

/**
 * Full fetch — retrieves all trades across all pages.
 * Used for the initial load.
 */
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

async function getAuthHeaders(): Promise<Record<string, string>> {
  const headers: Record<string, string> = { Accept: 'application/json' };
  if (OpenAPI.TOKEN) {
    const token =
      typeof OpenAPI.TOKEN === 'function'
        ? await (OpenAPI.TOKEN as (options: unknown) => Promise<string>)({})
        : OpenAPI.TOKEN;
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
  }
  return headers;
}

/**
 * Incremental fetch — retrieves only trades updated after `since`.
 * Returns a single page (up to MAX_PAGE_SIZE) which is sufficient for
 * polling intervals where only a few new trades appear between cycles.
 */
export async function fetchTradesSince(
  taskId: string,
  taskType: TaskType,
  since: string
): Promise<Array<Record<string, unknown>>> {
  const prefix =
    taskType === TaskType.BACKTEST
      ? '/api/trading/tasks/backtest'
      : '/api/trading/tasks/trading';

  const url = `${OpenAPI.BASE}${prefix}/${taskId}/trades/`;
  const headers = await getAuthHeaders();

  let allResults: Array<Record<string, unknown>> = [];
  let page = 1;

  while (page <= MAX_PAGES) {
    const response = await axios.get(url, {
      params: {
        since,
        page: String(page),
        page_size: String(MAX_PAGE_SIZE),
      },
      headers,
      withCredentials: OpenAPI.WITH_CREDENTIALS,
    });

    const results = (response.data.results || []) as Array<
      Record<string, unknown>
    >;
    allResults = allResults.concat(results);

    if (!response.data.next) break;
    page++;
  }

  return allResults;
}
