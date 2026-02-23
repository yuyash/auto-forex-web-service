/**
 * Unit tests for API client wrapper
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import {
  configureApiClient,
  setAuthToken,
  clearAuthToken,
  getAuthToken,
  isAuthenticated,
  transformApiError,
  withRetry,
  ApiErrorType,
} from '../../../src/api/client';
import { apiConfig } from '../../../src/api/apiConfig';
import { ApiError } from '../../../src/api/apiClient';

describe('API Client Configuration', () => {
  beforeEach(() => {
    // Reset configuration before each test
    configureApiClient({
      baseUrl: 'http://localhost:8000',
      token: '',
      withCredentials: true,
    });
  });

  it('should configure base URL', () => {
    const baseUrl = 'https://api.example.com';
    configureApiClient({ baseUrl });

    expect(apiConfig.BASE).toBe(baseUrl);
  });

  it('should configure credentials', () => {
    configureApiClient({ withCredentials: false });
    expect(apiConfig.WITH_CREDENTIALS).toBe(false);

    configureApiClient({ withCredentials: true });
    expect(apiConfig.WITH_CREDENTIALS).toBe(true);
  });

  it('should configure authentication token', () => {
    const token = 'test-token-123';
    configureApiClient({ token });

    expect(apiConfig.TOKEN).toBe(token);
  });

  it('should merge configuration with defaults', () => {
    const baseUrl = 'https://api.example.com';
    configureApiClient({ baseUrl });

    // Other defaults should remain
    expect(apiConfig.WITH_CREDENTIALS).toBe(true);
  });
});

describe('Authentication Token Management', () => {
  beforeEach(() => {
    clearAuthToken();
  });

  it('should set authentication token', () => {
    const token = 'test-token-456';
    setAuthToken(token);

    expect(getAuthToken()).toBe(token);
    expect(apiConfig.TOKEN).toBe(token);
  });

  it('should clear authentication token', () => {
    setAuthToken('test-token');
    clearAuthToken();

    expect(getAuthToken()).toBe('');
    expect(apiConfig.TOKEN).toBeUndefined();
  });

  it('should check if user is authenticated', () => {
    expect(isAuthenticated()).toBe(false);

    setAuthToken('test-token');
    expect(isAuthenticated()).toBe(true);

    clearAuthToken();
    expect(isAuthenticated()).toBe(false);
  });

  it('should handle empty token as unauthenticated', () => {
    setAuthToken('');
    expect(isAuthenticated()).toBe(false);
  });
});

describe('Error Transformation', () => {
  it('should transform 401 authentication error', () => {
    const apiError = new ApiError('/api/test', 401, 'Unauthorized', {
      detail: 'Invalid token',
    });

    const transformed = transformApiError(apiError);

    expect(transformed.type).toBe(ApiErrorType.AUTHENTICATION_ERROR);
    expect(transformed.statusCode).toBe(401);
    expect(transformed.message).toContain('Authentication required');
    expect(transformed.originalError).toBe(apiError);
  });

  it('should transform 403 authorization error', () => {
    const apiError = new ApiError('/api/test', 403, 'Forbidden', {
      detail: 'Permission denied',
    });

    const transformed = transformApiError(apiError);

    expect(transformed.type).toBe(ApiErrorType.AUTHORIZATION_ERROR);
    expect(transformed.statusCode).toBe(403);
    expect(transformed.message).toContain('permission');
  });

  it('should transform 404 not found error', () => {
    const apiError = new ApiError('/api/test/123', 404, 'Not Found', {
      detail: 'Resource not found',
    });

    const transformed = transformApiError(apiError);

    expect(transformed.type).toBe(ApiErrorType.NOT_FOUND_ERROR);
    expect(transformed.statusCode).toBe(404);
    expect(transformed.message).toContain('not found');
  });

  it('should transform 422 validation error', () => {
    const apiError = new ApiError('/api/test', 422, 'Unprocessable Entity', {
      errors: [{ field: 'name', message: 'Required' }],
    });

    const transformed = transformApiError(apiError);

    expect(transformed.type).toBe(ApiErrorType.VALIDATION_ERROR);
    expect(transformed.statusCode).toBe(422);
    expect(transformed.message).toContain('Validation error');
    expect(transformed.details).toBeDefined();
  });

  it('should transform 500 server error', () => {
    const apiError = new ApiError('/api/test', 500, 'Internal Server Error', {
      detail: 'Server error',
    });

    const transformed = transformApiError(apiError);

    expect(transformed.type).toBe(ApiErrorType.SERVER_ERROR);
    expect(transformed.statusCode).toBe(500);
    expect(transformed.message).toContain('Server error');
  });

  it('should transform network error', () => {
    const networkError = new Error('Network request failed');

    const transformed = transformApiError(networkError);

    expect(transformed.type).toBe(ApiErrorType.NETWORK_ERROR);
    expect(transformed.message).toContain('Network error');
    expect(transformed.originalError).toBe(networkError);
  });

  it('should transform unknown error', () => {
    const unknownError = 'Something went wrong';

    const transformed = transformApiError(unknownError);

    expect(transformed.type).toBe(ApiErrorType.UNKNOWN_ERROR);
    expect(transformed.message).toContain('unexpected error');
  });
});

describe('Retry Logic', () => {
  it('should succeed on first attempt', async () => {
    const mockFn = vi.fn().mockResolvedValue('success');

    const result = await withRetry(mockFn);

    expect(result).toBe('success');
    expect(mockFn).toHaveBeenCalledTimes(1);
  });

  it('should retry on network error', async () => {
    const mockFn = vi
      .fn()
      .mockRejectedValueOnce(new Error('Network error'))
      .mockResolvedValue('success');

    const result = await withRetry(mockFn, {
      maxRetries: 2,
      retryDelay: 10,
    });

    expect(result).toBe('success');
    expect(mockFn).toHaveBeenCalledTimes(2);
  });

  it('should retry on server error (500)', async () => {
    const serverError = new ApiError(
      '/api/test',
      500,
      'Internal Server Error',
      null
    );

    const mockFn = vi
      .fn()
      .mockRejectedValueOnce(serverError)
      .mockResolvedValue('success');

    const result = await withRetry(mockFn, {
      maxRetries: 2,
      retryDelay: 10,
    });

    expect(result).toBe('success');
    expect(mockFn).toHaveBeenCalledTimes(2);
  });

  it('should not retry on authentication error (401)', async () => {
    const authError = new ApiError('/api/test', 401, 'Unauthorized', null);

    const mockFn = vi.fn().mockRejectedValue(authError);

    await expect(
      withRetry(mockFn, { maxRetries: 2, retryDelay: 10 })
    ).rejects.toMatchObject({
      type: ApiErrorType.AUTHENTICATION_ERROR,
    });

    expect(mockFn).toHaveBeenCalledTimes(1);
  });

  it('should not retry on validation error (422)', async () => {
    const validationError = new ApiError(
      '/api/test',
      422,
      'Unprocessable Entity',
      null
    );

    const mockFn = vi.fn().mockRejectedValue(validationError);

    await expect(
      withRetry(mockFn, { maxRetries: 2, retryDelay: 10 })
    ).rejects.toMatchObject({
      type: ApiErrorType.VALIDATION_ERROR,
    });

    expect(mockFn).toHaveBeenCalledTimes(1);
  });

  it('should exhaust retries and throw last error', async () => {
    const networkError = new Error('Network error');
    const mockFn = vi.fn().mockRejectedValue(networkError);

    await expect(
      withRetry(mockFn, { maxRetries: 2, retryDelay: 10 })
    ).rejects.toMatchObject({
      type: ApiErrorType.NETWORK_ERROR,
    });

    expect(mockFn).toHaveBeenCalledTimes(3); // Initial + 2 retries
  });

  it('should use exponential backoff', async () => {
    const mockFn = vi
      .fn()
      .mockRejectedValueOnce(new Error('Network error'))
      .mockRejectedValueOnce(new Error('Network error'))
      .mockResolvedValue('success');

    const startTime = Date.now();
    await withRetry(mockFn, { maxRetries: 3, retryDelay: 100 });
    const endTime = Date.now();

    // First retry: 100ms, second retry: 200ms = 300ms minimum
    expect(endTime - startTime).toBeGreaterThanOrEqual(300);
    expect(mockFn).toHaveBeenCalledTimes(3);
  });

  it('should respect custom retry options', async () => {
    const mockFn = vi
      .fn()
      .mockRejectedValueOnce(new Error('Network error'))
      .mockResolvedValue('success');

    const result = await withRetry(mockFn, {
      maxRetries: 5,
      retryDelay: 50,
    });

    expect(result).toBe('success');
    expect(mockFn).toHaveBeenCalledTimes(2);
  });
});
