/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { StatusEnum } from './StatusEnum';
import type { TradingModeEnum } from './TradingModeEnum';
/**
 * Serializer for TradingTask with execution data.
 */
export type TradingTask = {
  /**
   * Unique identifier for this record
   */
  readonly id: string;
  /**
   * Human-readable name for this trading task
   */
  name: string;
  /**
   * Optional description of this trading task
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
   * User who created this trading task
   */
  readonly user: number;
  /**
   * Strategy configuration used by this task
   */
  config: string;
  /**
   * OANDA account used for trading
   */
  oanda_account: number;
  /**
   * Close all positions when task is stopped
   */
  sell_on_stop?: boolean;
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
  /**
   * Strategy-specific state for persistence across restarts
   */
  readonly strategy_state: any;
};
