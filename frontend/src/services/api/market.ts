/**
 * Market API service for direct HTTP requests to /api/market/ endpoints.
 */

import { OpenAPI } from '../../api/generated/core/OpenAPI';

async function getHeaders(): Promise<Record<string, string>> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };

  if (typeof OpenAPI.TOKEN === 'string' && OpenAPI.TOKEN) {
    headers['Authorization'] = `Bearer ${OpenAPI.TOKEN}`;
  } else if (typeof OpenAPI.TOKEN === 'function') {
    const token = await OpenAPI.TOKEN({
      method: 'GET',
      url: '',
    } as Parameters<Exclude<typeof OpenAPI.TOKEN, string | undefined>>[0]);
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
  }

  return headers;
}

export interface TickDataRange {
  instrument: string;
  has_data: boolean;
  min_timestamp: string | null;
  max_timestamp: string | null;
}

/**
 * Fetch the available tick data date range for a given instrument.
 */
export async function fetchTickDataRange(
  instrument: string
): Promise<TickDataRange> {
  const base = OpenAPI.BASE || '';
  const url = `${base}/api/market/ticks/data-range/?instrument=${encodeURIComponent(instrument)}`;
  const headers = await getHeaders();

  const response = await fetch(url, {
    method: 'GET',
    headers,
    credentials: OpenAPI.WITH_CREDENTIALS ? 'include' : 'same-origin',
  });

  if (!response.ok) {
    throw new Error(
      `Failed to fetch tick data range: ${response.status} ${response.statusText}`
    );
  }

  return response.json() as Promise<TickDataRange>;
}
