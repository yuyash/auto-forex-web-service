import { ApiError, api, getApiErrorBody } from '../../api/apiClient';
import { withRetry } from '../../api/client';
import type { SystemSettings, User } from '../../types/auth';

export interface LoginRequest {
  email: string;
  password: string;
}

export interface LoginResponse {
  authenticated: boolean;
  user: User;
}

export interface RegisterRequest {
  username: string;
  email: string;
  password: string;
  password_confirm: string;
}

export interface RegisterResponse {
  message: string;
  user: {
    id: number;
    email: string;
    username: string;
  };
}

export interface UserSettingsResponse {
  user: User;
  settings: {
    notification_enabled?: boolean;
  };
}

function getErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError) {
    const body = getApiErrorBody(error);
    if (typeof body?.error === 'string' && body.error.trim()) {
      return body.error;
    }
    if (
      error.body &&
      typeof error.body === 'object' &&
      'message' in error.body &&
      typeof (error.body as { message?: unknown }).message === 'string'
    ) {
      return (error.body as { message: string }).message;
    }
  }

  if (error instanceof Error && error.message) {
    return error.message;
  }

  return fallback;
}

export function getValidationErrors(
  error: unknown
): Record<string, string[] | undefined> {
  if (
    error instanceof ApiError &&
    error.body &&
    typeof error.body === 'object'
  ) {
    return error.body as Record<string, string[] | undefined>;
  }
  return {};
}

export const authApi = {
  login: (data: LoginRequest) =>
    api.post<LoginResponse>('/api/accounts/auth/login', data),

  register: (data: RegisterRequest) =>
    api.post<RegisterResponse>('/api/accounts/auth/register', data),

  refresh: () => api.post<LoginResponse>('/api/accounts/auth/refresh', {}),

  logout: () =>
    api.post<{ message: string; sessions_terminated: number }>(
      '/api/accounts/auth/logout',
      {}
    ),

  getPublicSettings: () =>
    withRetry(() => api.get<SystemSettings>('/api/accounts/settings/public')),

  getUserSettings: () =>
    withRetry(() => api.get<UserSettingsResponse>('/api/accounts/settings/')),

  updateUserSettings: (data: Record<string, unknown>) =>
    api.put<UserSettingsResponse>('/api/accounts/settings/', data),

  getErrorMessage,
};
