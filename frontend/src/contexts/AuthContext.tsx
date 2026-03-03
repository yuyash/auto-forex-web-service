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

const getInitialAuthState = (): {
  token: string | null;
  user: User | null;
  refreshToken: string | null;
} => {
  try {
    const storedToken = localStorage.getItem('token');
    const storedUser = localStorage.getItem('user');
    const storedRefreshToken = localStorage.getItem('refresh_token');

    if (storedToken && storedUser) {
      const parsedUser = JSON.parse(storedUser);
      return {
        token: storedToken,
        user: parsedUser,
        refreshToken: storedRefreshToken,
      };
    }
  } catch (error) {
    console.error('Failed to parse stored user data:', error);
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    localStorage.removeItem('refresh_token');
  }

  return { token: null, user: null, refreshToken: null };
};

export const AuthProvider = ({ children }: { children: ReactNode }) => {
  const initialState = getInitialAuthState();
  const [user, setUser] = useState<User | null>(initialState.user);
  const [token, setToken] = useState<string | null>(initialState.token);
  const [refreshTokenValue, setRefreshTokenValue] = useState<string | null>(
    initialState.refreshToken
  );
  const [systemSettings, setSystemSettings] = useState<SystemSettings | null>(
    null
  );
  const [systemSettingsLoading, setSystemSettingsLoading] =
    useState<boolean>(true);

  // Initialize OpenAPI client with stored token on mount
  useEffect(() => {
    if (initialState.token) {
      setAuthToken(initialState.token);
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const fetchSystemSettings = useCallback(async () => {
    setSystemSettingsLoading(true);
    try {
      const response = await fetch('/api/accounts/settings/public');
      if (response.ok) {
        const data = await response.json();
        setSystemSettings(data);
      } else {
        console.error('Failed to fetch system settings');
      }
    } catch (error) {
      console.error('Error fetching system settings:', error);
    } finally {
      setSystemSettingsLoading(false);
    }
  }, []);

  // Fetch system settings on mount
  useEffect(() => {
    fetchSystemSettings();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const login = useCallback(
    (newToken: string, newRefreshToken: string, newUser: User) => {
      setToken(newToken);
      setRefreshTokenValue(newRefreshToken);
      setUser(newUser);
      localStorage.setItem('token', newToken);
      localStorage.setItem('refresh_token', newRefreshToken);
      localStorage.setItem('user', JSON.stringify(newUser));
      // Configure OpenAPI client with the new token
      setAuthToken(newToken);
    },
    []
  );

  const logout = useCallback(async () => {
    // Call logout API endpoint if token exists
    if (token) {
      try {
        await fetch('/api/accounts/auth/logout', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
          },
        });
      } catch (error) {
        console.error('Logout API call failed:', error);
        // Continue with local logout even if API call fails
      }
    }

    // Clear local state and storage
    setToken(null);
    setRefreshTokenValue(null);
    setUser(null);
    localStorage.removeItem('token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('user');
    // Clear OpenAPI client token
    clearAuthToken();
  }, [token]);

  const refreshToken = useCallback(async (): Promise<boolean> => {
    if (!refreshTokenValue) {
      return false;
    }

    try {
      const response = await fetch('/api/accounts/auth/refresh', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ refresh_token: refreshTokenValue }),
      });

      if (!response.ok) {
        // Token refresh failed, logout user
        await logout();
        return false;
      }

      const data = await response.json();

      if (data.token && data.refresh_token && data.user) {
        // Update token and user
        login(data.token, data.refresh_token, data.user);
        return true;
      }

      return false;
    } catch (error) {
      console.error('Token refresh failed:', error);
      await logout();
      return false;
    }
  }, [refreshTokenValue, login, logout]);

  // Set up token refresh interval (refresh every 20 hours, token expires in 24 hours)
  useEffect(() => {
    if (!token) {
      return;
    }

    // Refresh token every 50 minutes (access token expires in 1 hour)
    const refreshInterval = setInterval(
      () => {
        refreshToken();
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
        console.warn('Authentication error:', detail.message);
      }
      void logout();
    };

    window.addEventListener(AUTH_LOGOUT_EVENT, handleForcedLogout);

    return () => {
      window.removeEventListener(AUTH_LOGOUT_EVENT, handleForcedLogout);
    };
  }, [logout]);

  const value = {
    user,
    token,
    isAuthenticated: !!token && !!user,
    systemSettings,
    systemSettingsLoading,
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
