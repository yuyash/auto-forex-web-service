/**
 * Unit tests for auth event utilities.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  isAuthErrorStatus,
  broadcastAuthLogout,
  handleAuthErrorStatus,
  AUTH_LOGOUT_EVENT,
  shouldBroadcastAuthLogoutForHttp,
} from '../../../src/utils/authEvents';

describe('isAuthErrorStatus', () => {
  it('returns true for 401', () => {
    expect(isAuthErrorStatus(401)).toBe(true);
  });

  it('returns true for 419', () => {
    expect(isAuthErrorStatus(419)).toBe(true);
  });

  it('returns false for 200', () => {
    expect(isAuthErrorStatus(200)).toBe(false);
  });

  it('returns false for 403', () => {
    expect(isAuthErrorStatus(403)).toBe(false);
  });

  it('returns false for 500', () => {
    expect(isAuthErrorStatus(500)).toBe(false);
  });
});

describe('broadcastAuthLogout', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('dispatches custom event on window', () => {
    const spy = vi.spyOn(window, 'dispatchEvent');
    broadcastAuthLogout({ source: 'http', status: 401 });

    expect(spy).toHaveBeenCalledTimes(1);
    const event = spy.mock.calls[0][0] as CustomEvent;
    expect(event.type).toBe(AUTH_LOGOUT_EVENT);
    expect(event.detail?.status).toBe(401);
  });
});

describe('handleAuthErrorStatus', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('returns true and broadcasts for refresh auth failures', () => {
    const spy = vi.spyOn(window, 'dispatchEvent');
    expect(
      handleAuthErrorStatus(401, { url: '/api/accounts/auth/refresh' })
    ).toBe(true);
    expect(spy).toHaveBeenCalled();
  });

  it('returns false for non-auth statuses', () => {
    const spy = vi.spyOn(window, 'dispatchEvent');
    expect(handleAuthErrorStatus(404)).toBe(false);
    expect(spy).not.toHaveBeenCalled();
  });

  it('returns false for unrelated 401 responses', () => {
    const spy = vi.spyOn(window, 'dispatchEvent');
    expect(handleAuthErrorStatus(401, { url: '/api/tasks/123/' })).toBe(false);
    expect(spy).not.toHaveBeenCalled();
  });
});

describe('shouldBroadcastAuthLogoutForHttp', () => {
  it('accepts refresh endpoint failures', () => {
    expect(
      shouldBroadcastAuthLogoutForHttp({
        status: 401,
        url: '/api/accounts/auth/refresh',
      })
    ).toBe(true);
  });

  it('rejects generic unauthorized responses', () => {
    expect(
      shouldBroadcastAuthLogoutForHttp({
        status: 401,
        url: '/api/trading/tasks/',
      })
    ).toBe(false);
  });
});
