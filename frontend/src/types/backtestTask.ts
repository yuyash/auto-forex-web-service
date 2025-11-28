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
  instrument: string;
  status: TaskStatus;
  sell_at_completion: boolean;
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
  instrument: string;
  sell_at_completion?: boolean;
}

// Form data type - matches the validation schema (after transformation)
export interface BacktestTaskFormData {
  config_id: number;
  name: string;
  description?: string;
  data_source: DataSource;
  start_time: string;
  end_time: string;
  initial_balance: number;
  commission_per_trade?: number;
  instrument: string;
  sell_at_completion?: boolean;
}

export interface BacktestTaskUpdateData {
  config?: number;
  name?: string;
  description?: string;
  data_source?: DataSource;
  start_time?: string;
  end_time?: string;
  initial_balance?: number | string;
  commission_per_trade?: number | string;
  instrument?: string;
  sell_at_completion?: boolean;
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

/**
 * Live/intermediate results during backtest execution
 */
export interface BacktestLiveResults {
  task_id: number;
  has_data: boolean;
  message?: string;
  day_date?: string;
  progress?: number;
  days_processed?: number;
  total_days?: number;
  ticks_processed?: number;
  balance?: number;
  total_trades?: number;
  metrics?: {
    total_pnl?: number;
    total_return?: number;
    win_rate?: number;
    winning_trades?: number;
    losing_trades?: number;
    average_win?: number;
    average_loss?: number;
    profit_factor?: number;
    max_drawdown?: number;
    sharpe_ratio?: number;
    [key: string]: number | string | undefined;
  };
  recent_trades?: Array<{
    timestamp: string;
    instrument: string;
    direction: string;
    entry_price: number;
    exit_price: number;
    units: number;
    pnl: number;
    duration: number;
    [key: string]: string | number | boolean | undefined;
  }>;
  equity_curve?: Array<{
    timestamp: string;
    balance: number;
    [key: string]: string | number | undefined;
  }>;
}
