/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { StatusEnum } from './StatusEnum';
/**
 * Serializer for TradingTask full details.
 */
export type TradingTask = {
  readonly id: number;
  readonly user_id: number;
  readonly config_id: number;
  readonly config_name: string;
  readonly strategy_type: string;
  /**
   * Get instrument from configuration parameters.
   */
  readonly instrument: string;
  readonly account_id: number;
  readonly account_name: string;
  readonly account_type: string;
  /**
   * Human-readable name for this trading task
   */
  name: string;
  /**
   * Optional description of this trading task
   */
  description?: string;
  /**
   * Close all positions when task is stopped
   */
  sell_on_stop?: boolean;
  /**
   * Current task status
   *
   * * `created` - Created
   * * `running` - Running
   * * `stopped` - Stopped
   * * `completed` - Completed
   * * `failed` - Failed
   */
  readonly status: StatusEnum;
  /**
   * Get summary of latest execution with metrics.
   */
  readonly latest_execution: Record<string, any> | null;
  /**
   * Check if task has saved strategy state.
   */
  readonly has_strategy_state: boolean;
  /**
   * Check if task can be resumed with state recovery.
   */
  readonly can_resume: boolean;
  /**
   * Timestamp when the task was created
   */
  readonly created_at: string;
  /**
   * Timestamp when the task was last updated
   */
  readonly updated_at: string;
};
