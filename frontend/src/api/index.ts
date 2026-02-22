/**
 * API Client Module
 *
 * Exports the generated OpenAPI client and wrapper utilities.
 */

// Export generated client
export * from './generated';

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
