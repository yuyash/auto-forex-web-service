/**
 * API Configuration
 *
 * Centralized configuration for API requests, replacing the generated OpenAPI config.
 * All hooks and services should import from here instead of the old generated/core/OpenAPI.
 */

type TokenResolver = (options: unknown) => Promise<string>;

export interface ApiConfig {
  BASE: string;
  TOKEN?: string | TokenResolver | undefined;
  WITH_CREDENTIALS: boolean;
  HEADERS?: Record<string, string> | (() => Promise<Record<string, string>>);
}

export const apiConfig: ApiConfig = {
  BASE: import.meta.env.VITE_API_BASE_URL || '',
  TOKEN: undefined,
  WITH_CREDENTIALS: true,
};

/**
 * Helper to resolve the current auth token from apiConfig.
 */
export async function resolveToken(): Promise<string | undefined> {
  if (!apiConfig.TOKEN) return undefined;
  if (typeof apiConfig.TOKEN === 'function') {
    return apiConfig.TOKEN({});
  }
  return apiConfig.TOKEN;
}

/**
 * Build auth headers from the current apiConfig.
 */
export async function getAuthHeaders(): Promise<Record<string, string>> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  const token = await resolveToken();
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
}
