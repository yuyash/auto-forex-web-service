/**
 * Simple API client wrapper for direct HTTP requests
 * Used by components that need raw API access outside the generated OpenAPI client.
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

export const apiClient = {
  async get<T>(url: string): Promise<T> {
    const base = OpenAPI.BASE || '';
    const fullUrl = `${base}/api/trading${url}`;
    const headers = await getHeaders();

    const response = await fetch(fullUrl, {
      method: 'GET',
      headers,
      credentials: OpenAPI.WITH_CREDENTIALS ? 'include' : 'same-origin',
    });

    if (!response.ok) {
      throw new Error(
        `API request failed: ${response.status} ${response.statusText}`
      );
    }

    return response.json() as Promise<T>;
  },
};
