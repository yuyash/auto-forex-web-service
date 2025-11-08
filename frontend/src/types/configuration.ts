// Strategy Configuration types

export interface StrategyConfig {
  id: number;
  user_id: number;
  name: string;
  strategy_type: string;
  parameters: Record<string, unknown>;
  description: string;
  is_in_use: boolean;
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
}

export interface ConfigurationTask {
  id: number;
  task_type: 'backtest' | 'trading';
  name: string;
  status: string;
}
