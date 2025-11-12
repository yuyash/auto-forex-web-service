// Admin dashboard types

export interface SystemHealth {
  cpu_usage?: number;
  memory_usage?: number;
  disk_usage?: number;
  database_status?: 'connected' | 'disconnected';
  redis_status?: 'connected' | 'disconnected';
  oanda_api_status?: 'connected' | 'disconnected';
  active_streams?: number;
  celery_tasks?: number;
  timestamp?: string;
}

export interface UserSession {
  id: number;
  username: string;
  email: string;
  login_time: string;
  last_activity: string;
  ip_address: string;
  session_count: number;
}

export interface RunningStrategy {
  id: number;
  username: string;
  account_id: string;
  strategy_name: string;
  strategy_type: string;
  start_time: string;
  position_count: number;
  unrealized_pnl: number;
  instrument: string;
}

export interface AdminEvent {
  id: number;
  timestamp: string;
  category: string;
  event_type: string;
  severity: 'debug' | 'info' | 'warning' | 'error' | 'critical';
  description: string;
  user?: string;
  ip_address?: string;
  details?: Record<string, unknown>;
}

export interface AdminDashboardData {
  health?: SystemHealth;
  online_users?: UserSession[];
  running_strategies?: RunningStrategy[];
  recent_events?: AdminEvent[];
}

export interface AdminNotification {
  id: number;
  timestamp: string;
  severity: 'info' | 'warning' | 'error' | 'critical';
  title: string;
  message: string;
  read: boolean;
}

export interface SystemSettings {
  registration_enabled: boolean;
  login_enabled: boolean;
  email_whitelist_enabled: boolean;
  last_updated: string;
  updated_by: string;
}

export interface User {
  id: number;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  is_active: boolean;
  is_staff: boolean;
  is_superuser: boolean;
  is_locked: boolean;
  failed_login_attempts: number;
  date_joined: string;
  last_login: string | null;
}
