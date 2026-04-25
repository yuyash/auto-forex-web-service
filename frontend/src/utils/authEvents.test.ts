import { describe, expect, it, vi } from 'vitest';
import {
  AUTH_LOGOUT_EVENT,
  handleAuthErrorStatus,
  shouldBroadcastAuthLogoutForHttp,
} from './authEvents';

describe('authEvents', () => {
  it('broadcasts logout for refresh failures', () => {
    const listener = vi.fn();
    window.addEventListener(AUTH_LOGOUT_EVENT, listener);

    const handled = handleAuthErrorStatus(401, {
      source: 'http',
      url: '/api/accounts/auth/refresh',
    });

    window.removeEventListener(AUTH_LOGOUT_EVENT, listener);
    expect(handled).toBe(true);
    expect(listener).toHaveBeenCalledTimes(1);
  });

  it('does not broadcast logout for unrelated 401 responses', () => {
    expect(
      shouldBroadcastAuthLogoutForHttp({
        status: 401,
        source: 'http',
        url: '/api/trading/tasks/backtest/',
      })
    ).toBe(false);
  });
});
