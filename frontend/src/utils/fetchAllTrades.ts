/**
 * Utility to fetch all trade pages from the paginated trades API.
 *
 * Used by TaskTrendPanel where the full trade set is needed for chart markers.
 * Supports incremental fetching via the `since` parameter so that polling
 * cycles only retrieve new/updated records.
 *
 * Includes automatic retry with exponential backoff for 429 responses.
 */

import { TaskType } from '../types/common';
import { ApiError } from '../api/apiClient';
import {
  fetchAllTaskResourcePages,
  isApiErrorWithStatus,
} from '../services/api/taskResources';

const MAX_PAGE_SIZE = 5000;

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
  executionRunId?: string
): Promise<Array<Record<string, unknown>>> {
  return fetchWithRetry(taskId, taskType, {
    execution_id: executionRunId,
    page: 1,
    page_size: MAX_PAGE_SIZE,
  });
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
  executionRunId?: string
): Promise<Array<Record<string, unknown>>> {
  return fetchWithRetry(taskId, taskType, {
    execution_id: executionRunId,
    since,
    page: 1,
    page_size: MAX_PAGE_SIZE,
  });
}

async function fetchWithRetry(
  taskId: string,
  taskType: TaskType,
  params: Record<string, string | number | undefined>
): Promise<Array<Record<string, unknown>>> {
  for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
    try {
      return await fetchAllTaskResourcePages<Record<string, unknown>>(
        taskType,
        taskId,
        'trades',
        params
      );
    } catch (err) {
      const status = isApiErrorWithStatus(err) ? err.status : undefined;
      if (status === 429 && attempt < MAX_RETRIES) {
        const retryAfter = getRetryAfterHeader(err);
        await sleep(getBackoffMs(retryAfter, attempt));
        continue;
      }
      throw err;
    }
  }

  return [];
}

function getRetryAfterHeader(error: unknown): string | null | undefined {
  if (
    !(error instanceof ApiError) ||
    !error.body ||
    typeof error.body !== 'object'
  ) {
    return undefined;
  }

  const maybeRetryAfter = (error.body as { retry_after?: unknown }).retry_after;
  if (typeof maybeRetryAfter === 'number') {
    return String(maybeRetryAfter);
  }
  if (typeof maybeRetryAfter === 'string') {
    return maybeRetryAfter;
  }
  return undefined;
}
