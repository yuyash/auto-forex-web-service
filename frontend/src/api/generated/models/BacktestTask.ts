/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */

import type { DataSourceEnum } from './DataSourceEnum';
import type { StatusEnum } from './StatusEnum';
import type { TradingModeEnum } from './TradingModeEnum';
/**
 * Serializer for BacktestTask with execution data.
 */
export type BacktestTask = {
  /**
   * Unique identifier for this record
   */
  readonly id: string;
  /**
   * Human-readable name for this backtest task
   */
  name: string;
  /**
   * Optional description of this backtest task
   */
  description?: string;
  /**
   * Get the task type.
   *
   * Args:
   * obj: Task instance
   *
   * Returns:
   * str: "backtest" or "trading"
   */
  readonly task_type: string;
  /**
   * Current task status
   *
   * * `created` - Created
   * * `starting` - Starting
   * * `running` - Running
   * * `paused` - Paused
   * * `stopping` - Stopping
   * * `stopped` - Stopped
   * * `completed` - Completed
   * * `failed` - Failed
   */
  readonly status: StatusEnum;
  /**
   * Timestamp when this record was created
   */
  readonly created_at: string;
  /**
   * Timestamp when this record was last updated
   */
  readonly updated_at: string;
  /**
   * Timestamp when the task execution started
   */
  readonly started_at: string | null;
  /**
   * Timestamp when the task execution completed
   */
  readonly completed_at: string | null;
  /**
   * Calculate task execution duration in seconds.
   *
   * Args:
   * obj: Task instance
   *
   * Returns:
   * float | None: Duration in seconds if both started_at and completed_at are set,
   * None otherwise
   */
  readonly duration: number | null;
  /**
   * Celery task ID for tracking execution
   */
  readonly celery_task_id: string | null;
  /**
   * Number of times this task has been retried
   */
  retry_count?: number;
  /**
   * Maximum number of retries allowed
   */
  max_retries?: number;
  /**
   * Error message if task failed
   */
  readonly error_message: string | null;
  /**
   * Full error traceback if task failed
   */
  readonly error_traceback: string | null;
  /**
   * User who created this backtest task
   */
  readonly user: number;
  /**
   * Strategy configuration used by this task
   */
  config: string;
  /**
   * Data source for historical tick data
   *
   * * `postgresql` - PostgreSQL
   * * `athena` - AWS Athena
   * * `s3` - AWS S3
   */
  data_source?: DataSourceEnum;
  /**
   * Start time for backtest period
   */
  start_time: string;
  /**
   * End time for backtest period
   */
  end_time: string;
  /**
   * Initial account balance for backtest
   */
  initial_balance?: string;
  /**
   * Commission to apply per trade
   */
  commission_per_trade?: string;
  /**
   * Trading instrument (e.g., EUR_USD, USD_JPY)
   */
  instrument?: string;
  /**
   * Trading mode: netting (aggregated positions) or hedging (independent trades)
   *
   * * `netting` - Netting Mode
   * * `hedging` - Hedging Mode
   */
  trading_mode?: TradingModeEnum;
};
