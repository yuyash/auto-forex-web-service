export const AUTH_LOGOUT_EVENT = 'auth:logout';

export interface AuthLogoutDetail {
  source?: 'http' | 'ws';
  status?: number;
  message?: string;
  context?: string;
}

const AUTH_ERROR_STATUSES = new Set([401, 419, 4401, 4403]);
const AUTH_CLOSE_CODES = new Set([4001, 4401, 4403]);

export const isAuthErrorStatus = (status: number): boolean =>
  AUTH_ERROR_STATUSES.has(status);

export const broadcastAuthLogout = (detail?: AuthLogoutDetail) => {
  if (
    typeof window === 'undefined' ||
    typeof window.dispatchEvent !== 'function'
  ) {
    return;
  }

  window.dispatchEvent(
    new CustomEvent<AuthLogoutDetail>(AUTH_LOGOUT_EVENT, { detail })
  );
};

export const handleAuthErrorStatus = (
  status: number,
  detail?: AuthLogoutDetail
): boolean => {
  if (!isAuthErrorStatus(status)) {
    return false;
  }

  broadcastAuthLogout({ ...detail, status, source: detail?.source ?? 'http' });
  return true;
};

export const handleWebSocketAuthClose = (
  event: CloseEvent,
  detail?: AuthLogoutDetail
): boolean => {
  const reason = event.reason?.toLowerCase?.() ?? '';
  const isAuthClose =
    AUTH_CLOSE_CODES.has(event.code) ||
    reason.includes('unauthorized') ||
    reason.includes('forbidden') ||
    reason.includes('token') ||
    reason.includes('authentication');

  if (!isAuthClose) {
    return false;
  }

  broadcastAuthLogout({
    ...detail,
    source: 'ws',
    status: detail?.status ?? event.code,
    message: detail?.message ?? (event.reason || undefined),
  });

  return true;
};

export const installAuthFetchInterceptor = () => {
  if (typeof window === 'undefined') {
    return;
  }

  const globalScope = window as typeof window & {
    __authInterceptorInstalled__?: boolean;
  };

  if (
    globalScope.__authInterceptorInstalled__ ||
    typeof window.fetch !== 'function'
  ) {
    return;
  }

  const originalFetch = window.fetch.bind(window);

  const hasAuthorizationHeader = (
    input: RequestInfo | URL,
    init?: RequestInit
  ): boolean => {
    if (input instanceof Request) {
      return !!input.headers.get('Authorization');
    }

    const headers = init?.headers;

    if (!headers) {
      return false;
    }

    if (headers instanceof Headers) {
      return headers.has('Authorization');
    }

    if (Array.isArray(headers)) {
      return headers.some(([key]) => key.toLowerCase() === 'authorization');
    }

    return Object.entries(headers as Record<string, unknown>).some(
      ([key]) => key.toLowerCase() === 'authorization'
    );
  };

  window.fetch = async (...args: Parameters<typeof fetch>) => {
    const [input, init] = args;
    const includesAuthHeader = hasAuthorizationHeader(input, init);

    const response = await originalFetch(...args);

    if (includesAuthHeader) {
      handleAuthErrorStatus(response.status, {
        source: 'http',
        status: response.status,
      });
    }

    return response;
  };

  globalScope.__authInterceptorInstalled__ = true;
};
