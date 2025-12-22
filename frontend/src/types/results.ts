import type { TaskStatus, TaskType } from './common';
import type {
  BacktestStrategyEvent,
  EquityPoint,
  ExecutionMetrics,
  ExecutionMetricsCheckpoint,
  Trade,
} from './execution';

export interface TaskResultsExecutionSummary {
  id: number;
  execution_number: number;
  status: TaskStatus;
  progress: number;
  started_at?: string | null;
  completed_at?: string | null;
  error_message?: string | null;
}

/**
 * Unified results payload for both trading and backtest tasks.
 *
 * - `live` mirrors Redis live snapshot when present
 * - `metrics` mirrors the latest execution metrics when present
 */
export interface TaskResults {
  task_id: number;
  task_type: TaskType | 'trading' | 'backtest';
  status: TaskStatus;
  execution?: TaskResultsExecutionSummary | null;

  has_live: boolean;
  live?: Record<string, unknown> | null;

  has_metrics: boolean;
  metrics?: ExecutionMetrics | null;
}

export interface TaskEquityCurveResponse {
  task_id: number;
  task_type: TaskType | 'trading' | 'backtest';
  execution_id?: number | null;
  has_metrics: boolean;
  equity_curve: EquityPoint[];
  count: number;
  next: string | null;
  previous: string | null;
  equity_curve_granularity_seconds?: number | null;
}

export interface TaskStrategyEventsResponse {
  task_id: number;
  task_type: TaskType | 'trading' | 'backtest';
  execution_id?: number | null;
  has_metrics: boolean;
  strategy_events: BacktestStrategyEvent[];
  count: number;
  next: string | null;
  previous: string | null;
}

export interface TaskTradeLogsResponse {
  task_id: number;
  task_type: TaskType | 'trading' | 'backtest';
  execution_id?: number | null;
  has_metrics: boolean;
  trade_logs: Trade[];
  count: number;
  next: string | null;
  previous: string | null;
}

export interface TaskMetricsCheckpointResponse {
  task_id: number;
  task_type: TaskType | 'trading' | 'backtest';
  execution_id?: number | null;
  has_checkpoint: boolean;
  checkpoint: ExecutionMetricsCheckpoint | null;
}
