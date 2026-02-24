/**
 * Global Axios interceptor for 429 Too Many Requests.
 *
 * Automatically retries failed requests with exponential backoff
 * when the server returns 429.  Respects the Retry-After header
 * when present.
 *
 * Call `installRetryInterceptor()` once at app startup.
 */

import axios, { type AxiosError, type InternalAxiosRequestConfig } from 'axios';

const MAX_RETRIES = 3;
const INITIAL_BACKOFF_MS = 1_000;

interface RetryMeta {
  __retryCount?: number;
}

function getBackoffMs(
  retryAfter: string | null | undefined,
  attempt: number
): number {
  if (retryAfter) {
    const seconds = Number(retryAfter);
    if (Number.isFinite(seconds) && seconds > 0) {
      return seconds * 1_000;
    }
  }
  return INITIAL_BACKOFF_MS * Math.pow(2, attempt);
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export function installRetryInterceptor(): void {
  axios.interceptors.response.use(undefined, async (error: AxiosError) => {
    const config = error.config as
      | (InternalAxiosRequestConfig & RetryMeta)
      | undefined;
    if (!config || error.response?.status !== 429) {
      return Promise.reject(error);
    }

    const retryCount = config.__retryCount ?? 0;
    if (retryCount >= MAX_RETRIES) {
      return Promise.reject(error);
    }

    config.__retryCount = retryCount + 1;

    const retryAfter = error.response?.headers?.['retry-after'] as
      | string
      | undefined;
    const delayMs = getBackoffMs(retryAfter, retryCount);

    await sleep(delayMs);
    return axios(config);
  });
}
