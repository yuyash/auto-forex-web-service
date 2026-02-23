/**
 * API Client Module
 *
 * Exports the API client, configuration, and types.
 */

// Export API types
export * from './types';

// Export API client
export { api, ApiError } from './apiClient';

// Export API config
export { apiConfig, getAuthHeaders, resolveToken } from './apiConfig';

// Export wrapper utilities
export {
  configureApiClient,
  setAuthToken,
  clearAuthToken,
  getAuthToken,
  isAuthenticated,
  transformApiError,
  withRetry,
  initializeApiClient,
  ApiErrorType,
  type ApiClientConfig,
  type TransformedApiError,
} from './client';
