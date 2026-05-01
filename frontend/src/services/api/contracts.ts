import type { PaginatedApiResponse } from './pagination';
import type { TaskActionPolicy } from '../../types/common';
import type { StrategyCapabilities } from '../../types/strategy';

export interface BackendExecutionMetrics {
  total_return?: string;
  total_pnl?: string;
  unrealized_pnl?: string;
  total_pnl_quote?: string;
  realized_pnl_quote?: string;
  unrealized_pnl_quote?: string;
  total_trades?: number;
  winning_trades?: number;
  losing_trades?: number;
  win_rate?: string;
  pnl_currency?: string;
  quote_currency?: string;
}

export interface BackendTaskExecutionSummary extends BackendExecutionMetrics {
  id: string;
  task_type: 'backtest' | 'trading';
  task_id: string;
  execution_number: string;
  segment_index?: number;
  config_revision_count?: number;
  status: string;
  progress: number;
  started_at?: string | null;
  completed_at?: string | null;
  error_message?: string | null;
  error_traceback?: string | null;
  duration?: number | null;
  created_at: string;
}

export interface BackendBacktestTask {
  id: string;
  user_id: number;
  config_id: string;
  config_name: string;
  strategy_type: string;
  name: string;
  description: string;
  data_source: string;
  start_time: string;
  end_time: string;
  initial_balance: string;
  account_currency?: string;
  commission_per_trade: string;
  pip_size?: string | null;
  instrument: string;
  hedging_enabled: boolean;
  sell_on_stop: boolean;
  tick_granularity: string;
  tick_window_value_mode: string;
  status: string;
  execution_id?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
  error_message?: string | null;
  latest_execution?: BackendTaskExecutionSummary | null;
  can_resume?: boolean;
  action_policy?: TaskActionPolicy;
  drain_duration_hours?: number;
  market_idle_pre_close_minutes?: number;
  market_idle_resume_delay_minutes?: number;
  market_close_enabled?: boolean;
  market_close_weekday?: number;
  market_close_hour_utc?: number;
  market_open_weekday?: number;
  market_open_hour_utc?: number;
  max_tick_gap_hours?: number;
  created_at: string;
  updated_at: string;
  debug_options?: Record<string, unknown>;
}

export interface BackendTradingTask {
  id: string;
  user_id: number;
  config_id: string;
  config_name: string;
  strategy_type: string;
  instrument: string;
  account_id: number;
  account_name: string;
  account_type: 'live' | 'practice';
  name: string;
  description: string;
  sell_on_stop: boolean;
  dry_run: boolean;
  hedging_enabled: boolean;
  pip_size?: string | null;
  status: string;
  execution_id?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
  error_message?: string | null;
  latest_execution?: BackendTaskExecutionSummary | null;
  has_strategy_state: boolean;
  can_resume: boolean;
  action_policy?: TaskActionPolicy;
  api_retry_max_attempts?: number;
  api_retry_backoff_base_seconds?: string;
  api_retry_backoff_max_seconds?: string;
  drain_duration_hours?: number;
  market_idle_pre_close_minutes?: number;
  market_idle_resume_delay_minutes?: number;
  created_at: string;
  updated_at: string;
  debug_options?: Record<string, unknown>;
}

export interface BackendConfigurationTask {
  id: string;
  task_type: 'backtest' | 'trading';
  name: string;
  status: string;
}

export interface BackendConfigurationTaskList {
  results: BackendConfigurationTask[];
}

export interface BackendStrategyConfig {
  id: string;
  user_id: number;
  name: string;
  strategy_type: string;
  parameters?: Record<string, unknown> | null;
  description: string;
  is_in_use: boolean;
  has_running_tasks: boolean;
  created_at: string;
  updated_at: string;
}

export interface BackendStrategyListResponse {
  strategies: Array<{
    id: string;
    name: string;
    class_name?: string;
    description: string;
    capabilities?: StrategyCapabilities;
    config_schema: Record<string, unknown>;
  }>;
  count: number;
}

export interface BackendStrategyDefaultsResponse {
  strategy_id: string;
  defaults: Record<string, unknown>;
}

export interface BackendAccount {
  id?: number;
  account_id: string;
  api_type?: 'practice' | 'live';
  jurisdiction?: string;
  currency?: string;
  balance?: string;
  margin_used?: string;
  margin_available?: string;
  unrealized_pnl?: string;
  is_active?: boolean;
  is_default?: boolean;
  created_at?: string;
  updated_at?: string;
  nav?: string;
  open_trade_count?: number;
  open_position_count?: number;
  pending_order_count?: number;
  live_data?: boolean;
  live_data_error?: string;
  snapshot_refreshed_at?: string | null;
  snapshot_stale?: boolean;
  snapshot_refresh_error?: string;
  snapshot_refresh_task_id?: string;
  snapshot_refresh_status?: BackendAccountSnapshotRefreshStatus;
  snapshot_refresh_status_updated_at?: string | null;
  hedging_enabled?: boolean;
  position_mode?: 'hedging' | 'netting';
  oanda_account?: Record<string, unknown>;
}

export type BackendAccountSnapshotRefreshStatus =
  | 'idle'
  | 'queued'
  | 'running'
  | 'completed'
  | 'failed';

export interface BackendAccountSnapshotRefreshResponse {
  id: number;
  account_id: string;
  task_id: string;
  status: BackendAccountSnapshotRefreshStatus;
  snapshot_refreshed_at: string | null;
  snapshot_stale: boolean;
  snapshot_refresh_error: string;
  snapshot_refresh_status_updated_at: string | null;
}

export type BackendPaginatedBacktestTasks =
  PaginatedApiResponse<BackendBacktestTask>;
export type BackendPaginatedTradingTasks =
  PaginatedApiResponse<BackendTradingTask>;
export type BackendPaginatedConfigurations =
  PaginatedApiResponse<BackendStrategyConfig>;
