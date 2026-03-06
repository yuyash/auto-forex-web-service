export interface Strategy {
  id: string;
  name: string;
  class_name: string;
  description: string;
  config_schema: ConfigSchema;
}

export type JsonPrimitive = string | number | boolean | null;

export interface ConfigSchema {
  type: string;
  title?: string;
  description?: string;
  display_name?: string;
  properties: Record<string, ConfigProperty>;
  required?: string[];
}

export interface DependsOnCondition {
  field: string;
  values: JsonPrimitive[];
  and?: DependsOnCondition[];
  or?: DependsOnCondition[];
}

export interface ConfigProperty {
  type: string;
  title?: string;
  description?: string;
  default?: unknown;
  minimum?: number;
  maximum?: number;
  enum?: (string | number)[];
  properties?: Record<string, ConfigProperty>;
  required?: string[];
  items?: {
    type: string;
    enum?: (string | number)[];
    properties?: Record<string, ConfigProperty>;
    required?: string[];
    minimum?: number;
    maximum?: number;
  };
  /** Logical group for UI section grouping */
  group?: string;
  // Conditional visibility: show this field only when another field has specific values
  dependsOn?: DependsOnCondition;
  /**
   * For array fields: derive the required element count from another field.
   * `field` is the config key to read, `offset` is added to that value.
   * Example: { field: "r_max", offset: -1 } → array length = r_max − 1.
   */
  linkedCount?: {
    field: string;
    offset?: number;
  };
  /**
   * Label template for each array element.
   * `{index}` is replaced with the 1-based element index.
   */
  itemLabel?: string;
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
    timestamp: string | null;
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
  nav?: string;
  open_trade_count?: number;
  open_position_count?: number;
  pending_order_count?: number;
  live_data?: boolean;
  live_data_error?: string;
  hedging_enabled?: boolean;
  position_mode?: 'hedging' | 'netting';
  oanda_account?: Record<string, unknown>;
  is_active: boolean;
  is_default?: boolean;
  jurisdiction?: string;
}
