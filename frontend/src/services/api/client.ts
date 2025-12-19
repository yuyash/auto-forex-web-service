// API Client utility with authentication and error handling

import type { ApiError } from '../../types/common';

export class ApiClientError extends Error {
  status: number;
  data: unknown;

  constructor(status: number, data: unknown, message: string) {
    super(message);
    this.name = 'ApiClientError';
    this.status = status;
    this.data = data;
  }
}

export class ApiClient {
  private baseURL: string;

  constructor(baseURL: string = '/api') {
    this.baseURL = baseURL;
  }

  private getAuthHeaders(): HeadersInit {
    const token = localStorage.getItem('token');
    return {
      'Content-Type': 'application/json',
      ...(token && { Authorization: `Bearer ${token}` }),
    };
  }

  private extractErrorMessage(errorData: unknown, response: Response): string {
    if (errorData && typeof errorData === 'object') {
      const maybe = errorData as Record<string, unknown>;

      const errorObj = maybe.error as
        | { message?: unknown; details?: unknown }
        | undefined;
      if (errorObj && typeof errorObj === 'object') {
        const msg = (errorObj as { message?: unknown }).message;
        if (typeof msg === 'string' && msg.trim()) {
          return msg;
        }
      }

      if (typeof maybe.message === 'string' && maybe.message.trim()) {
        return maybe.message;
      }

      if (typeof maybe.detail === 'string' && maybe.detail.trim()) {
        return maybe.detail;
      }

      // DRF serializer validation errors often look like:
      // { field: ["msg"], other_field: ["msg"] }
      for (const [key, value] of Object.entries(maybe)) {
        if (
          Array.isArray(value) &&
          typeof value[0] === 'string' &&
          value[0].trim()
        ) {
          return `${key}: ${value[0]}`;
        }
        if (typeof value === 'string' && value.trim()) {
          return `${key}: ${value}`;
        }
      }
    }

    return `HTTP ${response.status}: ${response.statusText}`;
  }

  private async handleResponse<T>(response: Response): Promise<T> {
    if (!response.ok) {
      let errorData: ApiError | unknown;
      try {
        errorData = await response.json();
      } catch {
        errorData = null;
      }

      const message = this.extractErrorMessage(errorData, response);

      // Special handling for rate limiting
      if (response.status === 429) {
        throw new ApiClientError(
          response.status,
          errorData,
          'Too many requests. Please wait before trying again.'
        );
      }

      throw new ApiClientError(response.status, errorData, message);
    }

    // Handle 204 No Content
    if (response.status === 204) {
      return {} as T;
    }

    return response.json();
  }

  async get<T>(endpoint: string, params?: Record<string, unknown>): Promise<T> {
    const url = new URL(`${this.baseURL}${endpoint}`, window.location.origin);

    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null) {
          url.searchParams.append(key, String(value));
        }
      });
    }

    try {
      const response = await fetch(url.toString(), {
        method: 'GET',
        headers: this.getAuthHeaders(),
      });

      return this.handleResponse<T>(response);
    } catch (error) {
      // Handle network errors
      if (error instanceof TypeError) {
        throw new ApiClientError(
          0,
          { message: 'Network error. Server may be unavailable.' },
          'Network error. Server may be unavailable.'
        );
      }
      throw error;
    }
  }

  async post<T>(endpoint: string, data?: unknown): Promise<T> {
    try {
      const response = await fetch(`${this.baseURL}${endpoint}`, {
        method: 'POST',
        headers: this.getAuthHeaders(),
        body: data ? JSON.stringify(data) : undefined,
      });

      return this.handleResponse<T>(response);
    } catch (error) {
      // Handle network errors
      if (error instanceof TypeError) {
        throw new ApiClientError(
          0,
          { message: 'Network error. Server may be unavailable.' },
          'Network error. Server may be unavailable.'
        );
      }
      throw error;
    }
  }

  async put<T>(endpoint: string, data: unknown): Promise<T> {
    try {
      const response = await fetch(`${this.baseURL}${endpoint}`, {
        method: 'PUT',
        headers: this.getAuthHeaders(),
        body: JSON.stringify(data),
      });

      return this.handleResponse<T>(response);
    } catch (error) {
      // Handle network errors
      if (error instanceof TypeError) {
        throw new ApiClientError(
          0,
          { message: 'Network error. Server may be unavailable.' },
          'Network error. Server may be unavailable.'
        );
      }
      throw error;
    }
  }

  async patch<T>(endpoint: string, data: unknown): Promise<T> {
    try {
      const response = await fetch(`${this.baseURL}${endpoint}`, {
        method: 'PATCH',
        headers: this.getAuthHeaders(),
        body: JSON.stringify(data),
      });

      return this.handleResponse<T>(response);
    } catch (error) {
      // Handle network errors
      if (error instanceof TypeError) {
        throw new ApiClientError(
          0,
          { message: 'Network error. Server may be unavailable.' },
          'Network error. Server may be unavailable.'
        );
      }
      throw error;
    }
  }

  async delete<T>(endpoint: string): Promise<T> {
    try {
      const response = await fetch(`${this.baseURL}${endpoint}`, {
        method: 'DELETE',
        headers: this.getAuthHeaders(),
      });

      return this.handleResponse<T>(response);
    } catch (error) {
      // Handle network errors
      if (error instanceof TypeError) {
        throw new ApiClientError(
          0,
          { message: 'Network error. Server may be unavailable.' },
          'Network error. Server may be unavailable.'
        );
      }
      throw error;
    }
  }
}

// Create a singleton instance
export const apiClient = new ApiClient();
