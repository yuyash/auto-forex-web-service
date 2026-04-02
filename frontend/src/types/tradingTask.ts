// Trading Task types
import { TaskStatus } from './common';
import type { ExecutionSummary } from './execution';

export interface TradingTask {
  id: string;
  user_id: number;
  config_id: string;
  config_name: string;
  strategy_type: string;
  instrument: string;
  account_id: string;
  account_name: string;
  account_type: 'live' | 'practice';
  name: string;
  description: string;
  status: TaskStatus;
  sell_on_stop: boolean;
  dry_run: boolean;
  hedging_enabled: boolean;
  latest_execution?: ExecutionSummary;
  has_strategy_state?: boolean;
  can_resume?: boolean;
  execution_id?: string;
  started_at?: string;
  completed_at?: string;
  error_message?: string;
  pip_size?: string;
  created_at: string;
  updated_at: string;
  debug_options?: Record<string, unknown>;
}

export interface TradingTaskCreateData {
  config_id: string;
  account_id: string;
  name: string;
  description?: string;
  instrument?: string;
  sell_on_stop?: boolean;
  dry_run?: boolean;
  hedging_enabled?: boolean;
}

export interface TradingTaskUpdateData {
  config?: string;
  name?: string;
  description?: string;
  account_id?: string;
  sell_on_stop?: boolean;
  dry_run?: boolean;
  hedging_enabled?: boolean;
  debug_options?: Record<string, unknown>;
}

export interface TradingTaskListParams {
  page?: number;
  page_size?: number;
  search?: string;
  status?: TaskStatus;
  config_id?: string;
  account_id?: string;
  strategy_type?: string;
  ordering?: string;
}

export interface TradingTaskCopyData {
  new_name: string;
}
