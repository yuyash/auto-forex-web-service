/**
 * Utility to fetch all trade pages from the paginated trades API.
 *
 * Used by TaskReplayPanel where the full trade set is needed for chart markers.
 * Supports incremental fetching via the `since` parameter so that polling
 * cycles only retrieve new/updated records.
 */

import { api } from '../api/apiClient';
import { apiConfig, resolveToken } from '../api/apiConfig';
import { TaskType } from '../types/common';
import axios from 'axios';
import type { PaginatedApiResponse } from '../api/types';

const MAX_PAGE_SIZE = 1000;
const MAX_PAGES = 50; // safety limit

/**
 * Full fetch — retrieves all trades across all pages.
 * Used for the initial load.
 */
export async function fetchAllTrades(
  taskId: string,
  taskType: TaskType,
  celeryTaskId?: string
): Promise<Array<Record<string, unknown>>> {
  const prefix =
    taskType === TaskType.BACKTEST
      ? '/api/trading/tasks/backtest'
      : '/api/trading/tasks/trading';

  let allResults: Array<Record<string, unknown>> = [];
  let page = 1;

  while (page <= MAX_PAGES) {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const response = await api.get<PaginatedApiResponse<any>>(
      `${prefix}/${taskId}/trades/`,
      {
        celery_task_id: celeryTaskId,
        page,
        page_size: MAX_PAGE_SIZE,
      }
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
  const token = await resolveToken();
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
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
  since: string,
  celeryTaskId?: string
): Promise<Array<Record<string, unknown>>> {
  const prefix =
    taskType === TaskType.BACKTEST
      ? '/api/trading/tasks/backtest'
      : '/api/trading/tasks/trading';

  const url = `${apiConfig.BASE}${prefix}/${taskId}/trades/`;
  const headers = await getAuthHeaders();

  let allResults: Array<Record<string, unknown>> = [];
  let page = 1;

  while (page <= MAX_PAGES) {
    const params: Record<string, string> = {
      since,
      page: String(page),
      page_size: String(MAX_PAGE_SIZE),
    };
    if (celeryTaskId) params.celery_task_id = celeryTaskId;

    const response = await axios.get(url, {
      params,
      headers,
      withCredentials: apiConfig.WITH_CREDENTIALS,
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
