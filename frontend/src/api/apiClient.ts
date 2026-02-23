/**
 * Lightweight axios-based API client.
 *
 * Replaces the generated openapi-typescript-codegen request layer.
 * Provides typed request helpers for all HTTP methods.
 */

import axios, { type AxiosRequestConfig, type AxiosResponse } from 'axios';
import { apiConfig, getAuthHeaders } from './apiConfig';

export class ApiError extends Error {
  public readonly status: number;
  public readonly statusText: string;
  public readonly body: unknown;
  public readonly url: string;

  constructor(url: string, status: number, statusText: string, body: unknown) {
    super(`API Error: ${status} ${statusText}`);
    this.name = 'ApiError';
    this.url = url;
    this.status = status;
    this.statusText = statusText;
    this.body = body;
  }
}

function buildUrl(path: string): string {
  return `${apiConfig.BASE}${path}`;
}

async function makeRequest<T>(
  method: string,
  path: string,
  options?: {
    body?: unknown;
    query?: Record<string, unknown>;
    headers?: Record<string, string>;
  }
): Promise<T> {
  const url = buildUrl(path);
  const authHeaders = await getAuthHeaders();

  const config: AxiosRequestConfig = {
    method,
    url,
    headers: { ...authHeaders, ...options?.headers },
    withCredentials: apiConfig.WITH_CREDENTIALS,
  };

  if (options?.query) {
    // Filter out undefined values
    const params: Record<string, unknown> = {};
    for (const [key, value] of Object.entries(options.query)) {
      if (value !== undefined && value !== null) {
        params[key] = value;
      }
    }
    config.params = params;
  }

  if (options?.body !== undefined) {
    config.data = options.body;
  }

  let response: AxiosResponse<T>;
  try {
    response = await axios.request<T>(config);
  } catch (error) {
    if (axios.isAxiosError(error) && error.response) {
      throw new ApiError(
        url,
        error.response.status,
        error.response.statusText,
        error.response.data
      );
    }
    throw error;
  }

  if (response.status >= 400) {
    throw new ApiError(
      url,
      response.status,
      response.statusText,
      response.data
    );
  }

  return response.data;
}

export const api = {
  get: <T>(path: string, query?: Record<string, unknown>) =>
    makeRequest<T>('GET', path, { query }),

  post: <T>(path: string, body?: unknown, query?: Record<string, unknown>) =>
    makeRequest<T>('POST', path, { body, query }),

  put: <T>(path: string, body?: unknown, query?: Record<string, unknown>) =>
    makeRequest<T>('PUT', path, { body, query }),

  patch: <T>(path: string, body?: unknown, query?: Record<string, unknown>) =>
    makeRequest<T>('PATCH', path, { body, query }),

  delete: <T = void>(path: string, query?: Record<string, unknown>) =>
    makeRequest<T>('DELETE', path, { query }),
};
