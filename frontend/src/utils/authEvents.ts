export const AUTH_LOGOUT_EVENT = 'auth:logout';

export interface AuthLogoutDetail {
  source?: 'http';
  status?: number;
  message?: string;
  context?: string;
  url?: string;
}

const AUTH_ERROR_STATUSES = new Set([401, 419, 4401, 4403]);

export const isAuthErrorStatus = (status: number): boolean =>
  AUTH_ERROR_STATUSES.has(status);

const SESSION_EXPIRY_PATHS = ['/api/accounts/auth/refresh'];

function normalizePath(url?: string): string | null {
  if (!url) {
    return null;
  }

  try {
    return new URL(url, window.location.origin).pathname;
  } catch {
    return url.startsWith('/') ? url : null;
  }
}

export const shouldBroadcastAuthLogoutForHttp = (
  detail?: AuthLogoutDetail
): boolean => {
  if (!detail?.status || !isAuthErrorStatus(detail.status)) {
    return false;
  }

  if (detail.context === 'auth_refresh') {
    return true;
  }

  const path = normalizePath(detail.url);
  return path !== null && SESSION_EXPIRY_PATHS.includes(path);
};

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
  const logoutDetail = {
    ...detail,
    status,
    source: detail?.source ?? 'http',
  };

  if (!shouldBroadcastAuthLogoutForHttp(logoutDetail)) {
    return false;
  }

  broadcastAuthLogout(logoutDetail);
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
        url:
          input instanceof Request
            ? input.url
            : input instanceof URL
              ? input.toString()
              : String(input),
      });
    }

    return response;
  };

  globalScope.__authInterceptorInstalled__ = true;
};
