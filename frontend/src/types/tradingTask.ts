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
  latest_execution?: ExecutionSummary;
  // State management fields
  has_strategy_state: boolean;
  has_open_positions: boolean;
  open_positions_count: number;
  can_resume: boolean;
  created_at: string;
  updated_at: string;
}

export interface TradingTaskCreateData {
  config_id: string;
  account_id: string;
  name: string;
  description?: string;
  sell_on_stop?: boolean;
}

export interface TradingTaskUpdateData {
  config?: string;
  name?: string;
  description?: string;
  account_id?: string;
  sell_on_stop?: boolean;
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
