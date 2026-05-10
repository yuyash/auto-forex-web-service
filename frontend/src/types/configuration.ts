// Strategy Configuration types

export interface StrategyConfig {
  id: string;
  user_id: number;
  name: string;
  strategy_type: string;
  parameters: Record<string, unknown>;
  revision: number;
  config_hash: string;
  description: string;
  is_in_use: boolean;
  has_running_tasks: boolean;
  created_at: string;
  updated_at: string;
}

export interface StrategyConfigCreateData {
  name: string;
  strategy_type: string;
  parameters: Record<string, unknown>;
  description?: string;
}

export interface StrategyConfigUpdateData {
  name?: string;
  parameters?: Record<string, unknown>;
  description?: string;
}

export interface StrategyConfigListParams {
  page?: number;
  page_size?: number;
  search?: string;
  strategy_type?: string;
  ordering?: string;
  created_from?: string;
  created_to?: string;
  updated_from?: string;
  updated_to?: string;
}

export interface ConfigurationTask {
  id: string;
  task_type: 'backtest' | 'trading';
  name: string;
  status: string;
}
