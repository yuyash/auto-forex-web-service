/**
 * Integration tests for AuthContext.
 *
 * Verifies login, logout, token refresh, bootstrap persistence,
 * system settings fetch, and forced-logout via custom event.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { AuthProvider, useAuth } from '../../../src/contexts/AuthContext';
import { AUTH_LOGOUT_EVENT } from '../../../src/utils/authEvents';
import type { User } from '../../../src/types/auth';
import { ApiError } from '../../../src/api/apiClient';
import { authApi } from '../../../src/services/api';

// Mock the api module to avoid side-effects on import
vi.mock('../../../src/api', () => ({
  setAuthToken: vi.fn(),
  clearAuthToken: vi.fn(),
}));

vi.mock('../../../src/services/api', () => ({
  authApi: {
    getPublicSettings: vi.fn(),
    refresh: vi.fn(),
    logout: vi.fn(),
  },
}));

const TEST_USER: User = {
  id: 1,
  email: 'test@example.com',
  username: 'testuser',
  is_staff: false,
  timezone: 'UTC',
  language: 'en',
};

/** Helper component that exposes auth context values for assertions. */
function AuthConsumer({
  onRender,
}: {
  onRender?: (ctx: ReturnType<typeof useAuth>) => void;
}) {
  const auth = useAuth();
  onRender?.(auth);
  return (
    <div>
      <span data-testid="authenticated">{String(auth.isAuthenticated)}</span>
      <span data-testid="user">{auth.user?.email ?? 'none'}</span>
      <span data-testid="settings-loading">
        {String(auth.systemSettingsLoading)}
      </span>
      <span data-testid="login-enabled">
        {auth.systemSettings?.login_enabled != null
          ? String(auth.systemSettings.login_enabled)
          : 'null'}
      </span>
      <button data-testid="login-btn" onClick={() => auth.login(TEST_USER)}>
        Login
      </button>
      <button data-testid="logout-btn" onClick={() => void auth.logout()}>
        Logout
      </button>
      <button
        data-testid="refresh-btn"
        onClick={() => void auth.refreshToken()}
      >
        Refresh
      </button>
    </div>
  );
}

function renderWithAuth() {
  return render(
    <AuthProvider>
      <AuthConsumer />
    </AuthProvider>
  );
}

const authApiMock = vi.mocked(authApi);

describe('AuthContext', () => {
  beforeEach(() => {
    localStorage.clear();
    authApiMock.getPublicSettings.mockResolvedValue({
      login_enabled: true,
      registration_enabled: true,
    });
    authApiMock.refresh.mockRejectedValue(
      new ApiError('/api/accounts/auth/refresh', 401, 'Unauthorized', null)
    );
    authApiMock.logout.mockResolvedValue({
      message: 'Logged out successfully.',
      sessions_terminated: 0,
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  // ── Initial state ──────────────────────────────────────────────

  it('starts unauthenticated when localStorage is empty', async () => {
    renderWithAuth();
    await waitFor(() => {
      expect(screen.getByTestId('authenticated').textContent).toBe('false');
    });
    expect(screen.getByTestId('user').textContent).toBe('none');
  });

  it('fetches system settings on mount', async () => {
    renderWithAuth();
    await waitFor(() => {
      expect(screen.getByTestId('login-enabled').textContent).toBe('true');
    });
  });

  it('handles system settings fetch failure gracefully', async () => {
    authApiMock.getPublicSettings.mockRejectedValueOnce(new Error('boom'));
    renderWithAuth();
    await waitFor(() => {
      expect(screen.getByTestId('settings-loading').textContent).toBe('false');
    });
    expect(screen.getByTestId('login-enabled').textContent).toBe('null');
  });

  // ── Login ──────────────────────────────────────────────────────

  it('updates state and user storage on login', async () => {
    const user = userEvent.setup();
    renderWithAuth();

    await user.click(screen.getByTestId('login-btn'));

    expect(screen.getByTestId('authenticated').textContent).toBe('true');
    expect(screen.getByTestId('user').textContent).toBe('test@example.com');
    expect(JSON.parse(localStorage.getItem('user')!)).toEqual(TEST_USER);
  });

  it('does not persist the access token in the API client on login', async () => {
    const { clearAuthToken } = await import('../../../src/api');
    const user = userEvent.setup();
    renderWithAuth();

    await user.click(screen.getByTestId('login-btn'));

    expect(clearAuthToken).toHaveBeenCalled();
  });

  // ── Logout ─────────────────────────────────────────────────────

  it('clears state and persisted user on logout', async () => {
    const user = userEvent.setup();
    renderWithAuth();

    // Login first
    await user.click(screen.getByTestId('login-btn'));
    expect(screen.getByTestId('authenticated').textContent).toBe('true');

    // Logout
    await user.click(screen.getByTestId('logout-btn'));

    expect(screen.getByTestId('authenticated').textContent).toBe('false');
    expect(screen.getByTestId('user').textContent).toBe('none');
    expect(localStorage.getItem('user')).toBeNull();
  });

  it('calls logout API service', async () => {
    const user = userEvent.setup();
    renderWithAuth();

    await user.click(screen.getByTestId('login-btn'));
    await user.click(screen.getByTestId('logout-btn'));

    expect(authApiMock.logout).toHaveBeenCalled();
  });

  it('clears state even if logout API fails', async () => {
    authApiMock.logout.mockRejectedValueOnce(new Error('boom'));

    const user = userEvent.setup();
    renderWithAuth();

    await user.click(screen.getByTestId('login-btn'));
    await user.click(screen.getByTestId('logout-btn'));

    expect(screen.getByTestId('authenticated').textContent).toBe('false');
  });

  // ── Restore from persisted user + refresh cookie bootstrap ────

  it('restores auth state by refreshing on mount', async () => {
    localStorage.setItem('user', JSON.stringify(TEST_USER));
    authApiMock.refresh.mockResolvedValueOnce({
      authenticated: true,
      user: TEST_USER,
    });

    renderWithAuth();

    expect(screen.getByTestId('user').textContent).toBe('none');

    await waitFor(() => {
      expect(screen.getByTestId('authenticated').textContent).toBe('true');
    });
    expect(screen.getByTestId('user').textContent).toBe('test@example.com');
  });

  it('handles corrupted localStorage gracefully', async () => {
    localStorage.setItem('user', 'not-valid-json');

    renderWithAuth();

    await waitFor(() => {
      expect(screen.getByTestId('authenticated').textContent).toBe('false');
    });
    expect(localStorage.getItem('user')).toBeNull();
  });

  // ── Token refresh ──────────────────────────────────────────────

  it('refreshes token successfully', async () => {
    const newUser: User = { ...TEST_USER, email: 'refreshed@example.com' };
    authApiMock.refresh
      .mockRejectedValueOnce(
        new ApiError('/api/accounts/auth/refresh', 401, 'Unauthorized', null)
      )
      .mockResolvedValueOnce({
        authenticated: true,
        user: newUser,
      });

    const user = userEvent.setup();
    renderWithAuth();

    // Login first to set refresh token
    await user.click(screen.getByTestId('login-btn'));
    // Trigger refresh
    await user.click(screen.getByTestId('refresh-btn'));

    await waitFor(() => {
      expect(screen.getByTestId('user').textContent).toBe(
        'refreshed@example.com'
      );
    });
    expect(JSON.parse(localStorage.getItem('user')!)).toEqual(newUser);
  });

  it('logs out when token refresh fails', async () => {
    authApiMock.refresh.mockRejectedValue(
      new ApiError('/api/accounts/auth/refresh', 401, 'Unauthorized', null)
    );

    const user = userEvent.setup();
    renderWithAuth();

    await user.click(screen.getByTestId('login-btn'));
    await user.click(screen.getByTestId('refresh-btn'));

    await waitFor(() => {
      expect(screen.getByTestId('authenticated').textContent).toBe('false');
    });
  });

  it('keeps the session on transient refresh failures', async () => {
    authApiMock.refresh
      .mockRejectedValueOnce(
        new ApiError('/api/accounts/auth/refresh', 401, 'Unauthorized', null)
      )
      .mockRejectedValueOnce(new Error('network'));

    const user = userEvent.setup();
    renderWithAuth();

    await user.click(screen.getByTestId('login-btn'));
    await user.click(screen.getByTestId('refresh-btn'));

    await waitFor(() => {
      expect(screen.getByTestId('authenticated').textContent).toBe('true');
    });
  });

  // ── Forced logout via custom event ─────────────────────────────

  it('logs out when AUTH_LOGOUT_EVENT is dispatched', async () => {
    const user = userEvent.setup();
    renderWithAuth();

    await user.click(screen.getByTestId('login-btn'));
    expect(screen.getByTestId('authenticated').textContent).toBe('true');

    // Dispatch forced logout event
    act(() => {
      window.dispatchEvent(
        new CustomEvent(AUTH_LOGOUT_EVENT, {
          detail: { source: 'http', status: 401, message: 'Session expired' },
        })
      );
    });

    await waitFor(() => {
      expect(screen.getByTestId('authenticated').textContent).toBe('false');
    });
  });

  // ── useAuth outside provider ───────────────────────────────────

  it('throws when useAuth is used outside AuthProvider', () => {
    // Suppress console.error for expected error
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    expect(() => render(<AuthConsumer />)).toThrow(
      'useAuth must be used within an AuthProvider'
    );
    consoleSpy.mockRestore();
  });
});
