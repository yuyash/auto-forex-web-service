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
  enum?: (string | number)[];
  items?: {
    type: string;
  };
  // Conditional visibility: show this field only when another field has specific values
  dependsOn?: {
    field: string;
    values: string[];
  };
}

export interface StrategyConfig {
  [key: string]: unknown;
}

export interface StrategyStatus {
  is_active: boolean;
  strategy_type: string | null;
  config: StrategyConfig | null;
  instrument: string;
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
  instrument: string;
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
  balance: string; // Decimal field from backend, serialized as string
  margin_used: string; // Decimal field from backend, serialized as string
  margin_available: string; // Decimal field from backend, serialized as string
  unrealized_pnl: string; // Decimal field from backend, serialized as string
  is_active: boolean;
  is_default?: boolean;
  jurisdiction?: string;
}
