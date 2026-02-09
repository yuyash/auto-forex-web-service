/**
 * API Client Wrapper
 *
 * Provides a configured wrapper around the generated OpenAPI client with:
 * - Authentication token management
 * - Error handling and transformation
 * - Retry logic for transient failures
 * - Base URL configuration
 */

import { OpenAPI } from './generated/core/OpenAPI';
import { ApiError } from './generated/core/ApiError';
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

  // Update OpenAPI configuration
  OpenAPI.BASE = currentConfig.baseUrl;
  OpenAPI.WITH_CREDENTIALS = currentConfig.withCredentials;
  OpenAPI.TOKEN = currentConfig.token;

  // Set up request interceptor for authentication
  OpenAPI.HEADERS = async () => {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };

    if (currentConfig.token) {
      headers['Authorization'] = `Bearer ${currentConfig.token}`;
    }

    return headers;
  };

  // Set up response interceptor for 401 errors
  const originalRequest = OpenAPI.request;
  OpenAPI.request = async (options: unknown) => {
    const requestOptions = options as Record<string, unknown>;
    const requestId = Math.random().toString(36).substring(7);
    const timestamp = new Date().toISOString();

    console.log(`[API:REQUEST:${requestId}] ${timestamp}`, {
      method: requestOptions.method,
      url: requestOptions.url,
      body: requestOptions.body,
      headers: requestOptions.headers,
    });

    try {
      const response = await originalRequest(options);

      console.log(`[API:RESPONSE:${requestId}] ${timestamp} SUCCESS`, {
        method: requestOptions.method,
        url: requestOptions.url,
        status: 200,
        data: response,
      });

      return response;
    } catch (error) {
      if (error instanceof ApiError) {
        console.error(`[API:RESPONSE:${requestId}] ${timestamp} ERROR`, {
          method: requestOptions.method,
          url: requestOptions.url,
          status: error.status,
          statusText: error.statusText,
          body: error.body,
          message: error.message,
        });

        if (error.status === 401) {
          console.warn(
            `[API:AUTH] 401 Unauthorized - Clearing auth and redirecting to login`
          );
          // Clear authentication state
          localStorage.removeItem('token');
          localStorage.removeItem('user');
          clearAuthToken();

          // Broadcast logout event for AuthContext to handle
          broadcastAuthLogout({
            source: 'http',
            status: 401,
            message: 'Session expired',
            context: 'api_client',
          });

          // Redirect to login page
          window.location.href = '/login';
        }
      } else {
        console.error(
          `[API:RESPONSE:${requestId}] ${timestamp} NETWORK_ERROR`,
          {
            method: requestOptions.method,
            url: requestOptions.url,
            error: error,
          }
        );
      }
      throw error;
    }
  };
}

/**
 * Set authentication token
 */
export function setAuthToken(token: string): void {
  currentConfig.token = token;
  OpenAPI.TOKEN = token;
}

/**
 * Clear authentication token
 */
export function clearAuthToken(): void {
  currentConfig.token = '';
  OpenAPI.TOKEN = undefined;
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
      (error.statusCode === 429 || // Rate limit
        error.statusCode >= 500)) // Server errors
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

      // Don't retry if error is not retryable or we've exhausted retries
      if (!isRetryableError(lastError) || attempt === maxRetries) {
        throw lastError;
      }

      // Exponential backoff
      const delayMs = retryDelay * Math.pow(2, attempt);
      await delay(delayMs);
    }
  }

  // This should never be reached, but TypeScript needs it
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
