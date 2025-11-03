export interface User {
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

export interface AuthContextType {
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
