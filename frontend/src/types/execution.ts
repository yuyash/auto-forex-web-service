// Task Execution and Metrics types
import { TaskStatus, TaskType } from './common';

export interface ExecutionLog {
  timestamp: string;
  level: string;
  message: string;
}

export interface TaskExecution {
  id: number;
  task_type: TaskType;
  task_id: number;
  execution_number: number;
  status: TaskStatus;
  progress: number;
  started_at: string;
  completed_at?: string;
  error_message?: string;
  error_traceback?: string;
  logs?: ExecutionLog[];
  duration?: string;
  metrics?: ExecutionMetrics;
  created_at: string;
}

export interface ExecutionMetrics {
  id: number;
  execution_id: number;
  total_return: string;
  total_pnl: string;
  realized_pnl?: string;
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

// Periodic, append-only metrics snapshots during execution (best-effort)
export interface ExecutionMetricsCheckpoint {
  id: number;
  execution_id: number;
  processed?: number | null;
  total_return: string;
  total_pnl: string;
  realized_pnl?: string;
  unrealized_pnl?: string;
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  win_rate: string;
  max_drawdown: string;
  sharpe_ratio?: string | null;
  profit_factor?: string | null;
  average_win?: string;
  average_loss?: string;
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
    | 'margin_protection';
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
  realized_pnl?: number;
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
  realized_pnl?: number;
  unrealized_pnl?: number;
  duration?: string;
  // Floor strategy specific fields
  layer_number?: number;
  is_first_lot?: boolean;
  retracement_count?: number;
  entry_retracement_count?: number;
  [key: string]: unknown; // Allow additional properties for DataTable compatibility
}

export interface ExecutionSummary {
  id: number;
  execution_number: number;
  status: TaskStatus;
  progress: number;
  started_at: string;
  completed_at?: string;
  error_message?: string;
  total_return?: string;
  total_pnl?: string;
  realized_pnl?: string;
  unrealized_pnl?: string;
  total_trades?: number;
  winning_trades?: number;
  losing_trades?: number;
  win_rate?: string;
}

export interface ExecutionListParams {
  page?: number;
  page_size?: number;
  status?: TaskStatus;
  ordering?: string;
}
