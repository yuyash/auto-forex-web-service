/**
 * Utility to fetch all trade pages from the paginated trades API.
 *
 * Used by TaskTrendPanel where the full trade set is needed for chart markers.
 * Supports incremental fetching via the `since` parameter so that polling
 * cycles only retrieve new/updated records.
 *
 * Includes automatic retry with exponential backoff for 429 responses.
 */

import { api } from '../api/apiClient';
import { apiConfig, resolveToken } from '../api/apiConfig';
import { TaskType } from '../types/common';
import axios, { AxiosError } from 'axios';
import type { PaginatedApiResponse } from '../api/types';

const MAX_PAGE_SIZE = 5000;
const MAX_PAGES = 50; // safety limit

/** Retry config for 429 Too Many Requests */
const MAX_RETRIES = 3;
const INITIAL_BACKOFF_MS = 1000;

/**
 * Sleep helper.
 */
function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Compute backoff delay from Retry-After header or exponential fallback.
 */
function getBackoffMs(
  retryAfterHeader: string | null | undefined,
  attempt: number
): number {
  if (retryAfterHeader) {
    const seconds = Number(retryAfterHeader);
    if (Number.isFinite(seconds) && seconds > 0) {
      return seconds * 1000;
    }
  }
  return INITIAL_BACKOFF_MS * Math.pow(2, attempt);
}

/**
 * Full fetch — retrieves all trades across all pages.
 * Used for the initial load.
 */
export async function fetchAllTrades(
  taskId: string,
  taskType: TaskType,
  executionRunId?: number
): Promise<Array<Record<string, unknown>>> {
  const prefix =
    taskType === TaskType.BACKTEST
      ? '/api/trading/tasks/backtest'
      : '/api/trading/tasks/trading';

  let allResults: Array<Record<string, unknown>> = [];
  let page = 1;

  while (page <= MAX_PAGES) {
    let response: PaginatedApiResponse<unknown> | null = null;

    for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
      try {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        response = await api.get<PaginatedApiResponse<any>>(
          `${prefix}/${taskId}/trades/`,
          {
            execution_run_id: executionRunId,
            page,
            page_size: MAX_PAGE_SIZE,
          }
        );
        break; // success
      } catch (err: unknown) {
        const status =
          err instanceof AxiosError ? err.response?.status : undefined;
        if (status === 429 && attempt < MAX_RETRIES) {
          const retryAfter =
            err instanceof AxiosError
              ? err.response?.headers?.['retry-after']
              : undefined;
          await sleep(getBackoffMs(retryAfter, attempt));
          continue;
        }
        throw err;
      }
    }

    if (!response) break;

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
 * Returns trades across pages which is sufficient for
 * polling intervals where only a few new trades appear between cycles.
 */
export async function fetchTradesSince(
  taskId: string,
  taskType: TaskType,
  since: string,
  executionRunId?: number
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
    if (executionRunId != null) {
      params.execution_run_id = String(executionRunId);
    }

    let responseData: Record<string, unknown> | null = null;

    for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
      try {
        const response = await axios.get(url, {
          params,
          headers,
          withCredentials: apiConfig.WITH_CREDENTIALS,
        });
        responseData = response.data as Record<string, unknown>;
        break; // success
      } catch (err: unknown) {
        const status =
          err instanceof AxiosError ? err.response?.status : undefined;
        if (status === 429 && attempt < MAX_RETRIES) {
          const retryAfter =
            err instanceof AxiosError
              ? err.response?.headers?.['retry-after']
              : undefined;
          await sleep(getBackoffMs(retryAfter, attempt));
          continue;
        }
        throw err;
      }
    }

    if (!responseData) break;

    const results = (responseData.results || []) as Array<
      Record<string, unknown>
    >;
    allResults = allResults.concat(results);

    if (!responseData.next) break;
    page++;
  }

  return allResults;
}
