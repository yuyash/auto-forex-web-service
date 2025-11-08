// Backtest Task types
import { TaskStatus, DataSource } from './common';
import type { ExecutionSummary } from './execution';

export interface BacktestTask {
  id: number;
  user_id: number;
  config_id: number;
  config_name: string;
  strategy_type: string;
  name: string;
  description: string;
  data_source: DataSource;
  start_time: string;
  end_time: string;
  initial_balance: string;
  commission_per_trade: string;
  instruments: string[];
  status: TaskStatus;
  latest_execution?: ExecutionSummary;
  created_at: string;
  updated_at: string;
}

export interface BacktestTaskCreateData {
  config_id: number;
  name: string;
  description?: string;
  data_source: DataSource;
  start_time: string;
  end_time: string;
  initial_balance: number | string;
  commission_per_trade?: number | string;
  instruments: string[];
}

export interface BacktestTaskUpdateData {
  name?: string;
  description?: string;
  data_source?: DataSource;
  start_time?: string;
  end_time?: string;
  initial_balance?: number | string;
  commission_per_trade?: number | string;
  instruments?: string[];
}

export interface BacktestTaskListParams {
  page?: number;
  page_size?: number;
  search?: string;
  status?: TaskStatus;
  config_id?: number;
  strategy_type?: string;
  ordering?: string;
}

export interface BacktestTaskCopyData {
  new_name: string;
}
