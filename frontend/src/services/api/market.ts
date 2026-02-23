/**
 * Market API service for direct HTTP requests to /api/market/ endpoints.
 */

import { apiConfig, getAuthHeaders } from '../../api/apiConfig';

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
  const base = apiConfig.BASE || '';
  const url = `${base}/api/market/ticks/data-range/?instrument=${encodeURIComponent(instrument)}`;
  const headers = await getAuthHeaders();

  const response = await fetch(url, {
    method: 'GET',
    headers,
    credentials: apiConfig.WITH_CREDENTIALS ? 'include' : 'same-origin',
  });

  if (!response.ok) {
    throw new Error(
      `Failed to fetch tick data range: ${response.status} ${response.statusText}`
    );
  }

  return response.json() as Promise<TickDataRange>;
}
