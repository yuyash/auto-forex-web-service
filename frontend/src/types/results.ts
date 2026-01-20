import type { TaskStatus, TaskType } from './common';
import type { ExecutionMetrics } from './execution';

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
