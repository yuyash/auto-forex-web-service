/**
 * API Client Wrapper
 *
 * Provides authentication token management, error handling,
 * retry logic, and base URL configuration.
 */

import { apiConfig } from './apiConfig';
import { ApiError } from './apiClient';
import { broadcastAuthLogout } from '../utils/authEvents';

/**
 * API Client Configuration
 */
export interface ApiClientConfig {
  baseUrl?: string;
  token?: string;
  withCredentials?: boolean;
  maxRetries?: number;
  retryDelay?: number;
}

/**
 * Default configuration
 *
 * In development, we use an empty baseUrl to let Vite's proxy handle /api requests.
 * The proxy is configured in vite.config.ts to forward /api -> http://localhost:8000
 * This avoids CORS issues during development.
 *
 * In production, set VITE_API_BASE_URL to your backend URL.
 */
const DEFAULT_CONFIG: Required<ApiClientConfig> = {
  baseUrl: import.meta.env.VITE_API_BASE_URL || '',
  token: '',
  withCredentials: true,
  maxRetries: 3,
  retryDelay: 1000,
};

/**
 * Current configuration
 */
let currentConfig: Required<ApiClientConfig> = { ...DEFAULT_CONFIG };

/**
 * Configure the API client
 */
export function configureApiClient(config: ApiClientConfig): void {
  currentConfig = { ...currentConfig, ...config };

  // Sync to apiConfig so all modules share the same state
  apiConfig.BASE = currentConfig.baseUrl;
  apiConfig.WITH_CREDENTIALS = currentConfig.withCredentials;
  apiConfig.TOKEN = currentConfig.token || undefined;
}

/**
 * Set authentication token
 */
export function setAuthToken(token: string): void {
  currentConfig.token = token;
  apiConfig.TOKEN = token;
}

/**
 * Clear authentication token
 */
export function clearAuthToken(): void {
  currentConfig.token = '';
  apiConfig.TOKEN = undefined;
}

/**
 * Get current authentication token
 */
export function getAuthToken(): string {
  return currentConfig.token;
}

/**
 * Check if user is authenticated
 */
export function isAuthenticated(): boolean {
  return !!currentConfig.token;
}

/**
 * Error types for better error handling
 */
export enum ApiErrorType {
  NETWORK_ERROR = 'NETWORK_ERROR',
  AUTHENTICATION_ERROR = 'AUTHENTICATION_ERROR',
  AUTHORIZATION_ERROR = 'AUTHORIZATION_ERROR',
  VALIDATION_ERROR = 'VALIDATION_ERROR',
  NOT_FOUND_ERROR = 'NOT_FOUND_ERROR',
  SERVER_ERROR = 'SERVER_ERROR',
  UNKNOWN_ERROR = 'UNKNOWN_ERROR',
}

/**
 * Transformed API error with additional context
 */
export interface TransformedApiError {
  type: ApiErrorType;
  message: string;
  statusCode?: number;
  details?: unknown;
  originalError: Error;
}

/**
 * Transform API errors into a consistent format
 */
export function transformApiError(error: unknown): TransformedApiError {
  if (error instanceof ApiError) {
    const statusCode = error.status;
    let type: ApiErrorType;
    let message: string;

    switch (statusCode) {
      case 400:
        type = ApiErrorType.VALIDATION_ERROR;
        message = 'Validation error. Please check your input.';
        break;
      case 401:
        type = ApiErrorType.AUTHENTICATION_ERROR;
        message = 'Authentication required. Please log in.';
        break;
      case 403:
        type = ApiErrorType.AUTHORIZATION_ERROR;
        message = 'You do not have permission to perform this action.';
        break;
      case 404:
        type = ApiErrorType.NOT_FOUND_ERROR;
        message = 'The requested resource was not found.';
        break;
      case 422:
        type = ApiErrorType.VALIDATION_ERROR;
        message = 'Validation error. Please check your input.';
        break;
      case 500:
      case 502:
      case 503:
      case 504:
        type = ApiErrorType.SERVER_ERROR;
        message = 'Server error. Please try again later.';
        break;
      default:
        type = ApiErrorType.UNKNOWN_ERROR;
        message = error.message || 'An unexpected error occurred.';
    }

    // Handle 401 globally — clear credentials and let React Router
    // redirect via AuthContext state change.  Avoid window.location.href
    // to prevent race conditions with concurrent React state updates and
    // a full page reload that depends on systemSettings fetch succeeding.
    if (statusCode === 401) {
      console.warn(`[API:AUTH] 401 Unauthorized - Clearing auth state`);
      localStorage.removeItem('token');
      localStorage.removeItem('refresh_token');
      localStorage.removeItem('user');
      clearAuthToken();
      broadcastAuthLogout({
        source: 'http',
        status: 401,
        message: 'Session expired',
        context: 'api_client',
      });
    }

    return {
      type,
      message,
      statusCode,
      details: error.body,
      originalError: error,
    };
  }

  // Network errors or other errors
  if (error instanceof Error) {
    return {
      type: ApiErrorType.NETWORK_ERROR,
      message: 'Network error. Please check your connection.',
      originalError: error,
    };
  }

  // Unknown error type
  return {
    type: ApiErrorType.UNKNOWN_ERROR,
    message: 'An unexpected error occurred.',
    originalError: new Error(String(error)),
  };
}

/**
 * Check if an error is retryable
 */
function isRetryableError(error: TransformedApiError): boolean {
  return (
    error.type === ApiErrorType.NETWORK_ERROR ||
    error.type === ApiErrorType.SERVER_ERROR ||
    (error.statusCode !== undefined &&
      (error.statusCode === 429 || error.statusCode >= 500))
  );
}

/**
 * Delay helper for retry logic
 */
function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Retry wrapper for API calls
 */
export async function withRetry<T>(
  fn: () => Promise<T>,
  options?: { maxRetries?: number; retryDelay?: number }
): Promise<T> {
  const maxRetries = options?.maxRetries ?? currentConfig.maxRetries;
  const retryDelay = options?.retryDelay ?? currentConfig.retryDelay;

  let lastError: TransformedApiError | null = null;

  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      return await fn();
    } catch (error) {
      lastError = transformApiError(error);

      if (!isRetryableError(lastError) || attempt === maxRetries) {
        throw lastError;
      }

      const delayMs = retryDelay * Math.pow(2, attempt);
      await delay(delayMs);
    }
  }

  throw lastError!;
}

/**
 * Initialize the API client with default configuration
 */
export function initializeApiClient(config?: ApiClientConfig): void {
  configureApiClient(config || {});
}

// Initialize with default configuration on module load
initializeApiClient();
