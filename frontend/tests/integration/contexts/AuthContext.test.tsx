/**
 * Integration tests for AuthContext.
 *
 * Verifies login, logout, token refresh, localStorage persistence,
 * system settings fetch, and forced-logout via custom event.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { AuthProvider, useAuth } from '../../../src/contexts/AuthContext';
import { AUTH_LOGOUT_EVENT } from '../../../src/utils/authEvents';
import type { User } from '../../../src/types/auth';

// Mock the api module to avoid side-effects on import
vi.mock('../../../src/api', () => ({
  setAuthToken: vi.fn(),
  clearAuthToken: vi.fn(),
}));

const TEST_USER: User = {
  id: 1,
  email: 'test@example.com',
  username: 'testuser',
  is_staff: false,
  timezone: 'UTC',
  language: 'en',
};

const TEST_TOKEN = 'access-token-abc';
const TEST_REFRESH = 'refresh-token-xyz';

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
      <button
        data-testid="login-btn"
        onClick={() => auth.login(TEST_TOKEN, TEST_REFRESH, TEST_USER)}
      >
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

let fetchSpy: ReturnType<typeof vi.spyOn>;

function mockFetch(overrides: Record<string, () => Response> = {}) {
  fetchSpy.mockImplementation(async (input: RequestInfo | URL) => {
    const url = typeof input === 'string' ? input : input.toString();
    if (overrides[url]) return overrides[url]();

    // Default: public settings
    if (url === '/api/accounts/settings/public') {
      return new Response(
        JSON.stringify({ login_enabled: true, registration_enabled: true }),
        { status: 200, headers: { 'Content-Type': 'application/json' } }
      );
    }
    return new Response('{}', {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    });
  });
}

describe('AuthContext', () => {
  beforeEach(() => {
    localStorage.clear();
    fetchSpy = vi.spyOn(globalThis, 'fetch');
    mockFetch();
  });

  afterEach(() => {
    fetchSpy.mockRestore();
    vi.restoreAllMocks();
  });

  // ── Initial state ──────────────────────────────────────────────

  it('starts unauthenticated when localStorage is empty', async () => {
    renderWithAuth();
    expect(screen.getByTestId('authenticated').textContent).toBe('false');
    expect(screen.getByTestId('user').textContent).toBe('none');
  });

  it('fetches system settings on mount', async () => {
    renderWithAuth();
    await waitFor(() => {
      expect(screen.getByTestId('login-enabled').textContent).toBe('true');
    });
  });

  it('handles system settings fetch failure gracefully', async () => {
    mockFetch({
      '/api/accounts/settings/public': () => new Response('', { status: 500 }),
    });
    renderWithAuth();
    await waitFor(() => {
      expect(screen.getByTestId('settings-loading').textContent).toBe('false');
    });
    expect(screen.getByTestId('login-enabled').textContent).toBe('null');
  });

  // ── Login ──────────────────────────────────────────────────────

  it('updates state and localStorage on login', async () => {
    const user = userEvent.setup();
    renderWithAuth();

    await user.click(screen.getByTestId('login-btn'));

    expect(screen.getByTestId('authenticated').textContent).toBe('true');
    expect(screen.getByTestId('user').textContent).toBe('test@example.com');
    expect(localStorage.getItem('token')).toBe(TEST_TOKEN);
    expect(localStorage.getItem('refresh_token')).toBe(TEST_REFRESH);
    expect(JSON.parse(localStorage.getItem('user')!)).toEqual(TEST_USER);
  });

  it('calls setAuthToken on login', async () => {
    const { setAuthToken } = await import('../../../src/api');
    const user = userEvent.setup();
    renderWithAuth();

    await user.click(screen.getByTestId('login-btn'));

    expect(setAuthToken).toHaveBeenCalledWith(TEST_TOKEN);
  });

  // ── Logout ─────────────────────────────────────────────────────

  it('clears state and localStorage on logout', async () => {
    const user = userEvent.setup();
    renderWithAuth();

    // Login first
    await user.click(screen.getByTestId('login-btn'));
    expect(screen.getByTestId('authenticated').textContent).toBe('true');

    // Logout
    await user.click(screen.getByTestId('logout-btn'));

    expect(screen.getByTestId('authenticated').textContent).toBe('false');
    expect(screen.getByTestId('user').textContent).toBe('none');
    expect(localStorage.getItem('token')).toBeNull();
    expect(localStorage.getItem('refresh_token')).toBeNull();
    expect(localStorage.getItem('user')).toBeNull();
  });

  it('calls logout API endpoint', async () => {
    const user = userEvent.setup();
    renderWithAuth();

    await user.click(screen.getByTestId('login-btn'));
    await user.click(screen.getByTestId('logout-btn'));

    const logoutCall = fetchSpy.mock.calls.find(
      ([url]) => url === '/api/accounts/auth/logout'
    );
    expect(logoutCall).toBeDefined();
  });

  it('clears state even if logout API fails', async () => {
    mockFetch({
      '/api/accounts/settings/public': () =>
        new Response(
          JSON.stringify({ login_enabled: true, registration_enabled: true }),
          { status: 200, headers: { 'Content-Type': 'application/json' } }
        ),
      '/api/accounts/auth/logout': () => new Response('', { status: 500 }),
    });

    const user = userEvent.setup();
    renderWithAuth();

    await user.click(screen.getByTestId('login-btn'));
    await user.click(screen.getByTestId('logout-btn'));

    expect(screen.getByTestId('authenticated').textContent).toBe('false');
  });

  // ── Restore from localStorage ──────────────────────────────────

  it('restores auth state from localStorage on mount', async () => {
    localStorage.setItem('token', TEST_TOKEN);
    localStorage.setItem('refresh_token', TEST_REFRESH);
    localStorage.setItem('user', JSON.stringify(TEST_USER));

    renderWithAuth();

    expect(screen.getByTestId('authenticated').textContent).toBe('true');
    expect(screen.getByTestId('user').textContent).toBe('test@example.com');
  });

  it('handles corrupted localStorage gracefully', async () => {
    localStorage.setItem('token', TEST_TOKEN);
    localStorage.setItem('user', 'not-valid-json');

    renderWithAuth();

    expect(screen.getByTestId('authenticated').textContent).toBe('false');
    expect(localStorage.getItem('token')).toBeNull();
  });

  // ── Token refresh ──────────────────────────────────────────────

  it('refreshes token successfully', async () => {
    const newUser: User = { ...TEST_USER, email: 'refreshed@example.com' };
    mockFetch({
      '/api/accounts/settings/public': () =>
        new Response(
          JSON.stringify({ login_enabled: true, registration_enabled: true }),
          { status: 200, headers: { 'Content-Type': 'application/json' } }
        ),
      '/api/accounts/auth/refresh': () =>
        new Response(
          JSON.stringify({
            token: 'new-token',
            refresh_token: 'new-refresh',
            user: newUser,
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } }
        ),
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
    expect(localStorage.getItem('token')).toBe('new-token');
  });

  it('logs out when token refresh fails', async () => {
    mockFetch({
      '/api/accounts/settings/public': () =>
        new Response(
          JSON.stringify({ login_enabled: true, registration_enabled: true }),
          { status: 200, headers: { 'Content-Type': 'application/json' } }
        ),
      '/api/accounts/auth/refresh': () => new Response('', { status: 401 }),
    });

    const user = userEvent.setup();
    renderWithAuth();

    await user.click(screen.getByTestId('login-btn'));
    await user.click(screen.getByTestId('refresh-btn'));

    await waitFor(() => {
      expect(screen.getByTestId('authenticated').textContent).toBe('false');
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
