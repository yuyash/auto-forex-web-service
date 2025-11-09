export interface Strategy {
  id: string;
  name: string;
  class_name: string;
  description: string;
  config_schema: ConfigSchema;
}

export interface ConfigSchema {
  type: string;
  title?: string;
  description?: string;
  display_name?: string;
  properties: Record<string, ConfigProperty>;
  required?: string[];
}

export interface ConfigProperty {
  type: string;
  title?: string;
  description?: string;
  default?: unknown;
  minimum?: number;
  maximum?: number;
  enum?: string[];
  items?: {
    type: string;
  };
}

export interface StrategyConfig {
  [key: string]: unknown;
}

export interface StrategyStatus {
  is_active: boolean;
  strategy_type: string | null;
  config: StrategyConfig | null;
  instruments: string[];
  state: {
    status: string;
    positions_count: number;
    total_pnl: number;
    last_tick_time: string | null;
  } | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface StrategyStartRequest {
  strategy_type: string;
  config: StrategyConfig;
  instruments: string[];
}

export interface StrategyPerformance {
  total_trades: number;
  win_rate: number;
  total_pnl: number;
  average_win: number;
  average_loss: number;
  profit_factor: number;
  max_drawdown: number;
  sharpe_ratio: number;
}

export interface Account {
  id: number;
  account_id: string;
  api_type: 'practice' | 'live';
  currency: string;
  balance: number;
  margin_used: number;
  margin_available: number;
  is_active: boolean;
  jurisdiction?: string;
  enable_position_differentiation?: boolean;
  position_diff_increment?: number;
  position_diff_pattern?: 'increment' | 'decrement' | 'alternating';
}

export interface PositionDifferentiationSettings {
  enable_position_differentiation: boolean;
  position_diff_increment: number;
  position_diff_pattern: 'increment' | 'decrement' | 'alternating';
}
