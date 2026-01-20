/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */

import type { StatusEnum } from './StatusEnum';
/**
 * Serializer for TradingTask list view (summary only).
 */
export type TradingTaskList = {
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
  readonly name: string;
  /**
   * Optional description of this trading task
   */
  readonly description: string;
  /**
   * Close all positions when task is stopped
   */
  readonly sell_on_stop: boolean;
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
   * Timestamp when the task was created
   */
  readonly created_at: string;
  /**
   * Timestamp when the task was last updated
   */
  readonly updated_at: string;
};
