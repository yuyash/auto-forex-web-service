// Trading Task types
import { TaskStatus } from './common';
import type { ExecutionSummary } from './execution';

export interface TradingTask {
  id: number;
  user_id: number;
  config_id: number;
  config_name: string;
  strategy_type: string;
  account_id: number;
  account_name: string;
  name: string;
  description: string;
  status: TaskStatus;
  latest_execution?: ExecutionSummary;
  created_at: string;
  updated_at: string;
}

export interface TradingTaskCreateData {
  config_id: number;
  account_id: number;
  name: string;
  description?: string;
}

export interface TradingTaskUpdateData {
  name?: string;
  description?: string;
  account_id?: number;
}

export interface TradingTaskListParams {
  page?: number;
  page_size?: number;
  search?: string;
  status?: TaskStatus;
  config_id?: number;
  account_id?: number;
  strategy_type?: string;
  ordering?: string;
}

export interface TradingTaskCopyData {
  new_name: string;
}
