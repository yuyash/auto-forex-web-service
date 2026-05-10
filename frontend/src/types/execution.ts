// Task Execution types
import type { TaskStatus, TaskType } from './common';

export interface ExecutionLog {
  timestamp: string;
  level: string;
  message: string;
}

export interface TaskExecution {
  id: string;
  task_type: TaskType;
  task_id: string;
  execution_number: number;
  segment_index?: number;
  config_revision_count?: number;
  status: TaskStatus;
  progress: number;
  started_at: string;
  completed_at?: string;
  error_message?: string;
  error_code?: string;
  logs?: ExecutionLog[];
  duration?: string;
  created_at: string;
  notes?: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  metrics?: Record<string, any>;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  task_config?: Record<string, any> | null;
  strategy_config?: {
    id: string;
    name: string;
    strategy_type: string;
    current?: {
      id?: string;
      name?: string;
      strategy_type?: string;
      parameters?: Record<string, unknown>;
    };
    initial?: Record<string, unknown>;
    revisions?: Array<Record<string, unknown>>;
    config_hash?: string;
    segment_index?: number;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    parameters: Record<string, any>;
  } | null;
}

export interface ExecutionMetrics {
  id: string;
  execution_id: string;
  total_return: string;
  total_pnl: string;
  unrealized_pnl?: string;
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  win_rate: string;
  max_drawdown: string;
  sharpe_ratio?: string;
  profit_factor?: string;
  average_win?: string;
  average_loss?: string;
  equity_curve?: EquityPoint[];
  trade_log?: Trade[];
  strategy_events?: BacktestStrategyEvent[];
  created_at: string;
}

export interface BacktestStrategyEvent {
  event_type: string;
  timestamp?: string;
  instrument?: string;
  layer_number?: number;
  retracement_count?: number;
  max_retracements_per_layer?: number;
  direction?: 'long' | 'short' | 'mixed';
  units?: string | number;
  bid?: string | number;
  ask?: string | number;
  price?: string | number;
  entry_price?: string | number;
  exit_price?: string | number;
  pips?: string | number;
  pnl?: string | number;
  entry_time?: string | null;
  exit_time?: string | null;
}

export interface StrategyEvent {
  event_type:
    | 'initial'
    | 'retracement'
    | 'layer'
    | 'close'
    | 'take_profit'
    | 'volatility_lock'
    | 'margin_protection'
    | 'stop_loss';
  timestamp: string;
  layer_number: number;
  retracement_count: number;
  entry_retracement_count?: number;
  direction?: 'long' | 'short';
  units?: number;
  entry_price?: number;
  exit_price?: number;
  pnl?: number;
  message?: string;
  metadata?: Record<string, unknown>;
}

export interface EquityPoint {
  timestamp: string;
  balance: number;
  unrealized_pnl?: number;
}

export interface Trade {
  entry_time: string;
  exit_time: string;
  instrument: string;
  direction: 'long' | 'short';
  units: number;
  entry_price: number;
  exit_price: number;
  pnl: number;
  unrealized_pnl?: number;
  duration?: string;
  // Layered strategy specific fields
  layer_number?: number;
  is_first_lot?: boolean;
  retracement_count?: number;
  entry_retracement_count?: number;
  [key: string]: unknown; // Allow additional properties for DataTable compatibility
}

export interface ExecutionSummary {
  id: string;
  execution_number: number;
  status: TaskStatus;
  progress: number;
  started_at: string;
  completed_at?: string;
  error_message?: string;
  error_code?: string;
  total_return?: string;
  total_pnl?: string;
  total_pnl_quote?: string;
  realized_pnl_quote?: string;
  unrealized_pnl_quote?: string;
  total_trades?: number;
  winning_trades?: number;
  losing_trades?: number;
  win_rate?: string;
  pnl_currency?: string;
  quote_currency?: string;
}

export interface ExecutionListParams {
  page?: number;
  page_size?: number;
  status?: TaskStatus;
  ordering?: string;
}

export interface ExecutionMetricsCheckpoint {
  total_return?: string;
  total_pnl?: string;
  total_trades?: number;
  winning_trades?: number;
  losing_trades?: number;
  win_rate?: string;
  max_drawdown?: string;
  sharpe_ratio?: string;
  profit_factor?: string;
  average_win?: string;
  average_loss?: string;
  timestamp?: string;
}
