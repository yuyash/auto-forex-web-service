// API Client utility with authentication and error handling

import type { ApiError } from '../../types/common';

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

  private async handleResponse<T>(response: Response): Promise<T> {
    if (!response.ok) {
      let errorData: ApiError;
      try {
        errorData = await response.json();
      } catch {
        errorData = {
          message: `HTTP ${response.status}: ${response.statusText}`,
        };
      }

      // Special handling for rate limiting
      if (response.status === 429) {
        throw {
          status: response.status,
          data: errorData,
          message: 'Too many requests. Please wait before trying again.',
        };
      }

      throw {
        status: response.status,
        data: errorData,
        message:
          errorData.error?.message ||
          errorData.message ||
          errorData.detail ||
          'An error occurred',
      };
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
        throw {
          status: 0,
          data: { message: 'Network error. Server may be unavailable.' },
          message: 'Network error. Server may be unavailable.',
        };
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
        throw {
          status: 0,
          data: { message: 'Network error. Server may be unavailable.' },
          message: 'Network error. Server may be unavailable.',
        };
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
        throw {
          status: 0,
          data: { message: 'Network error. Server may be unavailable.' },
          message: 'Network error. Server may be unavailable.',
        };
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
        throw {
          status: 0,
          data: { message: 'Network error. Server may be unavailable.' },
          message: 'Network error. Server may be unavailable.',
        };
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
        throw {
          status: 0,
          data: { message: 'Network error. Server may be unavailable.' },
          message: 'Network error. Server may be unavailable.',
        };
      }
      throw error;
    }
  }
}

// Create a singleton instance
export const apiClient = new ApiClient();
