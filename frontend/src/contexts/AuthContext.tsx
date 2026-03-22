import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
} from 'react';
import type { ReactNode } from 'react';
import type { User, SystemSettings, AuthContextType } from '../types/auth';
import { AUTH_LOGOUT_EVENT, type AuthLogoutDetail } from '../utils/authEvents';
import { setAuthToken, clearAuthToken } from '../api';
import i18n from '../i18n/config';
import { useIdleTimeout } from '../hooks/useIdleTimeout';
import { authApi } from '../services/api';
import { ApiError } from '../api/apiClient';
import { logger } from '../utils/logger';
import {
  readStoredValue,
  removeStoredValue,
  writeStoredValue,
} from '../utils/persistentState';
import { z } from 'zod';

// Persist context across HMR to prevent "useAuth must be used within AuthProvider" errors
// during Vite hot module replacement
const AUTH_CONTEXT_KEY = '__AUTH_CONTEXT__';
const globalWindow =
  typeof window !== 'undefined'
    ? (window as unknown as Record<string, unknown>)
    : ({} as Record<string, unknown>);

if (!globalWindow[AUTH_CONTEXT_KEY]) {
  globalWindow[AUTH_CONTEXT_KEY] = createContext<AuthContextType | undefined>(
    undefined
  );
}

const AuthContext = globalWindow[AUTH_CONTEXT_KEY] as React.Context<
  AuthContextType | undefined
>;
const persistedUserSchema = z.custom<User>(
  (value) => value !== null && typeof value === 'object'
);
const appSettingsSchema = z.object({
  sessionTimeoutMinutes: z.number().optional(),
});

export const AuthProvider = ({ children }: { children: ReactNode }) => {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [systemSettings, setSystemSettings] = useState<SystemSettings | null>(
    null
  );
  const [systemSettingsLoadingState, setSystemSettingsLoading] =
    useState<boolean>(true);
  const [authBootstrapLoading, setAuthBootstrapLoading] = useState(true);

  useEffect(() => {
    const storedUser = readStoredValue('user', persistedUserSchema, null);
    if (storedUser === null) {
      const rawUser = window.localStorage.getItem('user');
      if (rawUser) {
        logger.warn('Removing invalid persisted user payload');
        removeStoredValue('user');
      }
    }
  }, []);

  const clearPersistedAuth = useCallback(() => {
    removeStoredValue('user');
    clearAuthToken();
  }, []);

  const clearSessionState = useCallback(() => {
    setToken(null);
    setUser(null);
    clearPersistedAuth();
  }, [clearPersistedAuth]);

  const fetchSystemSettings = useCallback(async () => {
    setSystemSettingsLoading(true);
    try {
      setSystemSettings(await authApi.getPublicSettings());
    } catch (error) {
      logger.error('Error fetching system settings', {
        error: error instanceof Error ? error.message : String(error),
      });
    } finally {
      setSystemSettingsLoading(false);
    }
  }, []);

  // Fetch system settings on mount
  useEffect(() => {
    fetchSystemSettings();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const login = useCallback((newToken: string, newUser: User) => {
    setToken(newToken);
    setUser(newUser);
    writeStoredValue('user', newUser);
    setAuthToken(newToken);
    if (newUser.language && !localStorage.getItem('i18nextLng')) {
      i18n.changeLanguage(newUser.language);
    }
  }, []);

  const logout = useCallback(async () => {
    if (token) {
      try {
        await authApi.logout();
      } catch (error) {
        logger.warn('Logout API call failed', {
          error: error instanceof Error ? error.message : String(error),
        });
      }
    }
    clearSessionState();
  }, [clearSessionState, token]);

  const refreshToken = useCallback(async (): Promise<boolean> => {
    try {
      const data = await authApi.refresh();
      if (data.token && data.user) {
        login(data.token, data.user);
        return true;
      }
      return false;
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        clearSessionState();
        return false;
      }
      logger.warn('Token refresh failed', {
        error: error instanceof Error ? error.message : String(error),
      });
      return false;
    }
  }, [clearSessionState, login]);

  useEffect(() => {
    let isMounted = true;

    const bootstrapAuth = async () => {
      try {
        await refreshToken();
      } finally {
        if (isMounted) {
          setAuthBootstrapLoading(false);
        }
      }
    };

    void bootstrapAuth();

    return () => {
      isMounted = false;
    };
  }, [refreshToken]);

  useEffect(() => {
    if (!token) {
      return;
    }

    const refreshInterval = setInterval(
      () => {
        void refreshToken();
      },
      50 * 60 * 1000
    );

    return () => {
      clearInterval(refreshInterval);
    };
  }, [token, refreshToken]);

  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }

    const handleForcedLogout = (event: Event) => {
      const detail = (event as CustomEvent<AuthLogoutDetail>).detail;
      if (detail?.message) {
        logger.warn('Authentication error', { message: detail.message });
      }
      void logout();
    };

    window.addEventListener(AUTH_LOGOUT_EVENT, handleForcedLogout);

    return () => {
      window.removeEventListener(AUTH_LOGOUT_EVENT, handleForcedLogout);
    };
  }, [logout]);

  // Idle session timeout — read from app settings in localStorage
  const sessionTimeoutMinutes = (() => {
    const settings = readStoredValue('app_settings', appSettingsSchema, {});
    if (typeof settings.sessionTimeoutMinutes === 'number') {
      return settings.sessionTimeoutMinutes;
    }
    return 30; // default 30 minutes
  })();

  useIdleTimeout(
    token ? sessionTimeoutMinutes : 0,
    useCallback(() => {
      logger.warn('Session timed out due to inactivity');
      void logout();
    }, [logout])
  );

  const value = {
    user,
    token,
    isAuthenticated: !!token && !!user,
    systemSettings,
    systemSettingsLoading: systemSettingsLoadingState || authBootstrapLoading,
    authLoading: authBootstrapLoading,
    appLoading: systemSettingsLoadingState,
    login,
    logout,
    refreshToken,
    refetchSystemSettings: fetchSystemSettings,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

// eslint-disable-next-line react-refresh/only-export-components
export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
