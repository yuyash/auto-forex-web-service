/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */

import type { TradingModeEnum } from './TradingModeEnum';
/**
 * Serializer for TradingTask with execution data.
 */
export type TradingTaskRequest = {
  /**
   * Human-readable name for this trading task
   */
  name: string;
  /**
   * Optional description of this trading task
   */
  description?: string;
  /**
   * Number of times this task has been retried
   */
  retry_count?: number;
  /**
   * Maximum number of retries allowed
   */
  max_retries?: number;
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
};
