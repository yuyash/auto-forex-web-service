import axios from 'axios';

function getHeaderValue(headers: unknown, key: string): string | null {
  if (!headers || typeof headers !== 'object') {
    return null;
  }

  const record = headers as Record<string, unknown>;
  const value = record[key] ?? record[key.toLowerCase()] ?? null;
  return typeof value === 'string' ? value : null;
}

export function getRetryAfterMs(
  retryAfterHeader: string | null | undefined,
  fallbackMs = 30_000
): number {
  if (!retryAfterHeader) {
    return fallbackMs;
  }

  const seconds = Number(retryAfterHeader);
  if (Number.isFinite(seconds) && seconds > 0) {
    return Math.max(seconds * 1000, 1000);
  }

  const retryAt = Date.parse(retryAfterHeader);
  if (Number.isFinite(retryAt)) {
    return Math.max(retryAt - Date.now(), 1000);
  }

  return fallbackMs;
}

export function getRetryAfterMsFromError(
  error: unknown,
  fallbackMs = 30_000
): number | null {
  if (axios.isAxiosError(error)) {
    if (error.response?.status !== 429) {
      return null;
    }
    return getRetryAfterMs(
      getHeaderValue(error.response.headers, 'retry-after'),
      fallbackMs
    );
  }

  if (error instanceof Response) {
    if (error.status !== 429) {
      return null;
    }
    return getRetryAfterMs(error.headers.get('Retry-After'), fallbackMs);
  }

  return null;
}
