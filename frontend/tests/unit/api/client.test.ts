/**
 * Unit tests for API client wrapper.
 * Tests pure logic: token management, error transformation, retry.
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
    configureApiClient({
      baseUrl: 'http://localhost:8000',
      token: '',
      withCredentials: true,
    });
  });

  it('configures base URL', () => {
    configureApiClient({ baseUrl: 'https://api.example.com' });
    expect(apiConfig.BASE).toBe('https://api.example.com');
  });

  it('configures credentials', () => {
    configureApiClient({ withCredentials: false });
    expect(apiConfig.WITH_CREDENTIALS).toBe(false);
  });

  it('configures authentication token', () => {
    configureApiClient({ token: 'test-token' });
    expect(apiConfig.TOKEN).toBe('test-token');
  });

  it('merges partial config with existing values', () => {
    configureApiClient({ baseUrl: 'https://api.example.com' });
    expect(apiConfig.WITH_CREDENTIALS).toBe(true);
  });
});

describe('Authentication Token Management', () => {
  beforeEach(() => {
    clearAuthToken();
  });

  it('sets and retrieves token', () => {
    setAuthToken('abc123');
    expect(getAuthToken()).toBe('abc123');
    expect(apiConfig.TOKEN).toBe('abc123');
  });

  it('clears token', () => {
    setAuthToken('abc123');
    clearAuthToken();
    expect(getAuthToken()).toBe('');
    expect(apiConfig.TOKEN).toBeUndefined();
  });

  it('reports authentication state', () => {
    expect(isAuthenticated()).toBe(false);
    setAuthToken('token');
    expect(isAuthenticated()).toBe(true);
    clearAuthToken();
    expect(isAuthenticated()).toBe(false);
  });

  it('treats empty string as unauthenticated', () => {
    setAuthToken('');
    expect(isAuthenticated()).toBe(false);
  });
});

describe('Error Transformation', () => {
  const cases: [number, string, ApiErrorType][] = [
    [401, 'Unauthorized', ApiErrorType.AUTHENTICATION_ERROR],
    [403, 'Forbidden', ApiErrorType.AUTHORIZATION_ERROR],
    [404, 'Not Found', ApiErrorType.NOT_FOUND_ERROR],
    [422, 'Unprocessable Entity', ApiErrorType.VALIDATION_ERROR],
    [500, 'Internal Server Error', ApiErrorType.SERVER_ERROR],
  ];

  it.each(cases)('transforms %i %s → %s', (status, statusText, expected) => {
    const err = new ApiError('/api/test', status, statusText, {});
    expect(transformApiError(err).type).toBe(expected);
  });

  it('transforms network errors', () => {
    const err = new Error('Network request failed');
    const result = transformApiError(err);
    expect(result.type).toBe(ApiErrorType.NETWORK_ERROR);
    expect(result.originalError).toBe(err);
  });

  it('transforms unknown errors', () => {
    const result = transformApiError('something');
    expect(result.type).toBe(ApiErrorType.UNKNOWN_ERROR);
  });
});

describe('Retry Logic', () => {
  it('succeeds on first attempt', async () => {
    const fn = vi.fn().mockResolvedValue('ok');
    expect(await withRetry(fn)).toBe('ok');
    expect(fn).toHaveBeenCalledTimes(1);
  });

  it('retries on network error then succeeds', async () => {
    const fn = vi
      .fn()
      .mockRejectedValueOnce(new Error('Network'))
      .mockResolvedValue('ok');

    expect(await withRetry(fn, { maxRetries: 2, retryDelay: 10 })).toBe('ok');
    expect(fn).toHaveBeenCalledTimes(2);
  });

  it('retries on 500 then succeeds', async () => {
    const fn = vi
      .fn()
      .mockRejectedValueOnce(new ApiError('/x', 500, 'ISE', null))
      .mockResolvedValue('ok');

    expect(await withRetry(fn, { maxRetries: 2, retryDelay: 10 })).toBe('ok');
    expect(fn).toHaveBeenCalledTimes(2);
  });

  it('does not retry 401', async () => {
    const fn = vi
      .fn()
      .mockRejectedValue(new ApiError('/x', 401, 'Unauthorized', null));

    await expect(
      withRetry(fn, { maxRetries: 2, retryDelay: 10 })
    ).rejects.toMatchObject({ type: ApiErrorType.AUTHENTICATION_ERROR });
    expect(fn).toHaveBeenCalledTimes(1);
  });

  it('does not retry 422', async () => {
    const fn = vi
      .fn()
      .mockRejectedValue(new ApiError('/x', 422, 'Unprocessable', null));

    await expect(
      withRetry(fn, { maxRetries: 2, retryDelay: 10 })
    ).rejects.toMatchObject({ type: ApiErrorType.VALIDATION_ERROR });
    expect(fn).toHaveBeenCalledTimes(1);
  });

  it('exhausts retries then throws', async () => {
    const fn = vi.fn().mockRejectedValue(new Error('Network'));

    await expect(
      withRetry(fn, { maxRetries: 2, retryDelay: 10 })
    ).rejects.toMatchObject({ type: ApiErrorType.NETWORK_ERROR });
    expect(fn).toHaveBeenCalledTimes(3);
  });
});
