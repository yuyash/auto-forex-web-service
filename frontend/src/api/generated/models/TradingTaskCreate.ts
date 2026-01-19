/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * Serializer for creating and updating TradingTask.
 *
 * Includes validation for account ownership and configuration.
 */
export type TradingTaskCreate = {
  /**
   * Strategy configuration used by this task
   */
  config?: number;
  /**
   * OANDA account used for trading
   */
  oanda_account?: number;
  /**
   * Human-readable name for this trading task
   */
  name?: string;
  /**
   * Optional description of this trading task
   */
  description?: string;
  /**
   * Close all positions when task is stopped
   */
  sell_on_stop?: boolean;
};
