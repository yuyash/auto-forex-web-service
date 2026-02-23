/**
 * Simple API client wrapper for direct HTTP requests
 * Used by components that need raw API access outside the service layer.
 */

import { apiConfig, getAuthHeaders } from '../../api/apiConfig';

export const apiClient = {
  async get<T>(url: string): Promise<T> {
    const base = apiConfig.BASE || '';
    const fullUrl = `${base}/api/trading${url}`;
    const headers = await getAuthHeaders();

    const response = await fetch(fullUrl, {
      method: 'GET',
      headers,
      credentials: apiConfig.WITH_CREDENTIALS ? 'include' : 'same-origin',
    });

    if (!response.ok) {
      throw new Error(
        `API request failed: ${response.status} ${response.statusText}`
      );
    }

    return response.json() as Promise<T>;
  },
};
