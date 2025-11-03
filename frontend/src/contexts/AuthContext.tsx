import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
} from 'react';
import type { ReactNode } from 'react';

interface User {
  id: number;
  email: string;
  username: string;
  is_staff: boolean;
  timezone: string;
  language: string;
}

export interface SystemSettings {
  registration_enabled: boolean;
  login_enabled: boolean;
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  systemSettings: SystemSettings | null;
  systemSettingsLoading: boolean;
  login: (token: string, user: User) => void;
  logout: () => Promise<void>;
  refreshToken: () => Promise<boolean>;
  refetchSystemSettings: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const getInitialAuthState = (): { token: string | null; user: User | null } => {
  try {
    const storedToken = localStorage.getItem('token');
    const storedUser = localStorage.getItem('user');

    if (storedToken && storedUser) {
      const parsedUser = JSON.parse(storedUser);
      return { token: storedToken, user: parsedUser };
    }
  } catch (error) {
    console.error('Failed to parse stored user data:', error);
    localStorage.removeItem('token');
    localStorage.removeItem('user');
  }

  return { token: null, user: null };
};

export const AuthProvider = ({ children }: { children: ReactNode }) => {
  const initialState = getInitialAuthState();
  const [user, setUser] = useState<User | null>(initialState.user);
  const [token, setToken] = useState<string | null>(initialState.token);
  const [systemSettings, setSystemSettings] = useState<SystemSettings | null>(
    null
  );
  const [systemSettingsLoading, setSystemSettingsLoading] =
    useState<boolean>(true);

  const fetchSystemSettings = useCallback(async () => {
    setSystemSettingsLoading(true);
    try {
      const response = await fetch('/api/system/settings/public');
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
  }, [fetchSystemSettings]);

  const login = useCallback((newToken: string, newUser: User) => {
    setToken(newToken);
    setUser(newUser);
    localStorage.setItem('token', newToken);
    localStorage.setItem('user', JSON.stringify(newUser));
  }, []);

  const logout = useCallback(async () => {
    // Call logout API endpoint if token exists
    if (token) {
      try {
        await fetch('/api/auth/logout', {
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
    setUser(null);
    localStorage.removeItem('token');
    localStorage.removeItem('user');
  }, [token]);

  const refreshToken = useCallback(async (): Promise<boolean> => {
    if (!token) {
      return false;
    }

    try {
      const response = await fetch('/api/auth/refresh', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        // Token refresh failed, logout user
        await logout();
        return false;
      }

      const data = await response.json();

      if (data.token && data.user) {
        // Update token and user
        login(data.token, data.user);
        return true;
      }

      return false;
    } catch (error) {
      console.error('Token refresh failed:', error);
      await logout();
      return false;
    }
  }, [token, login, logout]);

  // Set up token refresh interval (refresh every 20 hours, token expires in 24 hours)
  useEffect(() => {
    if (!token) {
      return;
    }

    // Refresh token every 20 hours (72000000 ms)
    const refreshInterval = setInterval(
      () => {
        refreshToken();
      },
      20 * 60 * 60 * 1000
    );

    return () => {
      clearInterval(refreshInterval);
    };
  }, [token, refreshToken]);

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

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
